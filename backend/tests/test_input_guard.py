import hashlib

import pytest
from sqlalchemy import func, select

from app import database
from app.database import Provider, ResearchRun, Workspace


@pytest.mark.parametrize("prompt", ["hi", " HELLO! ", "hey there", "thanks", "   "])
def test_greetings_do_not_create_workspaces_or_research(client, prompt):
    response = client.post("/api/v1/chats", json={"prompt": prompt})

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Enter a provider name or website, such as Slack or linear.app."
    )
    assert client.get("/api/v1/chats").json() == []
    with database.SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Workspace)) == 0
        assert session.scalar(select(func.count()).select_from(ResearchRun)) == 0
        assert session.scalar(select(func.count()).select_from(Provider)) == 3


@pytest.mark.parametrize("prompt", ["Linear", "linear.app", "X", "HiBob", "hi.com"])
def test_unknown_and_short_provider_names_can_still_be_researched(client, prompt):
    response = client.post("/api/v1/chats", json={"prompt": prompt})

    assert response.status_code == 201
    workspace = response.json()
    assert workspace["research_needed"] is True
    assert workspace["use_case"] == prompt


def test_retry_of_legacy_greeting_workspace_does_not_start_research(client):
    client.get("/api/v1/chats")
    owner = hashlib.sha256(client.cookies["copilot_session"].encode()).hexdigest()
    with database.SessionLocal() as session:
        provider = Provider(
            name="hi",
            slug="research-legacy-greeting",
            website_url="",
            official_domain="",
            aliases=[],
        )
        session.add(provider)
        session.flush()
        workspace = Workspace(
            owner=owner,
            provider_id=provider.id,
            title="hi integration",
            use_case="hi",
            status="research_failed",
        )
        session.add(workspace)
        session.commit()
        workspace_id = workspace.id

    response = client.post(f"/api/v1/chats/{workspace_id}/research")

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Enter a provider name or website, such as Slack or linear.app."
    )
    with database.SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(ResearchRun)) == 0
        assert session.get(Workspace, workspace_id).status == "research_failed"
