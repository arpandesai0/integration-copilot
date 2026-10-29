"""Regression checks for private state, bounded context, and evidence boundaries."""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import database
from app.agents import workflows
from app.database import (
    ConversationThread,
    GuideStep,
    GuideVersion,
    Message,
    ResearchEvent,
    ResearchRun,
    Workspace,
    now,
)
from app.schemas import Guide, GuideDraft
from app.seeds.guides import seed_guide
from app.services.core import context_package, persist_guide


def workspace(client, prompt="Slack"):
    response = client.post("/api/v1/workspaces", json={"prompt": prompt})
    assert response.status_code == 201, response.text
    return response.json()


def step_thread(client, w, step):
    response = client.post(
        f"/api/v1/workspaces/{w['id']}/threads",
        json={
            "type": "step",
            "step_id": step["id"],
            "parent_thread_id": w["main_thread_id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_other_session_cannot_read_or_mutate_private_workspace(client):
    w = workspace(client)
    base = f"/api/v1/workspaces/{w['id']}"
    guide = client.get(base + "/guide").json()
    step = guide["steps"][0]
    thread = step_thread(client, w, step)
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=w["id"], status="failed")
        db.add(run)
        db.commit()
        run_id = run.id
    client.cookies.clear()

    assert client.get(base).status_code == 404
    assert client.get(base + "/guide").status_code == 404
    assert client.get(base + "/threads").status_code == 404
    assert client.get(f"/api/v1/threads/{thread['id']}/messages").status_code == 404
    assert (
        client.post(
            f"/api/v1/threads/{thread['id']}/messages", json={"content": "attack"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            base + f"/steps/{step['id']}", json={"status": "completed"}
        ).status_code
        == 404
    )
    assert client.post(base + "/threads", json={"type": "main"}).status_code == 404
    assert client.post(base + "/research").status_code == 404
    assert client.get(f"/api/v1/research-runs/{run_id}/events").status_code == 404
    assert client.get("/api/v1/workspaces").json() == []
    assert client.get(f"/api/v1/guides/{guide['share_slug']}").status_code == 200


def test_unknown_provider_search_does_not_expose_another_sessions_request(client):
    secret_request = "Confidential Acme payroll integration for acquisition Orion"
    workspace(client, secret_request)
    client.cookies.clear()
    response = client.get("/api/v1/providers", params={"q": "Acme"})
    assert response.status_code == 200
    assert secret_request not in response.text
    assert "acquisition Orion" not in response.text


def test_step_context_keeps_latest_messages_when_history_exceeds_budget(client):
    w = workspace(client)
    guide = client.get(f"/api/v1/workspaces/{w['id']}/guide").json()
    thread = step_thread(client, w, guide["steps"][0])
    with database.SessionLocal() as db:
        timestamp = now()
        for index in range(55):
            db.add(
                Message(
                    thread_id=thread["id"],
                    role="user",
                    content=f"question-{index}",
                    created_at=timestamp + timedelta(seconds=index),
                )
            )
        db.commit()
        context = context_package(db, db.get(ConversationThread, thread["id"]))
    history = context["step_thread_messages"]
    assert len(history) <= 20
    assert history[-1]["content"] == "question-54"
    assert "question-0" not in [message["content"] for message in history]


def test_chat_context_replaces_grounding_redirects_with_verified_destinations(client):
    w = workspace(client)
    guide = client.get(f"/api/v1/workspaces/{w['id']}/guide").json()
    redirect = (
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/opaque"
    )
    unresolved_redirect = (
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/missing"
    )
    resolved = "https://api.slack.com/authentication/oauth-v2#:~:text=OAuth"
    with database.SessionLocal() as db:
        workspace_row = db.get(Workspace, w["id"])
        guide_version = db.get(GuideVersion, workspace_row.active_guide_version_id)
        sources = [dict(source) for source in guide_version.data["sources"]]
        resolved_source = sources[0]
        sources[0] = {
            **resolved_source,
            "url": redirect,
            "text_fragment_url": resolved,
            "excerpt_verified": True,
        }
        unresolved_source = sources[1]
        sources[1] = {
            **unresolved_source,
            "url": unresolved_redirect,
            "text_fragment_url": None,
            "step_text_fragment_urls": {},
            "excerpt_verified": False,
        }
        guide_version.data = {**guide_version.data, "sources": sources}
        db.add(
            Message(
                thread_id=w["main_thread_id"],
                role="assistant",
                content=f"See [Slack]({redirect}) and {unresolved_redirect}",
            )
        )
        db.commit()
        main_context = context_package(
            db, db.get(ConversationThread, w["main_thread_id"])
        )

    serialized = json.dumps(main_context)
    assert "vertexaisearch.cloud.google.com" not in serialized
    assert resolved in serialized
    assert resolved_source["id"] in {
        source["id"] for source in main_context["guide"]["sources"]
    }
    assert unresolved_source["id"] not in {
        source["id"] for source in main_context["guide"]["sources"]
    }
    assert resolved in main_context["main_thread_messages"][-1]["content"]
    assert "[unresolved grounding source]" in main_context["main_thread_messages"][-1][
        "content"
    ]

    target_step = next(
        step
        for step in guide["steps"]
        if resolved_source["id"] in step["source_ids"]
    )
    thread = step_thread(client, w, target_step)
    with database.SessionLocal() as db:
        db.add(
            Message(
                thread_id=thread["id"],
                role="user",
                content=f"What does {redirect} say?",
            )
        )
        db.commit()
        step_context = context_package(
            db, db.get(ConversationThread, thread["id"])
        )
    assert "vertexaisearch.cloud.google.com" not in json.dumps(step_context)
    assert step_context["relevant_sources"][0]["url"] == resolved
    assert resolved in step_context["step_thread_messages"][-1]["content"]


def test_public_guide_excludes_private_notes_messages_and_session_hash(client):
    w = workspace(client)
    base = f"/api/v1/workspaces/{w['id']}"
    guide = client.get(base + "/guide").json()
    thread = step_thread(client, w, guide["steps"][0])
    with database.SessionLocal() as db:
        owner = db.get(Workspace, w["id"]).owner
        db.add(
            Message(
                thread_id=thread["id"], role="user", content="private message sentinel"
            )
        )
        db.commit()
    response = client.post(
        base + f"/steps/{guide['steps'][0]['id']}/notes",
        json={
            "content": "private note sentinel",
            "confirmed": True,
            "thread_id": thread["id"],
        },
    )
    assert response.status_code == 201
    public = client.get(f"/api/v1/guides/{guide['share_slug']}")
    assert public.status_code == 200
    for private in (
        owner,
        "private message sentinel",
        "private note sentinel",
        thread["id"],
        w["main_thread_id"],
    ):
        assert private not in public.text
    assert all("notes" not in step for step in public.json()["steps"])


def test_refresh_retains_historical_discussion_with_original_step_context(client):
    w = workspace(client)
    old_guide = client.get(f"/api/v1/workspaces/{w['id']}/guide").json()
    thread = step_thread(client, w, old_guide["steps"][0])
    with database.SessionLocal() as db:
        old_step = db.get(GuideStep, old_guide["steps"][0]["id"])
        old_step.status = "completed"
        db.add(
            Message(
                thread_id=thread["id"], role="user", content="historical discussion"
            )
        )
        db.commit()
        new_guide = seed_guide("slack")
        new_guide.steps[0].description = "Updated registration description"
        persist_guide(db, db.get(Workspace, w["id"]), new_guide)
        context = context_package(db, db.get(ConversationThread, thread["id"]))
    current = client.get(f"/api/v1/workspaces/{w['id']}/guide").json()
    assert current["version_number"] == 2
    assert current["steps"][0]["status"] == "completed"
    assert context["guide_version"] == old_guide["id"]
    assert (
        context["selected_step"]["description"] == old_guide["steps"][0]["description"]
    )
    assert context["step_thread_messages"][0]["content"] == "historical discussion"


@pytest.mark.parametrize("mutation", ["missing-source", "duplicate-source", "tested"])
def test_research_schema_rejects_unsupported_evidence_labels(mutation):
    data = seed_guide("slack").model_dump(mode="json")
    data["citations"] = []
    for citation_step in data["steps"]:
        citation_step["citations"] = []
    if mutation == "missing-source":
        data["steps"][0]["source_ids"] = ["invented-citation"]
    elif mutation == "duplicate-source":
        data["sources"].append(data["sources"][0])
    else:
        data["steps"][0]["verification_status"] = "tested"
    with pytest.raises(ValidationError):
        Guide.model_validate(data)


def test_research_reconnection_returns_only_events_after_cursor(client):
    w = workspace(client)
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=w["id"], status="completed")
        db.add(run)
        db.flush()
        start = ResearchEvent(
            research_run_id=run.id,
            event_type="research_started",
            payload={"message": "begin"},
        )
        done = ResearchEvent(
            research_run_id=run.id,
            event_type="guide_ready",
            payload={"message": "ready"},
        )
        db.add_all([start, done])
        db.commit()
        run_id, cursor = run.id, start.id
    response = client.get(
        f"/api/v1/research-runs/{run_id}/events", headers={"Last-Event-ID": str(cursor)}
    )
    assert response.status_code == 200
    assert "guide_ready" in response.text
    assert "research_started" not in response.text
    assert (
        client.get(
            f"/api/v1/research-runs/{run_id}/events",
            headers={"Last-Event-ID": "invalid"},
        ).status_code
        == 400
    )


def test_cross_origin_private_mutation_is_rejected(client):
    response = client.post(
        "/api/v1/workspaces",
        json={"prompt": "Slack"},
        headers={"Origin": "https://untrusted.example"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "result_kind", ["supported", "unsupported", "tampered-source", "unknown-source"]
)
def test_research_pipeline_validates_grounded_sources_before_persistence(
    client, monkeypatch, result_kind
):
    """Mocked SDK contract check; this is not a live Vertex/provider verification."""
    w = workspace(client, "Example Research Provider")
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=w["id"])
        db.add(run)
        db.commit()
        run_id = run.id
    calls = []
    official_url = "https://docs.example.com/oauth"

    async def generate_content(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            web = SimpleNamespace(uri=official_url, title="Example OAuth documentation")
            metadata = SimpleNamespace(grounding_chunks=[SimpleNamespace(web=web)])
            return SimpleNamespace(
                text="Provider authorization endpoint https://example.com/authorize and token endpoint https://example.com/token.",
                candidates=[SimpleNamespace(grounding_metadata=metadata)],
            )
        payload = json.loads(kwargs["contents"])
        data = seed_guide("slack").model_dump(mode="json")
        data["citations"] = []
        for citation_step in data["steps"]:
            citation_step["citations"] = []
        data["provider_name"] = "Example Research Provider"
        data["provider_website"] = "https://example.com"
        data["oauth_evidence"] = {
            "source_id": "source-1",
            "authorization_url": "https://example.com/authorize",
            "token_url": "https://example.com/token",
        }
        data["sources"] = payload["sources"]
        data["sources"][0]["claims"] = [
            "The provider documents its authorization mechanism."
        ]
        for step in data["steps"]:
            step["source_ids"] = ["source-1"]
        if result_kind == "unsupported":
            data["oauth_support_status"] = "unsupported"
            data["steps"] = []
            data["recommended_auth_path"] = (
                "Use the provider's documented non-OAuth mechanism."
            )
        elif result_kind == "tampered-source":
            data["sources"][0]["url"] = "https://invented.example.com/approval"
        elif result_kind == "unknown-source":
            data["sources"][0]["id"] = "invented-source"
            for step in data["steps"]:
                step["source_ids"] = ["invented-source"]
        return SimpleNamespace(text=json.dumps(data))

    fake_client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    monkeypatch.setattr(workflows, "client", lambda: fake_client)
    asyncio.run(workflows.research(run_id))
    assert len(calls) == 2
    assert calls[0]["config"].tools
    assert calls[1]["config"].response_schema is GuideDraft
    catalog = json.loads(calls[1]["contents"])["sources"]
    assert all(set(source) == {"id", "title"} for source in catalog)
    reference_schema = GuideDraft.model_json_schema()["$defs"]["SourceReference"]
    assert set(reference_schema["properties"]) == {"id", "claims", "excerpt"}
    with database.SessionLocal() as db:
        status = db.get(ResearchRun, run_id).status
    events = client.get(f"/api/v1/research-runs/{run_id}/events").text
    response = client.get(f"/api/v1/workspaces/{w['id']}/guide")
    if result_kind in {"tampered-source", "unknown-source"}:
        assert status == "failed"
        assert "research_failed" in events
        assert "guide_ready" not in events
        assert response.status_code == 404
    else:
        assert status == "completed"
        assert "guide_ready" in events
        assert response.status_code == 200
        guide = response.json()
        assert guide["sources"][0]["url"] == official_url
        assert guide["oauth_support_status"] == result_kind
        assert bool(guide["steps"]) == (result_kind == "supported")
