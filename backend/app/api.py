import asyncio
import hashlib
import json
import secrets
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete, update
from app.database import *
from app.schemas import (
    CreateWorkspace,
    CreateThread,
    SendMessage,
    UpdateStep,
    CreateNote,
)
from app.services.core import *
from app.agents.workflows import research, answer_stream, clarify_intent, clarification_reply_stream
from app.agents.client import safe_error
from app.config import settings
from app.chat_store import get_chat_store

router = APIRouter(prefix="/api/v1")
_tasks = set()
_research_tasks = {}
_clarifying = set()


DEVICE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)


def owner(request: Request, response: Response):
    # The browser persists this UUID. Only its hash is used in either datastore.
    device_id = request.headers.get("x-device-id", "").strip()
    if device_id:
        if not DEVICE_ID.fullmatch(device_id):
            raise HTTPException(400, "X-Device-ID must be a valid UUID")
        return hashlib.sha256(device_id.lower().encode()).hexdigest()

    # Temporary compatibility for older clients. New clients always send X-Device-ID.
    token = request.cookies.get("copilot_session")
    if not token or len(token) != 64:
        token = secrets.token_hex(32)
        response.set_cookie(
            "copilot_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return hashlib.sha256(token.encode()).hexdigest()


def persist_chat(db, message, identity):
    store = get_chat_store()
    if not store:
        return
    thread = db.get(ConversationThread, message.thread_id)
    store.save(message, device_id=identity, workspace_id=thread.workspace_id)


def sse(name, data, id=None):
    return (
        f"id: {id}\n" if id is not None else ""
    ) + f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/providers")
def providers(q: str = "", db: Session = Depends(get_db)):
    ps = list(db.scalars(select(Provider)))
    if q:
        ps = match_providers(db, q) or [p for p in ps if q.lower() in p.name.lower()]
    return [provider_dict(p) for p in ps if not p.slug.startswith("research-")]


@router.post("/workspaces", status_code=201)
def new_workspace(
    body: CreateWorkspace, identity=Depends(owner), db: Session = Depends(get_db)
):
    return workspace_dict(db, create_workspace(db, identity, body))


@router.get("/workspaces")
def workspaces(identity=Depends(owner), db: Session = Depends(get_db)):
    return [
        workspace_dict(db, w)
        for w in db.scalars(
            select(Workspace)
            .where(Workspace.owner == identity)
            .order_by(Workspace.created_at.desc())
        )
    ]


@router.get("/workspaces/{workspace_id}")
def workspace(
    workspace_id: str, identity=Depends(owner), db: Session = Depends(get_db)
):
    return workspace_dict(db, owned(db, workspace_id, identity))


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str, identity=Depends(owner), db: Session = Depends(get_db)
):
    w = owned(db, workspace_id, identity)
    thread_ids = select(ConversationThread.id).where(
        ConversationThread.workspace_id == w.id
    )
    if db.scalar(
        select(ResearchRun.id).where(
            ResearchRun.workspace_id == w.id, ResearchRun.status == "running"
        )
    ) or db.scalar(
        select(Message.id).where(
            Message.thread_id.in_(thread_ids), Message.status == "streaming"
        )
    ):
        raise HTTPException(
            409,
            "Wait for current research or response to finish, then delete this chat.",
        )
    step_ids = select(GuideStep.id).where(GuideStep.workspace_id == w.id)
    version_ids = select(GuideVersion.id).where(GuideVersion.workspace_id == w.id)
    run_ids = select(ResearchRun.id).where(ResearchRun.workspace_id == w.id)

    # Purge private and published workspace data in foreign-key-safe order.
    # Provider records are shared by other workspaces and remain in the catalog.
    db.execute(delete(StepNote).where(StepNote.step_id.in_(step_ids)))
    db.execute(delete(Message).where(Message.thread_id.in_(thread_ids)))
    db.execute(
        update(ConversationThread)
        .where(ConversationThread.workspace_id == w.id)
        .values(parent_thread_id=None)
    )
    db.execute(
        delete(ConversationThread).where(ConversationThread.workspace_id == w.id)
    )
    db.execute(
        delete(ClaimEvidence).where(ClaimEvidence.guide_version_id.in_(version_ids))
    )
    db.execute(delete(Source).where(Source.guide_version_id.in_(version_ids)))
    db.execute(delete(GuideStep).where(GuideStep.workspace_id == w.id))
    db.execute(delete(GuideVersion).where(GuideVersion.workspace_id == w.id))
    db.execute(delete(ResearchEvent).where(ResearchEvent.research_run_id.in_(run_ids)))
    db.execute(delete(ResearchRun).where(ResearchRun.workspace_id == w.id))
    db.delete(w)
    db.commit()
    store = get_chat_store()
    if store:
        store.delete_workspace(workspace_id=workspace_id, device_id=identity)
    return {"deleted": True, "id": workspace_id}


