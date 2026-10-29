import json
from types import SimpleNamespace
from app import api, database
from app.database import Workspace, Message, ResearchRun, ConversationThread
from app.seeds.guides import seed_guide
from app.services.core import persist_guide, guide_dict


def events(response):
    return [
        (block.splitlines()[0].removeprefix("event: "), json.loads(block.splitlines()[1].removeprefix("data: ")))
        for block in response.text.strip().split("\n\n")
    ]


def pending(client):
    w = client.post("/api/v1/chats", json={"prompt": "Slack"}).json()
    with database.SessionLocal() as db:
        record = db.get(Workspace, w["id"])
        guide = seed_guide("slack").model_copy(update={
            "oauth_support_status": "unknown", "steps": [],
            "clarification_questions": [],
            "uncertainties": ["Which data do you want to access?"],
        })
        persist_guide(db, record, guide)
    return w


def test_legacy_empty_unknown_projects_question_and_anchor(client):
    w = pending(client)
    guide = client.get(f"/api/v1/chats/{w['id']}/guide").json()
    assert guide["clarification_needed"]
    assert guide["clarification_questions"] == ["Which data do you want to access?"]
    assert guide["conversation_anchor_message_id"]
    assert not guide["steps"]


def test_confirmed_unsupported_is_not_unclear(client):
    w = pending(client)
    with database.SessionLocal() as db:
        record = db.get(Workspace, w["id"])
        guide = seed_guide("slack").model_copy(update={"oauth_support_status": "unsupported", "steps": []})
        persist_guide(db, record, guide)
    result = client.get(f"/api/v1/chats/{w['id']}/guide").json()
    assert not result["clarification_needed"]
    assert result["clarification_questions"] == []


def test_acknowledgement_keeps_question_without_research(client, monkeypatch):
    w = pending(client)
    async def decide(context, content):
        assert content == "thanks"
        return SimpleNamespace(action="reply", intent="acknowledgement")
    monkeypatch.setattr(api, "clarify_intent", decide)
    async def reply(context, content, decision):
        for chunk in ("You're ", "welcome!") if content == "thanks" else ("I'll check the docs ", "for reading tickets."):
            yield chunk
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    response = client.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "thanks"})
    assert response.status_code == 200
    assert [name for name, _ in events(response)][-1] == "message_completed"
    with database.SessionLocal() as db:
        assert db.query(ResearchRun).filter_by(workspace_id=w["id"]).count() == 0
        messages = db.query(Message).filter_by(thread_id=w["main_thread_id"]).order_by(Message.created_at).all()
        assert [m.content for m in messages][-3:] == ["Which data do you want to access?", "thanks", "You're welcome!"]


def test_actual_answer_starts_research_with_exact_requirement(client, monkeypatch):
    w = pending(client)
    async def decide(context, content):
        return SimpleNamespace(action="research", intent="read tickets")
    monkeypatch.setattr(api, "clarify_intent", decide)
    async def reply(context, content, decision):
        for chunk in ("You're ", "welcome!") if content == "thanks" else ("I'll check the docs ", "for reading tickets."):
            yield chunk
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    captured = []
    def launch(db, record):
        captured.append(record.capabilities)
        return {"id": "test-run", "run_id": "test-run", "status": "running"}
    monkeypatch.setattr(api, "launch_research", launch)
    response = client.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "Read tickets from our account"})
    assert response.status_code == 200
    assert events(response)[-1] == ("research_started", {"id": "test-run", "run_id": "test-run", "status": "running"})
    assert captured[0].endswith("Read tickets from our account")
    with database.SessionLocal() as db:
        record = db.get(Workspace, w["id"])
        assert "Read tickets from our account" in record.capabilities
        guide = guide_dict(db, record)
        assert guide["clarification_message_id"]
        # Persisting a new guide anchors it to the supplied answer, not the initial prompt.
        persist_guide(db, record, seed_guide("slack"))
        next_guide = guide_dict(db, record)
        anchor = db.get(Message, next_guide["conversation_anchor_message_id"])
        assert anchor.content == "I'll check the docs for reading tickets."


def test_clarification_endpoint_is_owner_scoped(client):
    from fastapi.testclient import TestClient
    from app.main import app
    w = pending(client)
    with TestClient(app) as stranger:
        response = stranger.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "Read tickets"})
        assert response.status_code == 404


def test_failed_research_can_be_refined_without_existing_guide(client, monkeypatch):
    w = client.post("/api/v1/chats", json={"prompt": "Help me integrate Example Service"}).json()
    with database.SessionLocal() as db:
        record = db.get(Workspace, w["id"])
        record.active_guide_version_id = None
        record.status = "research_failed"
        db.commit()
    async def decide(context, content):
        assert context["guide"] is None
        return SimpleNamespace(action="research", intent="read tickets")
    monkeypatch.setattr(api, "clarify_intent", decide)
    async def reply(context, content, decision):
        for chunk in ("You're ", "welcome!") if content == "thanks" else ("I'll check the docs ", "for reading tickets."):
            yield chunk
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    captured = []
    def launch(db, record):
        captured.append(record.capabilities)
        return {"id": "test-run", "status": "running"}
    monkeypatch.setattr(api, "launch_research", launch)
    response = client.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "I need to read tickets"})
    assert response.status_code == 200
    assert events(response)[-1][0] == "research_started"
    assert captured[0].endswith("I need to read tickets")

