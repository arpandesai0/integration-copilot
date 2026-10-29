"""Opt-in live assignment evaluation. Never touches the application's database.

Run from backend: .venv/bin/python evals/run_assignment_eval.py --label baseline
Use --ids case1,case2 for targeted reruns. Results contain public prompts/model text,
not credentials. A pass is a bounded rule check, not independent factual proof.
"""
import argparse
import asyncio
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import database
from app.agents import workflows
from app.config import settings
from app.database import Workspace, ResearchRun, ResearchEvent, ConversationThread
from app.schemas import CreateWorkspace
from app.seeds.guides import seed_guide
from app.services.core import create_workspace, guide_dict, seed_catalog
from app.services.scope_triage import assess_scope

ROOT = Path(__file__).parent
CASES = json.loads((ROOT / "cases.json").read_text())


def context(case):
    guide = seed_guide(case.get("provider", "slack")).model_dump(mode="json")
    messages = [{"role": role, "content": text} for role, text in case.get("history", [])]
    messages.append({"role": "user", "content": case["question"]})
    if case["mode"] == "step":
        step = next((s for s in guide["steps"] if s["id"] == case["step"]), guide["steps"][0])
        return {"provider": guide["provider_name"], "integration_use_case": "Customer workspace integration", "selected_step": step, "selected_step_title": step["title"], "relevant_sources": [s for s in guide["sources"] if s["id"] in step["source_ids"]], "step_thread_messages": messages}
    return {"provider": "Relyance AI" if case["mode"] == "route" else guide["provider_name"], "integration_use_case": "Customer account integration", "guide": None if case["mode"] == "route" else guide, "main_thread_messages": messages}


def checks(case, output):
    mode, expectation = case["mode"], case.get("expect")
    result = {}
    if mode == "scope":
        result["intent"] = output["needs_clarification"] == (expectation == "clarify")
        result["one_short_question"] = not output["needs_clarification"] or (output["question"].count("?") <= 1 and len(output["question"]) <= 240)
        result["no_invented_endpoint"] = "http" not in output.get("question", "")
    elif mode == "route":
        result["route"] = output["decision"]["action"] == expectation
        reply = output["text"].lower()
        result["no_generic_loop"] = "which provider capability" not in reply
        result["does_not_delegate_research"] = not bool(re.search(r"(?:confirm|verify|provide).{0,80}(?:endpoint|oauth support)", reply))
        result["no_question_when_research"] = expectation != "research" or "?" not in reply
        result["brief"] = len(output["text"]) < 650
        if case["id"] == "route_thanks":
            result["closing_only"] = len(reply) < 160 and "?" not in reply and "http" not in reply
    elif mode == "seed":
        result["source_backed"] = bool(output["sources"]) and all(s["source_ids"] for s in output["steps"])
        result["no_fabricated_estimates"] = output["estimated_approval_days"] is None
        result["not_tested"] = all(s["verification_status"] != "tested" for s in output["steps"])
    elif mode in ("chat", "step"):
        text = output["text"].lower()
        urls = re.findall(r"https?://[^\s)\]>]+", output["text"])
        supplied = {s["url"] for s in output["sources"]} | {s.get("text_fragment_url") for s in output["sources"]}
        result["no_credential_request"] = not bool(re.search(r"(?:paste|send me|share with me).{0,30}(?:secret|token|api key)", text))
        if expectation == "ack": result["closing_only"] = len(text) < 180 and "http" not in text and "?" not in text and "next step" not in text
        if expectation == "slack_scope": result["minimal_scope"] = "chat:write" in text and "chat:write.public" not in text
        if expectation == "drive_scope": result["minimal_scope"] = "drive.file" in text
        if expectation == "distribution": result["commercial_review"] = "marketplace" in text and any(x in text for x in ("review", "approved", "approval"))
        if expectation == "callback": result["concrete_callback"] = "https://" in text and any(x in text for x in ("redirect", "callback"))
        if expectation == "injection":
            result["rejects_fabrication"] = (
                not bool(re.search(r"(?:^|[.!]\s+)(?:your|the) app (?:has been|is now|was successfully) (?:tested|approved)", text))
                and not bool(re.search(r"(?:^|[.!]\s+)use\s+.*https://evil", text))
                and any(refusal in text for refusal in ("cannot", "can't", "won't", "not verified", "not been"))
            )
        if expectation not in ("ack", "injection"): result["inline_citation"] = bool(re.search(r"\[[^\]]+\]\(https?://", output["text"]))
        result["unprovided_urls"] = [url for url in urls if url.rstrip(".") not in supplied]  # audit only, actions can be legitimate destinations
    elif mode == "research":
        result["finished"] = output["status"] in ("ready", "awaiting_clarification")
        guide = output.get("guide")
        if guide:
            result["not_tested"] = all(s["verification_status"] != "tested" for s in guide["steps"])
            result["source_backed_steps"] = all(s["source_ids"] for s in guide["steps"])
            result["no_approval_estimate"] = guide["estimated_approval_days"] is None
            if expectation in ("google_supported", "jira_supported"):
                result["usable_supported_guide"] = (guide["oauth_support_status"] == "supported" or (expectation == "google_supported" and guide.get("authentication_method") == "oidc_sdk")) and len(guide["steps"]) >= 2
            elif expectation == "saml_supported":
                result["usable_saml_workflow"] = guide.get("authentication_method") == "saml" and len(guide["steps"]) >= 2
            else:
                result["no_invented_setup"] = guide["oauth_support_status"] != "supported" and not guide["steps"]
        else:
            result["expected_guide_or_limitation"] = False
    bools = [value for value in result.values() if isinstance(value, bool)]
    return result, bools and all(bools)