@router.get("/workspaces/{workspace_id}/guide")
def workspace_guide(
    workspace_id: str, identity=Depends(owner), db: Session = Depends(get_db)
):
    return guide_dict(db, owned(db, workspace_id, identity))


@router.get("/guides/{share_slug}")
def public_guide(share_slug: str, db: Session = Depends(get_db)):
    w = db.scalar(select(Workspace).where(Workspace.share_slug == share_slug))
    if not w:
        raise HTTPException(404, "Guide not found")
    return guide_dict(db, w, public=True)


@router.patch("/workspaces/{workspace_id}/steps/{step_id}")
def update_step(
    workspace_id: str,
    step_id: str,
    body: UpdateStep,
    identity=Depends(owner),
    db: Session = Depends(get_db),
):
    w = owned(db, workspace_id, identity)
    step = db.get(GuideStep, step_id)
    if (
        not step
        or step.workspace_id != w.id
        or step.guide_version_id != w.active_guide_version_id
    ):
        raise HTTPException(404, "Current guide step not found")
    step.status = body.status.value
    db.commit()
    return step_dict(db, step)


@router.post("/workspaces/{workspace_id}/steps/{step_id}/notes", status_code=201)
def add_note(
    workspace_id: str,
    step_id: str,
    body: CreateNote,
    identity=Depends(owner),
    db: Session = Depends(get_db),
):
    w = owned(db, workspace_id, identity)
    step = db.get(GuideStep, step_id)
    if not step or step.workspace_id != w.id:
        raise HTTPException(404, "Step not found")
    if not body.confirmed:
        raise HTTPException(422, "Explicit confirmation is required to save a finding")
    if body.thread_id:
        thread = owned_thread(db, body.thread_id, identity)
        if thread.step_id != step.id:
            raise HTTPException(422, "Finding thread must belong to this step")
    note = StepNote(step_id=step.id, thread_id=body.thread_id, content=body.content)
    db.add(note)
    db.commit()
    return {"id": note.id, "content": note.content}


@router.get("/workspaces/{workspace_id}/threads")
def threads(workspace_id: str, identity=Depends(owner), db: Session = Depends(get_db)):
    owned(db, workspace_id, identity)
    return [
        thread_dict(t, db)
        for t in db.scalars(
            select(ConversationThread)
            .where(ConversationThread.workspace_id == workspace_id)
            .order_by(ConversationThread.created_at)
        )
    ]


@router.post("/workspaces/{workspace_id}/threads", status_code=201)
def new_thread(
    workspace_id: str,
    body: CreateThread,
    identity=Depends(owner),
    db: Session = Depends(get_db),
):
    w = owned(db, workspace_id, identity)
    if body.type == "main":
        existing = db.scalar(
            select(ConversationThread).where(
                ConversationThread.workspace_id == w.id,
                ConversationThread.type == "main",
            )
        )
        if existing:
            return thread_dict(existing, db)
    step = None
    parent = None
    if body.type == "step":
        step = db.get(GuideStep, body.step_id) if body.step_id else None
        parent = (
            db.get(ConversationThread, body.parent_thread_id)
            if body.parent_thread_id
            else None
        )
        if not step or step.workspace_id != w.id:
            raise HTTPException(422, "Step must belong to this workspace")
        if not parent or parent.workspace_id != w.id or parent.type != "main":
            raise HTTPException(422, "Parent must be this workspace’s main thread")
    t = ConversationThread(
        workspace_id=w.id,
        type=body.type,
        step_id=step.id if step else None,
        guide_version_id=step.guide_version_id if step else w.active_guide_version_id,
        parent_thread_id=parent.id if parent else None,
        title=body.title
        or (step.data["title"] if step else "Integration conversation"),
    )
    db.add(t)
    db.commit()
    return thread_dict(t, db)


@router.get("/threads/{thread_id}/messages")
def messages(thread_id: str, identity=Depends(owner), db: Session = Depends(get_db)):
    owned_thread(db, thread_id, identity)
    relational = [
        message_dict(m)
        for m in db.scalars(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at)
        )
    ]
    store = get_chat_store()
    if not store:
        return relational
    # Backfill pre-migration messages once, then serve MongoDB as the chat source.
    for item in db.scalars(
        select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at)
    ):
        persist_chat(db, item, identity)
    return store.list(thread_id=thread_id, device_id=identity)


