from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError


class GeneratedWorkspace:
    ALLOWED_ROOTS = {"backend", "frontend", "docs"}
    EXCLUDED_PARTS = {"node_modules", ".venv", "__pycache__", ".pytest_cache", "dist", ".git"}

    def __init__(self, project_id: str, build_id: str) -> None:
        settings = get_settings()
        self.settings = settings
        self.root = (settings.agent_build_root / project_id / build_id).resolve()

    def initialize_fullstack(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        for path, content in baseline_files().items():
            self.write(path, content)

    def initialize_from(self, source_root: Path) -> None:
        source = source_root.resolve()
        if not source.is_dir() or source == self.root or source in self.root.parents:
            raise AppError(422, "BASE_WORKSPACE_INVALID", "增量构建的基础工作区无效")
        if self.root.exists():
            shutil.rmtree(self.root)
        shutil.copytree(
            source,
            self.root,
            ignore=shutil.ignore_patterns("node_modules", "dist", ".venv", ".git", "__pycache__", ".pytest_cache", "coverage.json", "*.log"),
        )

    def manifest(self) -> dict[str, str]:
        return {item["path"]: item["sha256"] for item in self.list_files()}

    @staticmethod
    def diff_manifests(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
        before_paths, after_paths = set(before), set(after)
        return {
            "added": sorted(after_paths - before_paths),
            "removed": sorted(before_paths - after_paths),
            "modified": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
        }

    def write(self, relative_path: str, content: str) -> dict[str, Any]:
        normalized = relative_path.replace("\\", "/").lstrip("/")
        if not normalized or normalized.split("/", 1)[0] not in self.ALLOWED_ROOTS:
            raise AppError(422, "GENERATED_PATH_INVALID", "生成文件必须位于 backend、frontend 或 docs 目录", {"path": relative_path})
        if any(part in {"..", "", ".git", "node_modules", ".venv"} for part in Path(normalized).parts):
            raise AppError(422, "GENERATED_PATH_INVALID", "生成文件路径包含禁止目录", {"path": relative_path})
        target = (self.root / normalized).resolve()
        if self.root not in target.parents:
            raise AppError(422, "GENERATED_PATH_INVALID", "生成文件越出项目工作目录", {"path": relative_path})
        self._validate_sensitive_file(normalized, content)
        encoded = content.encode("utf-8")
        if len(encoded) > self.settings.agent_max_file_bytes:
            raise AppError(422, "GENERATED_FILE_TOO_LARGE", "单个生成文件超过大小限制", {"path": relative_path, "size": len(encoded)})
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": normalized, "size": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}

    def apply_bundle(self, bundle: dict[str, Any], *, allowed_prefix: str | None = None) -> list[dict[str, Any]]:
        files = bundle.get("files")
        if not isinstance(files, list):
            raise AppError(422, "CODE_BUNDLE_INVALID", "模型响应必须包含 files 数组")
        if len(files) > self.settings.agent_max_files:
            raise AppError(422, "TOO_MANY_GENERATED_FILES", "生成文件数量超过限制", {"count": len(files)})
        written = []
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise AppError(422, "CODE_BUNDLE_INVALID", "每个生成文件必须包含 path 和 content")
            path = item["path"].replace("\\", "/")
            if allowed_prefix and not path.startswith(f"{allowed_prefix}/"):
                raise AppError(422, "GENERATED_PATH_SCOPE_ERROR", "Agent 尝试写入职责范围外的文件", {"path": path, "allowed": allowed_prefix})
            written.append(self.write(path, item["content"]))
        return written

    @staticmethod
    def _validate_sensitive_file(path: str, content: str) -> None:
        if path == "frontend/package.json":
            try:
                package = json.loads(content)
            except json.JSONDecodeError as exc:
                raise AppError(422, "PACKAGE_JSON_INVALID", "生成的 package.json 不是有效 JSON") from exc
            scripts = package.get("scripts", {})
            if scripts.get("build") != "vite build":
                raise AppError(422, "PACKAGE_SCRIPT_BLOCKED", "前端 build 脚本必须固定为 vite build")
            if scripts.get("test") != "vitest run":
                raise AppError(422, "PACKAGE_SCRIPT_BLOCKED", "前端 test 脚本必须固定为 vitest run")
            allowed_runtime = {"vue"}
            allowed_dev = {"vite", "@vitejs/plugin-vue", "typescript", "vue-tsc", "vitest", "@vue/test-utils", "jsdom"}
            unknown = set(package.get("dependencies", {})) - allowed_runtime
            unknown_dev = set(package.get("devDependencies", {})) - allowed_dev
            if unknown or unknown_dev:
                raise AppError(422, "PACKAGE_DEPENDENCY_BLOCKED", "生成项目引用了未批准的前端依赖", {"dependencies": sorted(unknown | unknown_dev)})
        if path == "backend/requirements.txt":
            allowed = {"fastapi", "uvicorn", "pydantic", "pytest", "pytest-cov", "httpx", "sqlalchemy", "alembic", "psycopg", "python-multipart"}
            unknown = []
            for raw in content.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                name = line.split(";", 1)[0].split("[", 1)[0]
                for marker in ["==", ">=", "<=", "~=", "!=", ">", "<"]:
                    name = name.split(marker, 1)[0]
                if name.strip().lower() not in allowed:
                    unknown.append(name.strip())
            if unknown:
                raise AppError(422, "PYTHON_DEPENDENCY_BLOCKED", "生成项目引用了未批准的 Python 依赖", {"dependencies": unknown})

    def list_files(self, include_content: bool = False) -> list[dict[str, Any]]:
        result = []
        if not self.root.exists():
            return result
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or self._is_runtime_artifact(path):
                continue
            relative = path.relative_to(self.root).as_posix()
            data = path.read_bytes()
            item: dict[str, Any] = {"path": relative, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if include_content and len(data) <= self.settings.agent_max_file_bytes:
                item["content"] = data.decode("utf-8", errors="replace")
            result.append(item)
        return result

    def read(self, relative_path: str) -> str:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents or not target.is_file() or self._is_runtime_artifact(target):
            raise AppError(404, "GENERATED_FILE_NOT_FOUND", "生成文件不存在", {"path": relative_path})
        return target.read_text(encoding="utf-8", errors="replace")

    def source_snapshot(self, max_chars: int = 120_000) -> str:
        chunks: list[str] = []
        total = 0
        for item in self.list_files(include_content=True):
            if item["path"].endswith(("package-lock.json", ".log")):
                continue
            block = f"\n--- FILE: {item['path']} ---\n{item.get('content', '')}\n"
            if total + len(block) > max_chars:
                break
            chunks.append(block)
            total += len(block)
        return "".join(chunks)

    def _is_runtime_artifact(self, path: Path) -> bool:
        return (
            any(part in self.EXCLUDED_PARTS for part in path.parts)
            or path.name in {"coverage.json", ".coverage"}
            or path.suffix == ".log"
        )

    def create_archive(self) -> Path:
        archive = self.root.parent / f"{self.root.name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in self.root.rglob("*"):
                if not path.is_file() or self._is_runtime_artifact(path):
                    continue
                output.write(path, path.relative_to(self.root))
        return archive


def baseline_files() -> dict[str, str]:
    return {
        "backend/app/__init__.py": "",
        "backend/app/main.py": '''from fastapi import FastAPI\n\napp = FastAPI(title="Generated Application")\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n''',
        "backend/tests/test_health.py": '''from fastapi.testclient import TestClient\nfrom app.main import app\n\nclient = TestClient(app)\n\ndef test_health():\n    response = client.get("/health")\n    assert response.status_code == 200\n    assert response.json() == {"status": "ok"}\n''',
        "backend/requirements.txt": "fastapi>=0.116,<1.0\nuvicorn>=0.35,<1.0\npydantic>=2.11,<3.0\npytest>=8.4,<10.0\npytest-cov>=6.2,<8.0\nhttpx>=0.28,<1.0\n",
        "frontend/package.json": json.dumps({
            "name": "generated-agent-app", "private": True, "version": "1.0.0", "type": "module",
            "scripts": {"dev": "vite", "build": "vite build", "test": "vitest run"},
            "dependencies": {"vue": "3.5.18"},
            "devDependencies": {"@vitejs/plugin-vue": "6.0.1", "vite": "7.3.6", "vitest": "3.2.4", "@vue/test-utils": "2.4.6", "jsdom": "26.1.0"},
        }, ensure_ascii=False, indent=2),
        "frontend/index.html": '<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Generated App</title></head><body><div id="app"></div><script type="module" src="/src/main.js"></script></body></html>',
        "frontend/vite.config.js": "import { defineConfig } from 'vite'\nimport vue from '@vitejs/plugin-vue'\nexport default defineConfig({ plugins: [vue()] })\n",
        "frontend/src/main.js": "import { createApp } from 'vue'\nimport App from './App.vue'\nimport './style.css'\ncreateApp(App).mount('#app')\n",
        "frontend/src/App.vue": '''<script setup>\nimport { ref } from 'vue'\nconst message = ref('应用正在等待 Agent 生成功能')\n</script>\n<template><main><h1>Generated Application</h1><p>{{ message }}</p></main></template>\n''',
        "frontend/src/App.test.js": "import { mount } from '@vue/test-utils'\nimport { describe, expect, it } from 'vitest'\nimport App from './App.vue'\ndescribe('App',()=>{it('renders',()=>{expect(mount(App).text()).toContain('Generated Application')})})\n",
        "frontend/src/style.css": "body{margin:0;font-family:system-ui,sans-serif;background:#f5f7fb;color:#202636}main{max-width:960px;margin:80px auto;padding:32px;background:white;border-radius:16px;box-shadow:0 12px 35px #20263614}",
        "docs/README.md": "# Generated Full-stack Application\n\nThis workspace was created by Agent Studio.\n",
    }