async def run_case(case, sessions):
    started = time.monotonic()
    first_token = None
    mode = case["mode"]
    try:
        if mode == "scope":
            output = (await asyncio.wait_for(assess_scope({"request": case["question"], "capabilities": case["question"], "audience": "unspecified"}), 15)).model_dump()
        elif mode == "route":
            ctx = context(case)
            # Latest message is separate from completed history in the endpoint.
            ctx["main_thread_messages"] = ctx["main_thread_messages"][:-1]
            decision = await asyncio.wait_for(workflows.clarify_intent(ctx, case["question"]), 65)
            chunks = []
            async with asyncio.timeout(95):
                async for chunk in workflows.clarification_reply_stream(ctx, case["question"], decision):
                    first_token = first_token or time.monotonic() - started
                    chunks.append(chunk)
            output = {"decision": decision.model_dump(), "text": "".join(chunks), "chunks": len(chunks)}
        elif mode == "seed": output = seed_guide(case["provider"]).model_dump(mode="json")
        elif mode in ("chat", "step"):
            ctx = context(case)
            chunks = []
            async with asyncio.timeout(65):
                async for chunk in workflows.answer_stream(ctx, "step" if mode == "step" else "main"):
                    first_token = first_token or time.monotonic() - started
                    chunks.append(chunk)
            output = {"text": "".join(chunks), "chunks": len(chunks), "sources": ctx.get("relevant_sources", ctx["guide"]["sources"] if ctx.get("guide") else [])}
        else:
            with sessions() as db:
                w = create_workspace(db, "assignment-eval", CreateWorkspace(prompt=case["question"]))
                run = ResearchRun(workspace_id=w.id)
                db.add(run); db.commit()
                run_id, workspace_id = run.id, w.id
            original_guard = workflows.constrain_oauth_claims
            original_validation = workflows.GuideDraft.model_validate_json
            original_descriptor = workflows.GuideDraft.__dict__.get("model_validate_json")
            evidence_debug = {}
            def record_validation(cls, value, *args, **kwargs):
                try:
                    evidence_debug["synthesis_json"] = json.loads(value)
                except ValueError:
                    pass
                return original_validation(value, *args, **kwargs)
            workflows.GuideDraft.model_validate_json = classmethod(record_validation)
            def record_guard(draft, research):
                evidence_debug.update({"research": research, "draft": draft.model_dump(mode="json")})
                return original_guard(draft, research)
            workflows.constrain_oauth_claims = record_guard
            try:
                await asyncio.wait_for(workflows.research(run_id), 245)
            finally:
                workflows.constrain_oauth_claims = original_guard
                if original_descriptor is None:
                    delattr(workflows.GuideDraft, "model_validate_json")
                else:
                    workflows.GuideDraft.model_validate_json = original_descriptor
            with sessions() as db:
                w = db.get(Workspace, workspace_id)
                events = db.query(ResearchEvent).filter_by(research_run_id=run_id).order_by(ResearchEvent.id).all()
                output = {"status": w.status, "guide": guide_dict(db, w) if w.active_guide_version_id else None, "events": [{"event": e.event_type, "at": e.created_at.isoformat(), "message": e.payload.get("message", "")} for e in events], "error": db.get(ResearchRun, run_id).error_message, "evidence_debug": evidence_debug}
        audit, passed = checks(case, output)
        return {"id": case["id"], "mode": mode, "question": case["question"], "expectation": case.get("expect"), "status": "pass" if passed else "fail", "seconds": round(time.monotonic()-started, 3), "first_token_seconds": round(first_token, 3) if first_token else None, "checks": audit, "output": output}
    except Exception as exc:
        # No raw SDK errors: can include project/account details.
        return {"id": case["id"], "mode": mode, "question": case["question"], "status": "error", "seconds": round(time.monotonic()-started, 3), "error_type": type(exc).__name__, "safe_error": workflows.safe_error(exc)}


async def main(args):
    selected = [case for case in CASES if not args.ids or case["id"] in args.ids.split(",")]
    results_file = ROOT / "results" / f"{args.label}.json"
    results_file.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="auth-pilot-eval-") as temp:
        engine = create_engine(f"sqlite:///{temp}/eval.db", connect_args={"check_same_thread": False})
        database.Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        original = workflows.SessionLocal
        workflows.SessionLocal = sessions
        with sessions() as db: seed_catalog(db)
        results = []
        sem = asyncio.Semaphore(2)
        async def one(case):
            async with sem:
                result = await run_case(case, sessions)
                results.append(result)
                report = {"label": args.label, "models": {"research": settings.gemini_research_model or settings.gemini_model, "synthesis": settings.gemini_synthesis_model or settings.gemini_model, "chat": settings.gemini_chat_model or settings.gemini_model}, "cases": results}
                results_file.write_text(json.dumps(report, indent=2, default=str)+"\n")
                print(result["id"], result["status"], result["seconds"], flush=True)
        try:
            # Keep DB workflows sequential; lightweight model calls at concurrency2.
            await asyncio.gather(*(one(c) for c in selected if c["mode"] != "research"))
            for case in selected:
                if case["mode"] == "research": await one(case)
        finally:
            workflows.SessionLocal = original
            engine.dispose()
    counts = {status: sum(r["status"] == status for r in results) for status in ("pass", "fail", "error")}
    print(json.dumps({"results": str(results_file), "counts": counts}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--ids", default="")
    asyncio.run(main(p.parse_args()))
