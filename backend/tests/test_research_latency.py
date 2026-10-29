"""Research latency contracts; mocked SDK and website calls, never live research."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from app import database
from app.agents import workflows
from app.database import ResearchEvent, ResearchRun
from app.seeds.guides import seed_guide


@pytest.mark.parametrize("hang", ["search", "synthesis", "highlights"])
def test_research_has_bounded_stages_and_one_terminal_event(client, monkeypatch, hang):
    workspace = client.post("/api/v1/workspaces", json={"prompt": "Xbox"}).json()
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=workspace["id"])
        db.add(run)
        db.commit()
        run_id = run.id
    for name in (
        "research_timeout_seconds",
        "research_search_timeout_seconds",
        "research_synthesis_timeout_seconds",
        "research_excerpt_timeout_seconds",
    ):
        monkeypatch.setattr(workflows.settings, name, 0.02)
    calls = []
    stopped = []

    async def blocked():
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)

    async def generate(**kwargs):
        calls.append(kwargs)
        if (len(calls) == 1 and hang == "search") or (
            len(calls) == 2 and hang == "synthesis"
        ):
            await blocked()
        if len(calls) == 1:
            web = SimpleNamespace(
                uri="https://docs.example.com/oauth", title="Official documentation"
            )
            return SimpleNamespace(
                text="Documented authentication",
                candidates=[
                    SimpleNamespace(
                        grounding_metadata=SimpleNamespace(
                            grounding_chunks=[SimpleNamespace(web=web)]
                        )
                    )
                ],
            )
        sources = json.loads(kwargs["contents"])["sources"]
        data = seed_guide("slack").model_dump(mode="json")
        data["citations"] = []
        for citation_step in data["steps"]:
            citation_step["citations"] = []
        data["sources"] = sources
        for step in data["steps"]:
            step["source_ids"] = ["source-1"]
        return SimpleNamespace(text=json.dumps(data))

    monkeypatch.setattr(
        workflows,
        "client",
        lambda: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        ),
    )
    monkeypatch.setattr(workflows, "enrich_guide_sources", lambda guide: blocked())
    started = time.monotonic()
    asyncio.run(workflows.research(run_id))
    assert time.monotonic() - started < 0.5
    assert stopped == [True]
    with database.SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        events = db.query(ResearchEvent).filter_by(research_run_id=run_id).all()
        terminals = [
            e for e in events if e.event_type in {"research_failed", "guide_ready"}
        ]
        assert len(terminals) == 1
        if hang == "highlights":
            assert run.status == "completed"
            assert terminals[0].event_type == "guide_ready"
        else:
            assert run.status == "failed"
            assert "timed out" in run.error_message
            assert "official documentation URL" in terminals[0].payload["message"]
    assert calls[0]["config"].http_options.retry_options.attempts == 1
    assert calls[0]["config"].max_output_tokens == 2200


def test_research_thinking_and_transport_settings_do_not_change_chat(monkeypatch):
    monkeypatch.setattr(workflows.settings, "gemini_model", "gemini-3.8-flash")
    config = workflows.research_config(0.05, max_output_tokens=3000)
    assert config.thinking_config.thinking_level.value == "LOW"
    assert config.http_options.timeout == 50
    assert config.http_options.retry_options.attempts == 1
    monkeypatch.setattr(workflows.settings, "gemini_model", "gemini-2.5-flash")
    assert workflows.research_config(1).thinking_config is None


@pytest.mark.parametrize("error_kind", ["transport", "provider_deadline"])
def test_provider_timeout_is_not_reported_as_configuration_failure(
    client, monkeypatch, error_kind
):
    import httpx

    class DeadlineError(Exception):
        code = 504

    workspace = client.post("/api/v1/workspaces", json={"prompt": "Xbox"}).json()
    with database.SessionLocal() as db:
        run = ResearchRun(workspace_id=workspace["id"])
        db.add(run)
        db.commit()
        run_id = run.id

    async def generate(**kwargs):
        if error_kind == "transport":
            raise httpx.ReadTimeout("provider response timed out")
        raise DeadlineError()

    monkeypatch.setattr(
        workflows,
        "client",
        lambda: SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        ),
    )
    asyncio.run(workflows.research(run_id))
    with database.SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        assert run.status == "failed"
        assert "timed out while finding official documentation" in run.error_message
        assert "configuration" not in run.error_message
