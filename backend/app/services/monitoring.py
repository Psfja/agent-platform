import psutil
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import AgentBuild, ApplicationDeployment, Project, QueuedJob, Task

cpu = Gauge("agent_platform_cpu_percent", "Host CPU utilization")
memory = Gauge("agent_platform_memory_percent", "Host memory utilization")
disk = Gauge("agent_platform_disk_percent", "Host disk utilization")
projects = Gauge("agent_platform_projects_total", "Projects by status", ["status"])
tasks = Gauge("agent_platform_tasks_total", "Tasks by status", ["status"])
builds = Gauge("agent_platform_agent_builds_total", "Agent builds by status", ["status"])
deployments = Gauge("agent_platform_deployments_total", "Deployments by status", ["status"])
queue_jobs = Gauge("agent_platform_queue_jobs_total", "Persistent jobs by status", ["status"])


def prometheus_payload() -> bytes:
    cpu.set(psutil.cpu_percent(interval=0.02)); memory.set(psutil.virtual_memory().percent); disk.set(psutil.disk_usage('/').percent)
    with SessionLocal() as db:
        for model, metric in [(Project, projects), (Task, tasks), (AgentBuild, builds), (ApplicationDeployment, deployments), (QueuedJob, queue_jobs)]:
            rows = db.execute(select(model.status, func.count()).group_by(model.status)).all()
            for status, count in rows: metric.labels(status=status).set(count)
    return generate_latest()
