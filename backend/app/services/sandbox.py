from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SandboxRun, uuid_str


@dataclass(slots=True)
class ExecutionResult:
    backend: str
    command: list[str]
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    error_message: str
    elapsed_ms: int
    workspace: Path


class SandboxManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.sandbox_data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def docker_available(self) -> bool:
        return bool(shutil.which("docker"))

    @property
    def active_backend(self) -> str:
        if self.settings.sandbox_backend == "docker" and self.docker_available:
            return "docker"
        return "local"

    def status(self) -> dict[str, Any]:
        warnings: list[str] = []
        if self.active_backend == "local":
            warnings.append("本地进程沙箱提供独立工作目录与资源限制，但不具备可靠的文件系统边界或网络隔离；生产环境请使用 Docker。")
        if self.settings.sandbox_backend == "docker" and not self.docker_available:
            warnings.append("未检测到 Docker，已回退到本地进程沙箱。")
        return {
            "configured_backend": self.settings.sandbox_backend,
            "active_backend": self.active_backend,
            "available": True,
            "isolation": "container-network-none" if self.active_backend == "docker" else "process-resource-limits",
            "docker_available": self.docker_available,
            "limits": {
                "timeoutSeconds": self.settings.sandbox_timeout_seconds,
                "memoryMb": self.settings.sandbox_memory_mb,
                "cpuSeconds": self.settings.sandbox_cpu_seconds,
                "outputBytes": self.settings.sandbox_output_limit,
            },
            "warnings": warnings,
        }

    def execute_python(self, run_id: str, code: str, stdin: str = "", timeout_seconds: int | None = None) -> ExecutionResult:
        timeout = min(timeout_seconds or self.settings.sandbox_timeout_seconds, 300)
        workspace = (self.settings.sandbox_data_dir / run_id / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=False)
        source = workspace / "main.py"
        source.write_text(code, encoding="utf-8")
        if self.active_backend == "docker":
            return self._execute_docker(workspace, stdin, timeout)
        return self._execute_local(workspace, stdin, timeout)

    def execute_build_command(self, workspace: Path, command: list[str], timeout_seconds: int | None = None) -> ExecutionResult:
        """Execute a trusted build/test command without a shell in a generated workspace."""
        workspace = workspace.resolve()
        if not workspace.is_dir():
            raise ValueError(f"workspace does not exist: {workspace}")
        if not command:
            raise ValueError("empty command")
        executable = command[0]
        allowed = {sys.executable, "python", "python3", "npm"}
        if executable not in allowed and Path(executable).name not in {"python", "python3", "npm"}:
            raise ValueError(f"build command is not allowed: {executable}")
        if executable in {"python", "python3"}:
            command = [sys.executable, *command[1:]]
        elif executable == "npm":
            npm = shutil.which("npm")
            if not npm:
                raise RuntimeError("npm is not installed")
            command = [npm, *command[1:]]
        timeout = min(timeout_seconds or self.settings.agent_build_timeout_seconds, self.settings.agent_build_timeout_seconds)
        if self.active_backend == "docker":
            container_command = ["python" if Path(command[0]).name in {"python", "python3"} else Path(command[0]).name, *command[1:]]
            install_step = container_command[:2] == ["npm", "install"]
            docker_command = [
                "docker", "run", "--rm", "--network", "bridge" if install_step else "none", "--read-only",
                "--memory", "1024m", "--cpus", "2", "--pids-limit", "128",
                "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
                "--tmpfs", "/tmp:rw,nosuid,size=256m", "-e", "npm_config_cache=/tmp/npm-cache",
                "-v", f"{workspace}:/workspace:rw", "-w", "/workspace",
                self.settings.agent_build_docker_image, *container_command,
            ]
            return self._run_process(docker_command, workspace, "", timeout, backend="docker-build")
        # Full-stack dependency installation requires more memory than a small tool call.
        return self._run_process(command, workspace, "", timeout, backend="local-build", preexec_fn=self._build_resource_limits)

    def _execute_local(self, workspace: Path, stdin: str, timeout: int) -> ExecutionResult:
        command = [sys.executable, "-I", "main.py"]
        return self._run_process(command, workspace, stdin, timeout, backend="local", preexec_fn=self._resource_limits)

    def _execute_docker(self, workspace: Path, stdin: str, timeout: int) -> ExecutionResult:
        command = [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--memory", f"{self.settings.sandbox_memory_mb}m", "--cpus", "1",
            "--pids-limit", "64", "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{workspace}:/workspace:rw", "-w", "/workspace",
            self.settings.sandbox_docker_image, "python", "-I", "main.py",
        ]
        return self._run_process(command, workspace, stdin, timeout, backend="docker")

    def _run_process(self, command: list[str], workspace: Path, stdin: str, timeout: int, backend: str, preexec_fn=None) -> ExecutionResult:
        started = time.perf_counter()
        stdout_path, stderr_path = workspace / "stdout.log", workspace / "stderr.log"
        status, exit_code, error = "running", None, ""
        safe_env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            process = subprocess.Popen(
                command, cwd=workspace, stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file,
                env=safe_env, start_new_session=True, preexec_fn=preexec_fn,
            )
            try:
                process.communicate(stdin.encode("utf-8"), timeout=timeout)
                exit_code = process.returncode
                status = "completed" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                exit_code = process.returncode
                status = "timed_out"
                error = f"Execution exceeded {timeout} seconds"
        stdout = self._read_output(stdout_path)
        stderr = self._read_output(stderr_path)
        if status == "failed" and not error:
            error = f"Process exited with code {exit_code}"
        return ExecutionResult(
            backend=backend, command=command, status=status, exit_code=exit_code,
            stdout=stdout, stderr=stderr, error_message=error,
            elapsed_ms=round((time.perf_counter() - started) * 1000), workspace=workspace,
        )

    def _read_output(self, path: Path) -> str:
        limit = self.settings.sandbox_output_limit
        data = path.read_bytes()[:limit]
        text = data.decode("utf-8", errors="replace")
        if path.stat().st_size > limit:
            text += "\n...[output truncated]"
        return text

    def _build_resource_limits(self) -> None:
        try:
            import resource
            memory = max(self.settings.sandbox_memory_mb, 1024) * 1024 * 1024
            cpu = min(self.settings.agent_build_timeout_seconds, 600)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
        except (ImportError, ValueError, OSError):
            pass

    def _resource_limits(self) -> None:
        try:
            import resource
            memory = self.settings.sandbox_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_CPU, (self.settings.sandbox_cpu_seconds, self.settings.sandbox_cpu_seconds + 1))
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_FSIZE, (self.settings.sandbox_output_limit, self.settings.sandbox_output_limit))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
        except (ImportError, ValueError, OSError):
            pass

    def execute_and_record(
        self, db: Session, project_id: str, code: str, stdin: str = "", task_id: str | None = None,
        skill_name: str | None = None, input_json: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> SandboxRun:
        run = SandboxRun(
            id=f"sandbox-{uuid_str()}", project_id=project_id, task_id=task_id,
            skill_name=skill_name, backend=self.active_backend, language="python",
            status="running", input_json=input_json or {}, started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()
        try:
            result = self.execute_python(run.id, code, stdin, timeout_seconds)
            run.backend = result.backend
            run.command = result.command
            run.status = result.status
            run.exit_code = result.exit_code
            run.stdout = result.stdout
            run.stderr = result.stderr
            run.error_message = result.error_message
            run.workspace_path = str(result.workspace)
            run.resource_usage = {"elapsedMs": result.elapsed_ms}
            if result.stdout.strip():
                try:
                    parsed = json.loads(result.stdout)
                    run.result_json = parsed if isinstance(parsed, dict) else {"value": parsed}
                except json.JSONDecodeError:
                    run.result_json = {}
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.flush()
        return run


sandbox_manager = SandboxManager()
