import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app import database, main, api
from app.agents import workflows


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(api, "SessionLocal", sessions)
    monkeypatch.setattr(workflows, "SessionLocal", sessions)
    monkeypatch.setattr(workflows.settings, "gemini_model", "")
    # Unit research tests stub routing independently of their grounded SDK mocks.
    # Scope-specific tests override this stub explicitly.
    from app.services.scope_triage import ScopeDecision
    async def scoped(request, timeout_seconds=12):
        return ScopeDecision(needs_clarification=False, focused_request=request["request"])
    monkeypatch.setattr(workflows, "assess_scope", scoped)

    def db():
        with sessions() as session:
            yield session

    main.app.dependency_overrides[database.get_db] = db
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
    engine.dispose()
