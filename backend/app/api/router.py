from fastapi import APIRouter, Depends

from app.api import agent_builds, agent_config, admin_users, application_deployments, artifacts, auth, content, conversations, events, iterations, members, operations, projects, queue, runtime, tasks
from app.core.auth import enforce_project_access

api_router = APIRouter()
api_router.include_router(auth.router)

protected_router = APIRouter(dependencies=[Depends(enforce_project_access)])
protected_router.include_router(projects.router)
protected_router.include_router(members.router)
protected_router.include_router(content.router)
protected_router.include_router(agent_builds.router)
protected_router.include_router(application_deployments.router)
protected_router.include_router(tasks.router)
protected_router.include_router(iterations.router)
protected_router.include_router(artifacts.router)
protected_router.include_router(runtime.router)
protected_router.include_router(conversations.router)
protected_router.include_router(queue.router)
protected_router.include_router(agent_config.router)
protected_router.include_router(admin_users.router)
protected_router.include_router(operations.router)
protected_router.include_router(events.router)

api_router.include_router(protected_router)
