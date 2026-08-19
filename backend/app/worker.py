from __future__ import annotations

import os
import socket
import threading
import time

from app.database import create_schema
from app.models import QueuedJob
from app.services.agent_builder import agent_build_runner
from app.services.application_deployer import application_deployment_runner
from app.services.task_queue import persistent_queue


def handle(job: QueuedJob) -> None:
    if job.job_type == "agent_build":
        agent_build_runner.run_sync(job.payload["build_id"])
    elif job.job_type == "application_deployment":
        application_deployment_runner.run_sync(job.payload["deployment_id"])
    else:
        raise ValueError(f"Unknown job type: {job.job_type}")


def heartbeat(job_id: str, stop: threading.Event) -> None:
    while not stop.wait(15):
        persistent_queue.heartbeat(job_id)


def main() -> None:
    create_schema()
    if not persistent_queue.available:
        raise SystemExit("Redis is not available; worker cannot start")
    persistent_queue.requeue_orphans()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    print(f"Worker {worker_id} listening on {persistent_queue.key}", flush=True)
    while True:
        item = persistent_queue.redis.brpop(persistent_queue.key, timeout=10)
        if not item:
            continue
        _, job_id = item
        if not persistent_queue.claim(job_id, worker_id):
            continue
        with persistent_queue.session_factory() as db:
            job = db.get(QueuedJob, job_id)
            if not job:
                continue
            stop = threading.Event()
            thread = threading.Thread(target=heartbeat, args=(job_id, stop), daemon=True)
            thread.start()
            try:
                handle(job)
                persistent_queue.complete(job_id)
            except Exception as exc:
                persistent_queue.fail(job_id, str(exc))
            finally:
                stop.set(); thread.join(timeout=1)


if __name__ == "__main__":
    main()
