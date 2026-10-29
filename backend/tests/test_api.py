from app import database, api
from app.database import ConversationThread, Provider
from app.services.core import context_package


def new(client, prompt="Slack"):
    response = client.post("/api/v1/chats", json={"prompt": prompt})
    assert response.status_code == 201, response.text
    return response.json()


def test_resolved_provider_wins_over_stale_provisional_identity(client):
    with database.SessionLocal() as db:
        db.add(
            Provider(
                name="Help me integrate linear.app",
                slug="research-stale-linear",
                website_url="",
                official_domain="",
                aliases=[],
                oauth_support_status="unknown",
            )
        )
        db.add(
            Provider(
                name="Linear",
                slug="resolved-linear-test",
                website_url="https://linear.app/",
                official_domain="linear.app",
                aliases=["linear", "linear.app"],
                oauth_support_status="supported",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/chats", json={"prompt": "Help me integrate linear.app."}
    )
    assert response.status_code == 201, response.text
    assert response.json()["provider"]["name"] == "Linear"


def test_health_and_seed_guides(client):
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/api/v1/providers").json()) == 3
    for name in ["Slack", "GitHub", "Google Drive"]:
        w = new(client, name)
        g = client.get(f"/api/v1/chats/{w['id']}/guide").json()
        assert len(g["steps"]) >= 5 and g["sources"]
        assert g["estimated_setup_minutes"] > 0
        assert g["estimated_approval_days"] > 0
        assert g["setup_confidence"] == "inferred"
        assert g["approval_confidence"] == "inferred"
        assert all(step["estimated_minutes"] > 0 for step in g["steps"])
        assert all(s["verification_status"] == "documented" for s in g["steps"])
        assert all(s["url"].startswith("https://") for s in g["sources"])


def test_step_progress_and_share_no_private_notes(client):
    w = new(client)
    base = f"/api/v1/chats/{w['id']}"
    g = client.get(base + "/guide").json()
    step = g["steps"][0]
    assert (
        client.patch(
            base + "/steps/" + step["id"], json={"status": "completed"}
        ).status_code
        == 200
    )
    assert client.get(base).json()["progress"]["completed"] == 1
    assert (
        client.post(
            base + "/steps/" + step["id"] + "/notes",
            json={"content": "private callback"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            base + "/steps/" + step["id"] + "/notes",
            json={"content": "private callback", "confirmed": True},
        ).status_code
        == 201
    )
    public = client.get("/api/v1/guides/" + g["share_slug"]).json()
    assert "private callback" not in str(public)
    assert public["next_best_action"] == g["steps"][1]["title"]
    assert (
        client.get(base + "/guide").json()["steps"][0]["notes"][0]["content"]
        == "private callback"
    )


def test_independent_threads_and_context(client, monkeypatch):
    async def fake(context, mode):
        yield "Scoped " + mode + " answer"

    monkeypatch.setattr(api, "answer_stream", fake)
    w = new(client)
    base = f"/api/v1/chats/{w['id']}"
    g = client.get(base + "/guide").json()
    ids = []
    for step in g["steps"][:2]:
        r = client.post(
            base + "/threads",
            json={
                "type": "step",
                "step_id": step["id"],
                "parent_thread_id": w["main_thread_id"],
            },
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    for question in ["first", "follow up", "third question"]:
        r = client.post(
            "/api/v1/threads/" + ids[0] + "/messages", json={"content": question}
        )
        assert "message_completed" in r.text
    client.post(
        "/api/v1/threads/" + ids[1] + "/messages",
        json={"content": "other step private question"},
    )
    assert len(client.get("/api/v1/threads/" + ids[0] + "/messages").json()) == 6
    assert (
        len(client.get("/api/v1/threads/" + w["main_thread_id"] + "/messages").json())
        == 1
    )
    with database.SessionLocal() as db:
        context = context_package(db, db.get(ConversationThread, ids[0]))
    assert context["selected_step_id"] == g["steps"][0]["id"]
    assert "other step private question" not in str(context)
    assert "guide" not in context


def test_missing_ai_is_explicit_and_persisted(client):
    w = new(client)
    r = client.post(
        "/api/v1/threads/" + w["main_thread_id"] + "/messages",
        json={"content": "Can I launch?"},
    )
    assert "message_error" in r.text and "message_completed" not in r.text
    messages = client.get("/api/v1/threads/" + w["main_thread_id"] + "/messages").json()
    assert messages[-1]["status"] == "failed"
    assert "Configure GOOGLE_CLOUD_PROJECT" in messages[-1]["content"]


def test_unknown_research_failure_reconnect(client):
    w = new(client, "Help me integrate linear.app")
    assert w["research_needed"] and not w["guide_available"]
    r = client.post(f"/api/v1/chats/{w['id']}/research")
    assert r.status_code == 202
    run = r.json()["id"]
    events = client.get("/api/v1/research-runs/" + run + "/events")
    assert "research_started" in events.text and "research_failed" in events.text
    replay = client.get("/api/v1/research-runs/" + run + "/events")
    assert replay.text == events.text


def test_ambiguous_provider_and_invalid_thread(client):
    assert (
        client.post(
            "/api/v1/chats", json={"prompt": "Slack and GitHub"}
        ).status_code
        == 409
    )
    a = new(client)
    b = new(client, "GitHub")
    g = client.get(f"/api/v1/chats/{a['id']}/guide").json()
    r = client.post(
        f"/api/v1/chats/{a['id']}/threads",
        json={
            "type": "step",
            "step_id": g["steps"][0]["id"],
            "parent_thread_id": b["main_thread_id"],
        },
    )
    assert r.status_code == 422


def test_research_synthesis_persists_returned_sources(client, monkeypatch):
    from types import SimpleNamespace
    from app.agents import workflows
    from app.seeds.guides import seed_guide

    guide = seed_guide("slack").model_dump(mode="json")
    guide["citations"] = []
    for citation_step in guide["steps"]:
        citation_step["citations"] = []
    chunks = [
        SimpleNamespace(web=SimpleNamespace(uri=s["url"], title=s["title"]))
        for s in guide["sources"]
    ]
    for i, s in enumerate(guide["sources"]):
        old = s["id"]
        s["id"] = f"source-{i + 1}"
        for step in guide["steps"]:
            step["source_ids"] = [
                s["id"] if id == old else id for id in step["source_ids"]
            ]

    class Models:
        count = 0

        async def generate_content(self, **kwargs):
            import json

            self.count += 1
            if self.count == 1:
                return SimpleNamespace(
                    text="Documented OAuth research",
                    candidates=[
                        SimpleNamespace(
                            grounding_metadata=SimpleNamespace(grounding_chunks=chunks)
                        )
                    ],
                )
            return SimpleNamespace(text=json.dumps(guide))

    monkeypatch.setattr(
        workflows,
        "client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=Models())),
    )
    w = new(client, "unfamiliar.example")
    run = client.post(f"/api/v1/chats/{w['id']}/research").json()["id"]
    events = client.get("/api/v1/research-runs/" + run + "/events").text
    assert "guide_ready" in events and "research_failed" not in events, events
    g = client.get(f"/api/v1/chats/{w['id']}/guide").json()
    assert g["version_number"] == 1 and len(g["sources"]) == len(guide["sources"])
    assert client.get(f"/api/v1/chats/{w['id']}").json()["guide_available"]


def test_obvious_credentials_are_rejected(client):
    r = client.post(
        "/api/v1/chats",
        json={"prompt": "Slack client_secret=exampleVerySensitiveValue123"},
    )
    assert r.status_code == 422
    assert "Do not submit credentials" in r.text
    assert "exampleVerySensitiveValue123" not in r.text
    # Ordinary troubleshooting about secret configuration remains allowed.
    assert (
        client.post(
            "/api/v1/chats",
            json={"prompt": "Slack: where should I store a client secret?"},
        ).status_code
        == 201
    )


def test_audience_intent_and_capabilities(client):
    for prompt, audience in [
        ("Slack for my personal account", "personal"),
        ("GitHub for our internal organization", "internal_organization"),
        ("Google Drive read-only for external customers", "external_customers"),
    ]:
        w = new(client, prompt)
        assert w["audience"] == audience
        assert w["capabilities"] == prompt
    w = client.post(
        "/api/v1/chats",
        json={
            "prompt": "Slack personal access",
            "audience": "external_customers",
            "capabilities": "Send messages only",
        },
    ).json()
    assert (
        w["audience"] == "external_customers"
        and w["capabilities"] == "Send messages only"
    )


def test_restart_recovers_streaming_message(client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import Message

    w = new(client)
    with database.SessionLocal() as db:
        m = Message(
            thread_id=w["main_thread_id"],
            role="assistant",
            content="Partial answer",
            status="streaming",
        )
        db.add(m)
        db.commit()
        message_id = m.id
    with TestClient(app):
        with database.SessionLocal() as db:
            assert db.get(Message, message_id).status == "incomplete"


def test_freshness_uses_source_verification_date_and_config(client, monkeypatch):
    from datetime import timedelta
    from app.config import settings
    from app.database import GuideVersion, now

    monkeypatch.setattr(settings, "guide_freshness_days", 7)
    w = new(client)
    base = f"/api/v1/chats/{w['id']}"
    with database.SessionLocal() as db:
        g = db.get(GuideVersion, w["active_guide_version_id"])
        g.data = {**g.data, "last_verified_at": (now() - timedelta(days=8)).isoformat()}
        db.commit()
    assert client.get(base).json()["guide_is_stale"] is True
    shared = client.get(base + "/guide").json()
    assert shared["guide_is_stale"] is True and shared["freshness_days"] == 7
    assert (
        client.get("/api/v1/guides/" + shared["share_slug"]).json()["guide_is_stale"]
        is True
    )
    with database.SessionLocal() as db:
        g = db.get(GuideVersion, w["active_guide_version_id"])
        g.data = {**g.data, "last_verified_at": (now() - timedelta(days=6)).isoformat()}
        db.commit()
    assert client.get(base).json()["guide_is_stale"] is False
    assert client.get(base + "/guide").json()["guide_is_stale"] is False


def test_researched_provider_identity_never_publishes_original_prompt(client):
    from app.database import Workspace, Provider
    from app.services.core import persist_guide
    from app.seeds.guides import seed_guide

    private_prompt = "Investigate Acme for our confidential acquisition Orion"
    w = new(client, private_prompt)
    with database.SessionLocal() as db:
        workspace = db.get(Workspace, w["id"])
        persist_guide(db, workspace, seed_guide("slack"))
        provider = db.get(Provider, workspace.provider_id)
        assert private_prompt not in str(provider.aliases)
        assert provider.official_domain == "slack.com"
        assert provider.slug.startswith("resolved-slack-")
    guide = client.get(f"/api/v1/chats/{w['id']}/guide").json()
    client.cookies.clear()
    public = client.get("/api/v1/guides/" + guide["share_slug"])
    assert private_prompt not in public.text and "acquisition Orion" not in public.text
    providers = client.get("/api/v1/providers", params={"q": "Slack"})
    assert (
        private_prompt not in providers.text
        and "acquisition Orion" not in providers.text
    )
