from __future__ import annotations

import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import QueuedJob, uuid_str


class PersistentTaskQueue:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session_factory = SessionLocal
        self.fallback_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="queue-fallback")
        self._redis: Redis | None = None
        self._available: bool | None = None

    @property
    def key(self) -> str:
        return f"{self.settings.queue_name}:jobs"

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=2)
        return self._redis

    @property
    def available(self) -> bool:
        try:
            self.redis.ping()
            self._available = True
        except RedisError:
            self._available = False
        return bool(self._available)

    def enqueue(self, job_type: str, payload: dict, fallback: Callable[[], None] | None = None, priority: int = 5) -> str:
        with self.session_factory() as db:
            job = QueuedJob(id=f"job-{uuid_str()}", job_type=job_type, payload=payload, priority=priority, status="queued")
            db.add(job); db.commit()
            job_id = job.id
        if self.available:
            self.redis.lpush(self.key, job_id)
        elif self.settings.queue_fallback_threads and fallback:
            self.fallback_executor.submit(self._run_fallback, job_id, fallback)
        return job_id

    def _run_fallback(self, job_id: str, handler: Callable[[], None]) -> None:
        worker = f"fallback:{os.getpid()}:{threading.get_ident()}"
        if not self.claim(job_id, worker):
            return
        try:
            handler()
            self.complete(job_id)
        except Exception as exc:
            self.fail(job_id, str(exc))

    def claim(self, job_id: str, worker_id: str) -> bool:
        with self.session_factory() as db:
            job = db.get(QueuedJob, job_id)
            available_at = job.available_at.replace(tzinfo=timezone.utc) if job and job.available_at.tzinfo is None else (job.available_at if job else None)
            if not job or job.status != "queued" or available_at > datetime.now(timezone.utc):
                return False
            job.status = "running"; job.worker_id = worker_id; job.attempts += 1
            job.started_at = job.started_at or datetime.now(timezone.utc); job.heartbeat_at = datetime.now(timezone.utc)
            db.commit(); return True

    def heartbeat(self, job_id: str) -> None:
        with self.session_factory() as db:
            job = db.get(QueuedJob, job_id)
            if job and job.status == "running":
                job.heartbeat_at = datetime.now(timezone.utc); db.commit()

    def complete(self, job_id: str) -> None:
        with self.session_factory() as db:
            job = db.get(QueuedJob, job_id)
            if job:
                job.status = "completed"; job.finished_at = datetime.now(timezone.utc); job.heartbeat_at = datetime.now(timezone.utc); db.commit()

    def fail(self, job_id: str, error: str) -> None:
        with self.session_factory() as db:
            job = db.get(QueuedJob, job_id)
            if not job:
                return
            job.error_message = error[:8000]
            if job.attempts < job.max_attempts and self.available:
                job.status = "queued"; job.available_at = datetime.now(timezone.utc); job.worker_id = None
                db.commit(); time.sleep(min(10, 2 ** job.attempts)); self.redis.lpush(self.key, job.id)
            else:
                job.status = "failed"; job.finished_at = datetime.now(timezone.utc); db.commit()

    def requeue_orphans(self, stale_seconds: int = 90) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
        with self.session_factory() as db:
            jobs = db.scalars(select(QueuedJob).where(QueuedJob.status == "running", QueuedJob.heartbeat_at < cutoff)).all()
            for job in jobs:
                job.status = "queued"; job.worker_id = None; job.error_message = "Worker heartbeat expired; job requeued"
            db.commit()
        if self.available:
            for job in jobs:
                self.redis.lpush(self.key, job.id)
        return len(jobs)

    def status(self) -> dict:
        with self.session_factory() as db:
            counts = dict(db.execute(select(QueuedJob.status, func.count(QueuedJob.id)).group_by(QueuedJob.status)).all())
        return {"redisAvailable": self.available, "redisUrl": self._safe_redis_url(), "queueName": self.settings.queue_name, "fallbackThreads": self.settings.queue_fallback_threads, "counts": counts}

    def _safe_redis_url(self) -> str:
        value = self.settings.redis_url
        if "@" in value:
            return value.split("://", 1)[0] + "://***@" + value.split("@", 1)[1]
        return value


persistent_queue = PersistentTaskQueue()
