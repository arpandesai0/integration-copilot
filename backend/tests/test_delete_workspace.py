import pytest
from sqlalchemy import func, select, text
from app import database
from app.database import (
    Workspace,
    Provider,
    ConversationThread,
    Message,
    StepNote,
    ResearchRun,
    ResearchEvent,
    ClaimEvidence,
    Source,
    GuideStep,
    GuideVersion,
)
from app.seeds.guides import seed_guide
from app.services.core import persist_guide


def create_workspace(client, prompt="Slack"):
    response = client.post("/api/v1/chats", json={"prompt": prompt})
    assert response.status_code == 201
    return response.json()


def test_delete_purges_nested_chat_and_revokes_share_preserving_other_workspace(client):
    # Enforce actual foreign-key restrictions on the isolated test connection.
    with database.SessionLocal() as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()
    workspace = create_workspace(client)
    other = create_workspace(client)
    base = f"/api/v1/chats/{workspace['id']}"
    guide = client.get(base + "/guide").json()
    thread = client.post(
        base + "/threads",
        json={
            "type": "step",
            "step_id": guide["steps"][0]["id"],
            "parent_thread_id": workspace["main_thread_id"],
        },
    ).json()
    with database.SessionLocal() as db:
        db.add(
            Message(thread_id=thread["id"], role="assistant", content="Private answer")
        )
        db.add(
            StepNote(
                step_id=guide["steps"][0]["id"],
                thread_id=thread["id"],
                content="Private note",
            )
        )
        run = ResearchRun(workspace_id=workspace["id"], status="completed")
        db.add(run)
        db.flush()
        db.add(
            ResearchEvent(research_run_id=run.id, event_type="guide_ready", payload={})
        )
        db.commit()
        persist_guide(db, db.get(Workspace, workspace["id"]), seed_guide("slack"))
        versions = list(
            db.scalars(
                select(GuideVersion.id).where(
                    GuideVersion.workspace_id == workspace["id"]
                )
            )
        )
        run_id = run.id
    public = client.get("/api/v1/guides/" + guide["share_slug"])
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-store"
    response = client.delete(base)
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True, "id": workspace["id"]}
    assert client.get(base).status_code == 404
    assert client.get("/api/v1/guides/" + guide["share_slug"]).status_code == 404
    assert client.get(f"/api/v1/threads/{thread['id']}/messages").status_code == 404
    assert client.get(f"/api/v1/research-runs/{run_id}/events").status_code == 404
    assert client.delete(base).status_code == 404
    assert [w["id"] for w in client.get("/api/v1/chats").json()] == [other["id"]]
    assert client.get(f"/api/v1/chats/{other['id']}/guide").status_code == 200
    with database.SessionLocal() as db:
        assert db.get(Provider, workspace["provider"]["id"]) is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(ConversationThread)
                .where(ConversationThread.workspace_id == workspace["id"])
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Message)
                .where(
                    Message.thread_id.in_([workspace["main_thread_id"], thread["id"]])
                )
            )
            == 0
        )
        assert db.scalar(select(func.count()).select_from(StepNote)) == 0
        assert db.get(ResearchRun, run_id) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(ResearchEvent)
                .where(ResearchEvent.research_run_id == run_id)
            )
            == 0
        )
        for model in [ClaimEvidence, Source, GuideStep]:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.guide_version_id.in_(versions))
                )
                == 0
            )
        assert all(db.get(GuideVersion, version) is None for version in versions)


def test_delete_requires_ownership(client):
    workspace = create_workspace(client)
    client.cookies.clear()
    assert client.delete(f"/api/v1/chats/{workspace['id']}").status_code == 404
    with database.SessionLocal() as db:
        assert db.get(Workspace, workspace["id"]) is not None


@pytest.mark.parametrize("active", ["research", "response"])
def test_delete_waits_for_active_generation(client, active):
    workspace = create_workspace(client)
    with database.SessionLocal() as db:
        if active == "research":
            db.add(ResearchRun(workspace_id=workspace["id"], status="running"))
        else:
            db.add(
                Message(
                    thread_id=workspace["main_thread_id"],
                    role="assistant",
                    content="",
                    status="streaming",
                )
            )
        db.commit()
    response = client.delete(f"/api/v1/chats/{workspace['id']}")
    assert response.status_code == 409
    assert "finish" in response.json()["detail"]
    assert client.get(f"/api/v1/chats/{workspace['id']}/guide").status_code == 200


def test_delete_browser_cors_and_origin(client):
    workspace = create_workspace(client)
    path = f"/api/v1/chats/{workspace['id']}"
    response = client.options(
        path,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert (
        client.delete(path, headers={"Origin": "https://attacker.example"}).status_code
        == 403
    )
    assert (
        client.delete(path, headers={"Origin": "http://localhost:3000"}).status_code
        == 200
    )
