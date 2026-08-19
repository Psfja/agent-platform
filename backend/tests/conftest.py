from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.agent_builder import agent_build_runner
from app.services.application_deployer import application_deployment_runner
from app.services.seed import seed_demo_data
from app.services.task_queue import persistent_queue


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        seed_demo_data(db)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    original_session_factory = agent_build_runner.session_factory
    original_deployment_session_factory = application_deployment_runner.session_factory
    original_queue_session_factory = persistent_queue.session_factory
    agent_build_runner.session_factory = TestingSession
    application_deployment_runner.session_factory = TestingSession
    persistent_queue.session_factory = TestingSession
    with TestClient(app) as test_client:
        login = test_client.post("/api/v1/auth/login", json={"email": "lin.jia@company.com", "password": "Agent@2026"})
        assert login.status_code == 200, login.text
        test_client.headers.update({"Authorization": f"Bearer {login.json()['accessToken']}"})
        yield test_client
    agent_build_runner.session_factory = original_session_factory
    application_deployment_runner.session_factory = original_deployment_session_factory
    persistent_queue.session_factory = original_queue_session_factory
    app.dependency_overrides.clear()
    engine.dispose()
