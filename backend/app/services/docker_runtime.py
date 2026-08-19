from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass(slots=True)
class DockerCommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int


class DockerRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def available(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            return self.run(["version", "--format", "{{.Server.Version}}"], timeout=10).exit_code == 0
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        version = ""
        if self.available:
            version = self.run(["version", "--format", "{{.Server.Version}}"], timeout=10).stdout.strip()
        return {
            "docker_available": bool(version),
            "docker_version": version,
            "ready": bool(version),
            "message": f"Docker {version} 可用，可构建并运行生成应用。" if version else "未检测到可用 Docker daemon；源码生成不受影响，但应用部署功能不可用。",
        }

    def write_deployment_files(self, workspace: Path) -> None:
        backend = workspace / "backend"
        frontend = workspace / "frontend"
        if not (backend / "app" / "main.py").is_file() or not (frontend / "package.json").is_file():
            raise RuntimeError("generated workspace is missing backend or frontend sources")
        (backend / "Dockerfile.agent").write_text(BACKEND_DOCKERFILE, encoding="utf-8")
        (frontend / "Dockerfile.agent").write_text(FRONTEND_DOCKERFILE, encoding="utf-8")
        (frontend / "nginx.agent.conf").write_text(NGINX_CONFIG, encoding="utf-8")
        (backend / ".dockerignore").write_text("__pycache__\n.pytest_cache\ncoverage.json\n*.log\n", encoding="utf-8")
        (frontend / ".dockerignore").write_text("node_modules\ndist\n*.log\n", encoding="utf-8")

    def build_image(self, context: Path, dockerfile: str, tag: str, timeout: int = 600) -> DockerCommandResult:
        return self.require_success(["build", "--pull=false", "-f", dockerfile, "-t", tag, "."], cwd=context, timeout=timeout)

    def create_network(self, name: str) -> DockerCommandResult:
        return self.require_success(["network", "create", "--label", "agent-platform.managed=true", name], timeout=30)

    def run_backend(self, name: str, image: str, network: str, database_url: str | None = None) -> DockerCommandResult:
        args = [
            "run", "-d", "--name", name, "--network", network, "--network-alias", "backend",
            "--label", "agent-platform.managed=true", "--restart", "unless-stopped",
            "--memory", f"{self.settings.deployment_backend_memory_mb}m", "--cpus", "1",
            "--pids-limit", "128", "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        ]
        if database_url:
            args.extend(["-e", f"DATABASE_URL={database_url}"])
        args.append(image)
        return self.require_success(args, timeout=60)

    def run_frontend(self, name: str, image: str, network: str) -> DockerCommandResult:
        return self.require_success([
            "run", "-d", "--name", name, "--network", network,
            "--label", "agent-platform.managed=true", "--restart", "unless-stopped",
            "--memory", f"{self.settings.deployment_frontend_memory_mb}m", "--cpus", "0.5",
            "--pids-limit", "64", "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--read-only", "--tmpfs", "/var/cache/nginx:rw,noexec,nosuid,size=32m",
            "--tmpfs", "/var/run:rw,noexec,nosuid,size=4m", "-p", "127.0.0.1::80", image,
        ], timeout=60)

    def host_port(self, container: str) -> int:
        output = self.require_success(["port", container, "80/tcp"], timeout=20).stdout.strip().splitlines()
        if not output:
            raise RuntimeError("Docker did not publish a frontend port")
        match = re.search(r":(\d+)$", output[0])
        if not match:
            raise RuntimeError(f"Cannot parse Docker port: {output[0]}")
        return int(match.group(1))

    def smoke_test(self, deploy_url: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.settings.deployment_smoke_timeout_seconds
        attempts: list[dict[str, Any]] = []
        last_error = ""
        while time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=5, follow_redirects=True) as client:
                    root = client.get(deploy_url)
                    health = client.get(f"{deploy_url}/health")
                attempt = {"rootStatus": root.status_code, "healthStatus": health.status_code}
                attempts.append(attempt)
                if root.status_code < 400 and health.status_code < 400:
                    return {"passed": True, "attempts": attempts, "rootStatus": root.status_code, "healthStatus": health.status_code}
                last_error = f"root={root.status_code}, health={health.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
                attempts.append({"error": last_error})
            time.sleep(2)
        return {"passed": False, "attempts": attempts[-10:], "error": last_error or "smoke test timeout"}

    def logs(self, container: str, tail: int = 200) -> str:
        result = self.run(["logs", "--tail", str(tail), container], timeout=20)
        return (result.stdout + "\n" + result.stderr).strip()

    def stop_remove(self, container: str) -> None:
        if container:
            self.run(["rm", "-f", container], timeout=30)

    def remove_network(self, network: str) -> None:
        if network:
            self.run(["network", "rm", network], timeout=30)

    def run(self, args: list[str], cwd: Path | None = None, timeout: int = 120) -> DockerCommandResult:
        command = ["docker", *args]
        started = time.perf_counter()
        process = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return DockerCommandResult(command, process.returncode, process.stdout[-100_000:], process.stderr[-100_000:], round((time.perf_counter() - started) * 1000))

    def require_success(self, args: list[str], cwd: Path | None = None, timeout: int = 120) -> DockerCommandResult:
        result = self.run(args, cwd, timeout)
        if result.exit_code != 0:
            raise RuntimeError(f"Docker command failed ({result.exit_code}): {result.stderr[-2000:]}")
        return result


BACKEND_DOCKERFILE = """FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
USER 65534:65534
CMD [\"python\", \"-m\", \"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]
"""

FRONTEND_DOCKERFILE = """FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund --ignore-scripts
COPY . .
RUN npm run build
FROM nginx:1.27-alpine
COPY nginx.agent.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
"""

NGINX_CONFIG = """server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location = /health {
        proxy_pass http://backend:8000/health;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
"""


docker_runtime = DockerRuntime()
