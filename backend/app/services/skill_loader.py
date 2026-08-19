from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError, not_found

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,79}$")


@dataclass(frozen=True, slots=True)
class SkillManifest:
    name: str
    display_name: str
    version: str
    description: str
    entrypoint: str | None
    instructions: str
    agent_types: tuple[str, ...]
    tags: tuple[str, ...]
    input_schema: dict[str, Any]
    path: Path
    checksum: str

    @property
    def executable(self) -> bool:
        return bool(self.entrypoint)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "instructions": self.instructions,
            "agent_types": list(self.agent_types),
            "tags": list(self.tags),
            "input_schema": self.input_schema,
            "path": str(self.path),
            "executable": self.executable,
            "checksum": self.checksum,
        }


class SkillRegistry:
    """Loads declarative skills from disk without importing their code into the API process."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest] = {}
        self._errors: list[dict[str, str]] = []
        self._lock = threading.RLock()

    @property
    def errors(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._errors)

    def reload(self) -> list[SkillManifest]:
        loaded: dict[str, SkillManifest] = {}
        errors: list[dict[str, str]] = []
        for root in get_settings().skill_directories:
            if not root.exists():
                continue
            for manifest_path in sorted(root.glob("*/skill.json")):
                try:
                    skill = self._load_manifest(manifest_path)
                    if skill.name in loaded:
                        raise ValueError(f"duplicate skill name: {skill.name}")
                    loaded[skill.name] = skill
                except Exception as exc:  # malformed third-party skill should not stop startup
                    errors.append({"path": str(manifest_path), "error": str(exc)})
        with self._lock:
            self._skills = loaded
            self._errors = errors
        return self.list()

    def list(self, agent_key: str | None = None) -> list[SkillManifest]:
        with self._lock:
            values = list(self._skills.values())
        if agent_key:
            values = [item for item in values if not item.agent_types or agent_key in item.agent_types or "*" in item.agent_types]
        return sorted(values, key=lambda item: item.name)

    def get(self, name: str) -> SkillManifest:
        with self._lock:
            skill = self._skills.get(name)
        if not skill:
            raise not_found("Skill", name)
        return skill

    def validate_input(self, skill: SkillManifest, data: dict[str, Any]) -> None:
        schema = skill.input_schema or {}
        required = schema.get("required", [])
        missing = [name for name in required if name not in data]
        if missing:
            raise AppError(422, "SKILL_INPUT_INVALID", "Skill 输入缺少必填字段", {"missing": missing})
        properties = schema.get("properties", {})
        type_map = {"string": str, "array": list, "object": dict, "number": (int, float), "integer": int, "boolean": bool}
        invalid = []
        for key, value in data.items():
            expected_name = properties.get(key, {}).get("type")
            expected = type_map.get(expected_name)
            if expected and not isinstance(value, expected):
                invalid.append({"field": key, "expected": expected_name})
        if invalid:
            raise AppError(422, "SKILL_INPUT_INVALID", "Skill 输入字段类型错误", {"invalid": invalid})

    def read_entrypoint(self, skill: SkillManifest) -> str:
        if not skill.entrypoint:
            raise AppError(400, "SKILL_NOT_EXECUTABLE", "该 Skill 仅提供提示词，不能直接执行")
        path = (skill.path / skill.entrypoint).resolve()
        if skill.path.resolve() not in path.parents or not path.is_file():
            raise AppError(400, "SKILL_ENTRYPOINT_INVALID", "Skill 入口文件不存在或越出 Skill 目录")
        if path.suffix != ".py":
            raise AppError(400, "SKILL_ENTRYPOINT_UNSUPPORTED", "当前仅支持 Python Skill 入口")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _load_manifest(path: Path) -> SkillManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        name = str(data.get("name", ""))
        if not _NAME_RE.fullmatch(name):
            raise ValueError("name must match ^[a-z][a-z0-9-]{1,79}$")
        display_name = str(data.get("display_name", "")).strip()
        description = str(data.get("description", "")).strip()
        version = str(data.get("version", "")).strip()
        if not display_name or not description or not version:
            raise ValueError("display_name, description and version are required")
        skill_dir = path.parent.resolve()
        instructions_file = str(data.get("instructions", "SKILL.md"))
        instructions_path = (skill_dir / instructions_file).resolve()
        if skill_dir not in instructions_path.parents or not instructions_path.is_file():
            raise ValueError("instructions file is missing or outside skill directory")
        instructions = instructions_path.read_text(encoding="utf-8")
        if len(instructions) > 100_000:
            raise ValueError("instructions exceed 100KB")
        entrypoint = data.get("entrypoint")
        if entrypoint:
            entrypoint_path = (skill_dir / str(entrypoint)).resolve()
            if skill_dir not in entrypoint_path.parents or not entrypoint_path.is_file():
                raise ValueError("entrypoint is missing or outside skill directory")
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        digest.update(instructions.encode())
        if entrypoint:
            digest.update((skill_dir / str(entrypoint)).read_bytes())
        return SkillManifest(
            name=name,
            display_name=display_name,
            version=version,
            description=description,
            entrypoint=str(entrypoint) if entrypoint else None,
            instructions=instructions,
            agent_types=tuple(str(item) for item in data.get("agent_types", [])),
            tags=tuple(str(item) for item in data.get("tags", [])),
            input_schema=data.get("input_schema", {}),
            path=skill_dir,
            checksum=digest.hexdigest(),
        )


skill_registry = SkillRegistry()