@router.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    body: SendMessage,
    identity=Depends(owner),
    db: Session = Depends(get_db),
):
    thread = owned_thread(db, thread_id, identity)
    if db.scalar(
        select(Message).where(
            Message.thread_id == thread_id, Message.status == "streaming"
        )
    ):
        raise HTTPException(
            409, "A response is already being generated in this discussion"
        )
    if thread.type == "main":
        workspace = db.get(Workspace, thread.workspace_id)
        current = guide_dict(db, workspace) if workspace.active_guide_version_id else None
        if (current and (current["clarification_needed"] or (not current["steps"] and current.get("oauth_support_status") == "unknown"))) or workspace.status == "awaiting_clarification":
            # Route on the server too: older clients must not bypass investigation.
            return await clarify_request(workspace.id, body, identity, db)
    user = Message(thread_id=thread.id, role="user", content=body.content)
    db.add(user)
    db.commit()
    persist_chat(db, user, identity)
    context = context_package(db, thread)
    assistant = Message(
        thread_id=thread.id, role="assistant", content="", status="streaming"
    )
    db.add(assistant)
    db.commit()
    persist_chat(db, assistant, identity)
    assistant_id = assistant.id
    mode = thread.type

    async def stream():
        text = ""
        complete = False
        yield sse("message_started", {"id": assistant_id, "thread_id": thread_id})
        try:
            async with asyncio.timeout(settings.chat_timeout_seconds):
                async for delta in answer_stream(context, mode):
                    text += delta
                    yield sse(
                        "message_delta",
                        {"id": assistant_id, "delta": delta, "content": delta},
                    )
            if not text:
                raise RuntimeError("Empty model response")
            citations = []
            for source in context.get(
                "relevant_sources",
                context.get("guide", {}).get("sources", [])
                if context.get("guide")
                else [],
            ):
                if source["url"] in text:
                    citations.append(source)
                    yield sse("citation", source)
            with SessionLocal() as session:
                m = session.get(Message, assistant_id)
                m.content = text
                m.status = "completed"
                m.citations = citations
                session.commit()
                persist_chat(session, m, identity)
                result = message_dict(m)
            complete = True
            yield sse("message_completed", result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = safe_error(exc)
            with SessionLocal() as session:
                m = session.get(Message, assistant_id)
                m.content = text or error
                m.status = "failed"
                session.commit()
                persist_chat(session, m, identity)
            yield sse("message_error", {"id": assistant_id, "message": error})
        finally:
            if not complete:
                with SessionLocal() as session:
                    m = session.get(Message, assistant_id)
                    if m.status == "streaming":
                        m.content = text
                        m.status = "incomplete"
                        session.commit()
                        persist_chat(session, m, identity)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/workspaces/{workspace_id}/research", status_code=202)
async def start_research(
    workspace_id: str, identity=Depends(owner), db: Session = Depends(get_db)
):
    w = owned(db, workspace_id, identity)
    validate_provider_request(w.use_case)
    return launch_research(db, w)


def launch_research(db, w):
    running = db.scalar(
        select(ResearchRun).where(
            ResearchRun.workspace_id == w.id, ResearchRun.status == "running"
        )
    )
    if running:
        return research_payload(running)
    run = ResearchRun(workspace_id=w.id)
    db.add(run)
    w.status = "researching"
    db.commit()
    task = asyncio.create_task(research(run.id))
    _tasks.add(task)
    _research_tasks[run.id] = task

    def finished(done):
        _tasks.discard(done)
        _research_tasks.pop(run.id, None)

    task.add_done_callback(finished)
    return research_payload(run)



@router.post("/workspaces/{workspace_id}/clarify")
async def clarify_request(
    workspace_id: str, body: SendMessage, identity=Depends(owner), db: Session = Depends(get_db)
):
    w = owned(db, workspace_id, identity)
    guide = guide_dict(db, w) if w.active_guide_version_id else None
    recovering = not guide and w.status in {"research_failed", "research_cancelled", "awaiting_clarification"}
    if not recovering and not (guide and (guide["clarification_needed"] or (not guide["steps"] and guide.get("oauth_support_status") == "unknown"))):
        raise HTTPException(409, "This integration is not waiting for clarification")
    if db.scalar(select(ResearchRun).where(ResearchRun.workspace_id == w.id, ResearchRun.status == "running")):
        raise HTTPException(409, "Research is already running")
    thread = db.scalar(select(ConversationThread).where(ConversationThread.workspace_id == w.id, ConversationThread.type == "main"))
    if w.id in _clarifying or db.scalar(select(Message).where(Message.thread_id == thread.id, Message.status == "streaming")):
        raise HTTPException(409, "A response is already being generated")
    version = db.get(GuideVersion, w.active_guide_version_id) if w.active_guide_version_id else None
    if version and guide["clarification_questions"] and not version.data.get("clarification_message_id"):
        prompt = Message(thread_id=thread.id, role="assistant", content=guide["clarification_questions"][0])
        db.add(prompt)
        db.flush()
        version.data = {**version.data, "clarification_message_id": prompt.id}
    user = Message(thread_id=thread.id, role="user", content=body.content)
    db.add(user)
    db.commit()
    persist_chat(db, user, identity)
    context = context_package(db, thread)
    assistant = Message(thread_id=thread.id, role="assistant", content="", status="streaming")
    db.add(assistant)
    db.commit()
    persist_chat(db, assistant, identity)
    assistant_id, thread_id, workspace_id = assistant.id, thread.id, w.id
    _clarifying.add(workspace_id)

    async def stream():
        text = ""
        complete = False
        yield sse("message_started", {"id": assistant_id, "thread_id": thread_id, "user_message_id": user.id})
        try:
            decision = await asyncio.wait_for(clarify_intent(context, body.content), timeout=settings.clarification_intent_timeout_seconds + 5)
            async with asyncio.timeout(settings.clarification_reply_timeout_seconds + 5):
                async for delta in clarification_reply_stream(context, body.content, decision):
                    text += delta
                    yield sse("message_delta", {"id": assistant_id, "delta": delta})
            if not text.strip():
                raise RuntimeError("Empty model response")
            with SessionLocal() as session:
                message = session.get(Message, assistant_id)
                message.content, message.status = text, "completed"
                session.commit()
                persist_chat(session, message, identity)
                result = message_dict(message)
            complete = True
            yield sse("message_completed", result)
            if decision.action == "research":
                with SessionLocal() as session:
                    record = session.get(Workspace, workspace_id)
                    # All exact answers are retained, including earlier auth/login context.
                    answers = [
                        item["content"] for item in context.get("main_thread_messages", [])
                        if item["role"] == "user"
                    ]
                    record.capabilities = (record.capabilities + "\nUser clarification: " + "\n".join(answers))[-20000:]
                    session.commit()
                    run = launch_research(session, record)
                yield sse("research_started", run)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = safe_error(exc)
            with SessionLocal() as session:
                message = session.get(Message, assistant_id)
                message.content = text or error
                message.status = "failed"
                session.commit()
                persist_chat(session, message, identity)
            yield sse("message_error", {"id": assistant_id, "message": error})
        finally:
            _clarifying.discard(workspace_id)
            if not complete:
                with SessionLocal() as session:
                    message = session.get(Message, assistant_id)
                    if message and message.status == "streaming":
                        message.content, message.status = text, "incomplete"
                        session.commit()
                        persist_chat(session, message, identity)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def research_payload(run):
    started = run.started_at.isoformat()
    if run.started_at.tzinfo is None:
        started += "Z"
    return {
        "id": run.id,
        "run_id": run.id,
        "status": run.status,
        "started_at": started,
        "timeout_seconds": settings.research_timeout_seconds,
    }


@router.post("/research-runs/{run_id}/cancel")
async def cancel_research(
    run_id: str, identity=Depends(owner), db: Session = Depends(get_db)
):
    run = db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(404, "Research run not found")
    workspace = owned(db, run.workspace_id, identity)
    if run.status == "running":
        run.status = "cancelled"
        workspace.status = (
            "ready" if workspace.active_guide_version_id else "research_cancelled"
        )
        db.add(
            ResearchEvent(
                research_run_id=run.id,
                event_type="research_cancelled",
                payload={
                    "message": "Research stopped. You can retry or ask a more specific integration question."
                },
            )
        )
        db.commit()
        task = _research_tasks.get(run_id)
        if task:
            task.cancel()
    return research_payload(run)


@router.get("/research-runs/{run_id}/events")
async def research_events(
    run_id: str,
    request: Request,
    after: int = 0,
    identity=Depends(owner),
    db: Session = Depends(get_db),
):
    run = db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(404, "Research run not found")
    owned(db, run.workspace_id, identity)
    last = request.headers.get("last-event-id", "")
    try:
        cursor = max(after, int(last or 0))
    except ValueError:
        raise HTTPException(400, "Invalid Last-Event-ID")

    async def events():
        nonlocal cursor
        idle = 0
        while not await request.is_disconnected():
            with SessionLocal() as session:
                records = list(
                    session.scalars(
                        select(ResearchEvent)
                        .where(
                            ResearchEvent.research_run_id == run_id,
                            ResearchEvent.id > cursor,
                        )
                        .order_by(ResearchEvent.id)
                    )
                )
                state = session.get(ResearchRun, run_id).status
            for record in records:
                cursor = record.id
                yield sse(record.event_type, record.payload, record.id)
            if state != "running":
                break
            idle += 1
            if idle % 20 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
