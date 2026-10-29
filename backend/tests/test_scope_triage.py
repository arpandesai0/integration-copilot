import asyncio
import json
from types import SimpleNamespace

from app import api, database
from app.agents import workflows
from app.agents.client import AIUnavailable
from app.database import Message, ResearchRun, ResearchEvent, Workspace
from app.services import scope_triage
from app.services.scope_triage import ScopeDecision


def run_for(client, prompt="i want to integrate google", capabilities=None):
    workspace = client.post("/api/v1/chats", json={"prompt": prompt}).json()
    with database.SessionLocal() as db:
        if capabilities:
            db.get(Workspace, workspace["id"]).capabilities = capabilities
        run = ResearchRun(workspace_id=workspace["id"])
        db.add(run)
        db.commit()
        return workspace, run.id


def test_ambiguous_brand_asks_before_any_search_or_guide(client, monkeypatch):
    workspace, run_id = run_for(client)
    question = "Are you adding Google sign-in, or connecting to a Google API such as Drive or Gmail?"
    async def unclear(request, timeout_seconds):
        assert request["request"] == "i want to integrate google"
        return ScopeDecision(needs_clarification=True, question=question)
    monkeypatch.setattr(workflows, "assess_scope", unclear)
    monkeypatch.setattr(workflows, "client", lambda: (_ for _ in ()).throw(AssertionError("No search")))
    asyncio.run(workflows.research(run_id))
    with database.SessionLocal() as db:
        record = db.get(Workspace, workspace["id"])
        assert record.status == "awaiting_clarification"
        assert record.active_guide_version_id is None
        assert db.get(ResearchRun, run_id).status == "completed"
        assert db.query(Message).filter_by(thread_id=workspace["main_thread_id"]).order_by(Message.created_at.desc()).first().content == question
        events = db.query(ResearchEvent).filter_by(research_run_id=run_id).all()
        assert [event.event_type for event in events] == ["clarification_needed"]


def test_scoped_request_proceeds_to_search_preserving_original(client, monkeypatch):
    workspace, run_id = run_for(client, "Let users sign in with Google")
    seen = []
    async def scoped(request, timeout_seconds):
        return ScopeDecision(needs_clarification=False, focused_request="Google OpenID Connect sign-in")
    async def generate(**kwargs):
        seen.append(json.loads(kwargs["contents"]))
        raise AIUnavailable("Test stopped after reaching grounded lookup")
    monkeypatch.setattr(workflows, "assess_scope", scoped)
    monkeypatch.setattr(workflows, "client", lambda: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    asyncio.run(workflows.research(run_id))
    assert seen[0]["focused_request"] == "Google OpenID Connect sign-in"
    assert seen[0]["request"] == "Let users sign in with Google"


def test_answered_scope_is_not_asked_again(client, monkeypatch):
    _, run_id = run_for(client, capabilities="Original request\nUser clarification: Users sign in")
    async def unexpected(*args, **kwargs):
        raise AssertionError("Scoped answer must bypass triage")
    async def generate(**kwargs):
        raise AIUnavailable("Reached scoped search")
    monkeypatch.setattr(workflows, "assess_scope", unexpected)
    monkeypatch.setattr(workflows, "client", lambda: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    asyncio.run(workflows.research(run_id))
    with database.SessionLocal() as db:
        assert db.get(ResearchRun, run_id).error_message == "Reached scoped search"


def test_triage_is_fast_tool_free_and_cannot_claim_support(monkeypatch):
    calls = []
    async def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=json.dumps({"needs_clarification": True, "question": "What should your app do?", "focused_request": ""}))
    monkeypatch.setattr(scope_triage, "client", lambda: SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))))
    result = asyncio.run(scope_triage.assess_scope({"request": "Google"}, 2))
    assert result.needs_clarification
    config = calls[0]["config"]
    assert not config.tools
    assert config.http_options.timeout == 2000
    assert calls[0]["model"] == (scope_triage.settings.gemini_synthesis_model or scope_triage.settings.gemini_model)


def test_awaiting_initial_scope_can_use_clarify_endpoint(client, monkeypatch):
    workspace, run_id = run_for(client)
    with database.SessionLocal() as db:
        db.get(Workspace, workspace["id"]).status = "awaiting_clarification"
        db.get(ResearchRun, run_id).status = "completed"
        db.commit()
    async def decide(context, content):
        return SimpleNamespace(action="reply", intent="acknowledgement")
    async def reply(*args):
        yield "You're welcome!"
    monkeypatch.setattr(api, "clarify_intent", decide)
    monkeypatch.setattr(api, "clarification_reply_stream", reply)
    response = client.post(f"/api/v1/chats/{workspace['id']}/clarify", json={"content": "thanks"})
    assert response.status_code == 200
    assert "You're welcome!" in response.text