def test_clarification_streams_before_completion_and_retains_prior_auth_answers(client, monkeypatch):
    w = pending(client)
    async def decide(context, content):
        assert context["main_thread_messages"][-1]["content"] == "I want my users to log in"
        return SimpleNamespace(action="research", intent="provider as identity provider")
    async def reply(context, content, decision):
        yield "I'll check "
        yield "public sign-in support."
    monkeypatch.setattr(api, "clarify_intent", decide)
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    captured = []
    def launch(db, record):
        captured.append(record.capabilities)
        return {"id": "test-run", "status": "running"}
    monkeypatch.setattr(api, "launch_research", launch)
    with database.SessionLocal() as db:
        db.add(Message(thread_id=w["main_thread_id"], role="user", content="I want OAuth"))
        db.commit()
    response = client.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "I want my users to log in"})
    output = events(response)
    assert [name for name, _ in output] == ["message_started", "message_delta", "message_delta", "message_completed", "research_started"]
    assert [data["delta"] for name, data in output if name == "message_delta"] == ["I'll check ", "public sign-in support."]
    assert "I want OAuth" in captured[0] and "I want my users to log in" in captured[0]
    with database.SessionLocal() as db:
        guide = guide_dict(db, db.get(Workspace, w["id"]))
        assert not guide["clarification_needed"]
        assert guide["clarification_questions"] == []


def test_clarification_failure_preserves_input_and_releases_lock(client, monkeypatch):
    w = pending(client)
    async def fail(context, content):
        raise RuntimeError("private model failure")
    monkeypatch.setattr(api, "clarify_intent", fail)
    response = client.post(f"/api/v1/chats/{w['id']}/clarify", json={"content": "OAuth"})
    assert [name for name, _ in events(response)] == ["message_started", "message_error"]
    assert w["id"] not in api._clarifying
    with database.SessionLocal() as db:
        messages = db.query(Message).filter_by(thread_id=w["main_thread_id"]).order_by(Message.created_at).all()
        assert messages[-2].content == "OAuth"
        assert messages[-1].status == "failed"
        assert "private model failure" not in messages[-1].content

def test_disconnect_preserves_partial_reply_and_releases_lock(client, monkeypatch):
    import asyncio
    from app.schemas import SendMessage
    w = pending(client)
    async def decide(context, content):
        return SimpleNamespace(action="reply", intent="explain sign-in versus API access")
    async def reply(context, content, decision):
        yield "Do you mean signing users "
        yield "into your app?"
    monkeypatch.setattr(api, "clarify_intent", decide)
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    async def disconnect():
        with database.SessionLocal() as db:
            record = db.get(Workspace, w["id"])
            response = await api.clarify_request(w["id"], SendMessage(content="auth?"), record.owner, db)
            iterator = response.body_iterator
            assert "message_started" in await anext(iterator)
            assert "message_delta" in await anext(iterator)
            await iterator.aclose()
    asyncio.run(disconnect())
    assert w["id"] not in api._clarifying
    with database.SessionLocal() as db:
        last = db.query(Message).filter_by(thread_id=w["main_thread_id"]).order_by(Message.created_at.desc()).first()
        assert last.content == "Do you mean signing users "
        assert last.status == "incomplete"
        assert db.query(ResearchRun).filter_by(workspace_id=w["id"]).count() == 0


def test_short_clarification_uses_fast_model_and_forwards_sdk_deltas(monkeypatch):
    import asyncio
    from app.agents import workflows
    requested = []
    async def generate(**kwargs):
        requested.append(kwargs)
        async def chunks():
            yield SimpleNamespace(text="Do you mean ")
            yield SimpleNamespace(text="signing users in?")
        return chunks()
    monkeypatch.setattr(workflows, "client", lambda: SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate))
    ))
    async def collect():
        return [part async for part in workflows.clarification_reply_stream(
            {}, "auth?", SimpleNamespace(action="reply", intent="sign-in versus API access")
        )]
    assert asyncio.run(collect()) == ["Do you mean ", "signing users in?"]
    assert requested[0]["model"] == "gemini-3.5-flash-lite"


def test_explicit_missing_requirement_is_not_hidden_by_assumed_steps(client):
    w = pending(client)
    with database.SessionLocal() as db:
        record = db.get(Workspace, w["id"])
        guide = seed_guide("slack").model_copy(update={
            "clarification_questions": ["Are you adding sign-in or accessing messages?"],
        })
        persist_guide(db, record, guide)
    result = client.get(f"/api/v1/chats/{w['id']}/guide").json()
    assert result["steps"]
    assert result["clarification_needed"] is True


def test_pending_main_chat_message_hands_off_even_for_older_clients(client, monkeypatch):
    w = pending(client)
    async def decide(context, content):
        return SimpleNamespace(action="research", intent="user sign-in")
    async def reply(context, content, decision):
        yield "I'll investigate the complete sign-in setup."
    monkeypatch.setattr(api, "clarify_intent", decide)
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    captured = []
    def launch(db, record):
        captured.append(record.capabilities)
        return {"id": "handoff-run", "status": "running"}
    monkeypatch.setattr(api, "launch_research", launch)
    response = client.post(f"/api/v1/threads/{w['main_thread_id']}/messages", json={"content": "SSO"})
    assert response.status_code == 200
    assert events(response)[-1][0] == "research_started"
    assert captured[0].endswith("SSO")
