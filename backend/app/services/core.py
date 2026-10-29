import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from app.config import settings
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import (
    Provider,
    Workspace,
    GuideVersion,
    GuideStep,
    Source,
    ClaimEvidence,
    ConversationThread,
    Message,
    StepNote,
    now,
)
from app.schemas import Guide
from app.services.source_links import source_link
from app.services.claim_citations import project_citations
from app.seeds.guides import CATALOG, seed_guide


GROUNDING_REDIRECT_HOST = "vertexaisearch.cloud.google.com"
GROUNDING_REDIRECT_URL = re.compile(
    r"https://vertexaisearch\.cloud\.google\.com/[^\s)\]}>\"]+"
)


def _is_grounding_redirect(value):
    try:
        return urlsplit(str(value)).hostname == GROUNDING_REDIRECT_HOST
    except (TypeError, ValueError):
        return False


def _chat_source(source):
    """Return evidence safe to place in model context.

    Grounded search URLs are opaque transport redirects, not useful public
    citations. Prefer a server-verified passage destination and withhold the
    source when no resolved destination is available.
    """
    result = dict(source)
    if not _is_grounding_redirect(result.get("url")):
        return result
    destinations = [
        result.get("text_fragment_url"),
        *(result.get("step_text_fragment_urls") or {}).values(),
    ]
    resolved = next(
        (
            str(destination)
            for destination in destinations
            if destination and not _is_grounding_redirect(destination)
        ),
        None,
    )
    if not resolved:
        return None
    result["url"] = resolved
    return result


def _chat_sources(sources):
    return [projected for source in sources if (projected := _chat_source(source))]


def _chat_messages(messages, sources):
    replacements = {
        str(source["url"]): str(projected["url"])
        for source in sources
        if (projected := _chat_source(source))
        and str(source.get("url", "")) != str(projected["url"])
    }
    result = []
    for message in messages:
        content = message["content"]
        content = GROUNDING_REDIRECT_URL.sub(
            lambda match: replacements.get(
                match.group(0), "[unresolved grounding source]"
            ),
            content,
        )
        result.append({**message, "content": content})
    return result


def _chat_guide(guide):
    if not guide:
        return None
    # JSON data is already the public serialization shape; a round trip keeps
    # chat projection isolated from API/persistence objects.
    result = json.loads(json.dumps(guide, default=str))
    result["sources"] = _chat_sources(result.get("sources", []))
    return result


def seed_catalog(db):
    for data in CATALOG:
        if not db.scalar(select(Provider).where(Provider.slug == data["slug"])):
            db.add(Provider(**data))
    db.commit()


def provider_dict(p):
    result = {
        k: getattr(p, k)
        for k in (
            "id",
            "name",
            "slug",
            "website_url",
            "official_domain",
            "aliases",
            "oauth_support_status",
        )
    }
    # Legacy provisional aliases may contain the original private request.
    if p.slug.startswith("research-"):
        result["aliases"] = []
    return result


def guide_is_stale(data):
    last_checked = data.get("last_verified_at")
    if not last_checked:
        return True
    try:
        timestamp = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    return timestamp < now() - timedelta(days=max(1, settings.guide_freshness_days))


def owned(db, workspace_id, owner):
    w = db.get(Workspace, workspace_id)
    if not w or w.owner != owner:
        raise HTTPException(404, "Chat not found")
    return w


def owned_thread(db, thread_id, owner):
    t = db.get(ConversationThread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")
    owned(db, t.workspace_id, owner)
    return t


def thread_dict(t, db=None):
    result = {
        k: getattr(t, k)
        for k in (
            "id",
            "workspace_id",
            "type",
            "step_id",
            "guide_version_id",
            "parent_thread_id",
            "title",
            "created_at",
        )
    }
    if db is not None and t.step_id:
        step = db.get(GuideStep, t.step_id)
        result["step_stable_key"] = step.stable_key if step else None
    return result


def message_dict(m):
    return {
        k: getattr(m, k)
        for k in (
            "id",
            "thread_id",
            "role",
            "content",
            "status",
            "citations",
            "created_at",
        )
    }


def step_dict(db, s, public=False):
    data = {
        **s.data,
        "id": s.id,
        "stable_key": s.stable_key,
        "position": s.position,
        "status": s.status,
    }
    if not public:
        data["notes"] = [
            {"id": n.id, "content": n.content}
            for n in db.scalars(select(StepNote).where(StepNote.step_id == s.id))
        ]
    return data


def guide_dict(db, w, public=False, version_id=None):
    g = (
        db.get(GuideVersion, version_id or w.active_guide_version_id)
        if (version_id or w.active_guide_version_id)
        else None
    )
    if not g:
        raise HTTPException(404, "Guide not ready")
    p = db.get(Provider, w.provider_id)
    steps = [
        step_dict(db, s, public)
        for s in db.scalars(
            select(GuideStep)
            .where(GuideStep.guide_version_id == g.id)
            .order_by(GuideStep.position)
        )
    ]
    data = {
        **g.data,
        "id": g.id,
        "version_number": g.version_number,
        "provider": provider_dict(p),
        "steps": steps,
        "sources": [source_link(source) for source in g.data.get("sources", [])],
        "share_slug": w.share_slug,
        "created_at": g.created_at,
        "last_verified_at": g.data.get("last_verified_at"),
        "guide_is_stale": guide_is_stale(g.data),
        "freshness_days": settings.guide_freshness_days,
        "next_best_action": next(
            (
                s["title"]
                for s in steps
                if s["status"] not in ("completed", "not_applicable")
            ),
            "Review launch readiness and verify the completed integration.",
        ),
    }
    # Upgrade existing seeded versions only where content and provenance still
    # match the reviewed seed. User/research changes retain their own evidence.
    if p and p.slug in {"github", "slack", "google-drive"}:
        reviewed = seed_guide(p.slug).model_dump(mode="json")
        reviewed_steps = {item["id"]: item for item in reviewed["steps"]}
        for item in steps:
            original = reviewed_steps.get(item.get("stable_key"))
            if (original and not item.get("citations")
                    and item.get("instructions") == original["instructions"]
                    and set(item.get("source_ids", [])) == set(original["source_ids"])):
                item["citations"] = original["citations"]
        if not data.get("citations"):
            data["citations"] = [citation for citation in reviewed["citations"]
                                 if data.get(citation["field"]) == reviewed[citation["field"]]
                                 and set(citation["source_ids"]) <= {source["id"] for source in data["sources"]}]
    # Once the developer supplied a scoped answer, missing provider evidence is
    # a research limitation, not another request for the same requirements.
    scoped_request = "User clarification:" in (w.capabilities or "")
    needs_clarification = (not steps or bool(data.get("clarification_questions"))) and data.get("oauth_support_status") != "unsupported" and not scoped_request
    questions = data.get("clarification_questions") or [
        item for item in data.get("uncertainties", []) if item.strip().endswith("?")
    ]
    anchor = db.scalar(
        select(Message).join(ConversationThread, Message.thread_id == ConversationThread.id)
        .where(ConversationThread.workspace_id == w.id, ConversationThread.type == "main",
               Message.created_at <= g.created_at)
        .order_by(Message.created_at.desc()).limit(1)
    )
    data["conversation_anchor_message_id"] = anchor.id if anchor and not public else None
    data["clarification_message_id"] = g.data.get("clarification_message_id") if not public else None
    data["clarification_needed"] = needs_clarification
    data["clarification_questions"] = (
        questions[:1] or [f"What would you like your app to do with {p.name}?"]
    ) if needs_clarification else []
    return project_citations(data)


def workspace_dict(db, w):
    steps = (
        list(
            db.scalars(
                select(GuideStep).where(
                    GuideStep.guide_version_id == w.active_guide_version_id
                )
            )
        )
        if w.active_guide_version_id
        else []
    )
    active_guide = (
        db.get(GuideVersion, w.active_guide_version_id)
        if w.active_guide_version_id
        else None
    )
    complete = sum(s.status in ("completed", "not_applicable") for s in steps)
    main = db.scalar(
        select(ConversationThread).where(
            ConversationThread.workspace_id == w.id, ConversationThread.type == "main"
        )
    )
    return {
        "id": w.id,
        "provider": provider_dict(db.get(Provider, w.provider_id)),
        "title": w.title,
        "use_case": w.use_case,
        "audience": w.audience,
        "capabilities": w.capabilities,
        "status": w.status,
        "active_guide_version_id": w.active_guide_version_id,
        "main_thread_id": main.id if main else None,
        "guide_available": bool(w.active_guide_version_id),
        "guide_is_stale": guide_is_stale(active_guide.data) if active_guide else False,
        "research_needed": not bool(w.active_guide_version_id),
        "resolution_status": "resolved"
        if db.get(Provider, w.provider_id).oauth_support_status != "unknown"
        else "research_needed",
        "progress": {
            "completed": complete,
            "total": len(steps),
            "percent": round(100 * complete / len(steps)) if steps else 0,
        },
        "created_at": w.created_at,
    }


def persist_guide(db, w, guide: Guide):
    data = guide.model_dump(mode="json")
    data["last_verified_at"] = min(
        (source["retrieved_at"] for source in data["sources"]), default=None
    )
    previous = (
        {
            s.stable_key: s
            for s in db.scalars(
                select(GuideStep).where(
                    GuideStep.guide_version_id == w.active_guide_version_id
                )
            )
        }
        if w.active_guide_version_id
        else {}
    )
    version = (
        db.scalar(
            select(func.max(GuideVersion.version_number)).where(
                GuideVersion.workspace_id == w.id
            )
        )
        or 0
    ) + 1
    g = GuideVersion(
        workspace_id=w.id,
        version_number=version,
        data={k: v for k, v in data.items() if k != "steps"},
    )
    db.add(g)
    db.flush()
    source_map = {}
    for src in data["sources"]:
        s = Source(guide_version_id=g.id, data=src)
        db.add(s)
        db.flush()
        source_map[src["id"]] = s.id
        for claim in src.get("claims", []):
            db.add(
                ClaimEvidence(
                    guide_version_id=g.id,
                    source_id=s.id,
                    claim_text=claim,
                    verification_status="documented",
                )
            )
    for pos, step in enumerate(data["steps"]):
        key = step["id"]
        old = previous.get(key)
        s = GuideStep(
            workspace_id=w.id,
            guide_version_id=g.id,
            stable_key=key,
            position=pos,
            status=old.status if old else "not_started",
            data=step,
        )
        db.add(s)
        db.flush()
        for src_id in step["source_ids"]:
            db.add(
                ClaimEvidence(
                    guide_version_id=g.id,
                    step_id=s.id,
                    source_id=source_map[src_id],
                    claim_text=step["description"],
                    verification_status=step["verification_status"],
                )
            )
    w.active_guide_version_id = g.id
    w.status = "ready"
    p = db.get(Provider, w.provider_id)
    if p.slug.startswith("research-"):
        # Replace provisional identity and aliases before any public projection.
        domain = urlsplit(str(guide.provider_website)).hostname or ""
        safe_name = (
            re.sub(r"[^a-z0-9]+", "-", guide.provider_name.lower()).strip("-")[:60]
            or "provider"
        )
        p.slug = f"resolved-{safe_name}-{p.id[:8]}"
        p.official_domain = domain
        p.aliases = [guide.provider_name.lower(), domain]
    p.name = guide.provider_name
    p.website_url = str(guide.provider_website)
    p.oauth_support_status = guide.oauth_support_status
    db.commit()
    return g


def match_providers(db, prompt):
    text = prompt.lower().strip()
    return [
        p
        for p in db.scalars(select(Provider))
        if any(
            re.search(r"(?<![a-z0-9])" + re.escape(a.lower()) + r"(?![a-z0-9])", text)
            for a in [
                p.name,
                p.slug,
                *([] if p.slug.startswith("research-") else p.aliases),
            ]
        )
    ]


def validate_provider_request(prompt):
    # A greeting is not a provider identity; keep it out of the research pipeline.
    greeting = " ".join(prompt.lower().strip(" \t\r\n!.,?").split())
    if not greeting or greeting in {
        "hi",
        "hello",
        "hey",
        "hi there",
        "hello there",
        "hey there",
        "thanks",
        "thank you",
        "good morning",
        "good afternoon",
        "good evening",
        "howdy",
        "greetings",
    }:
        raise HTTPException(
            422,
            "Enter a provider name or website, such as Slack or linear.app.",
        )


def create_workspace(db, owner, body):
    validate_provider_request(body.prompt)
    matches = match_providers(db, body.prompt)
    if len(matches) > 1:
        raise HTTPException(
            409,
            detail={
                "message": "Choose one provider to start an integration.",
                "providers": [provider_dict(p) for p in matches],
            },
        )
    if matches:
        p = matches[0]
    else:
        # The unknown identity is deliberately provisional; grounded research must resolve it.
        label = body.prompt.strip()[:100]
        slug = "research-" + hashlib.sha256(label.lower().encode()).hexdigest()[:16]
        p = db.scalar(select(Provider).where(Provider.slug == slug))
        if not p:
            p = Provider(
                name=label,
                slug=slug,
                website_url="",
                official_domain="",
                aliases=[],
                oauth_support_status="unknown",
            )
            db.add(p)
            db.flush()
    text = body.prompt.lower()
    if re.search(r"\b(external|customers|public)\b", text):
        inferred_audience = "external_customers"
    elif re.search(
        r"\b(internal|my organization|our organization|our company)\b", text
    ):
        inferred_audience = "internal_organization"
    elif re.search(r"\b(personal|my own|my account|my drive)\b", text):
        inferred_audience = "personal"
    else:
        inferred_audience = "unspecified"
    w = Workspace(
        owner=owner,
        provider_id=p.id,
        title=f"{p.name} integration",
        use_case=body.prompt,
        audience=body.audience or inferred_audience,
        capabilities=body.capabilities or body.prompt,
    )
    db.add(w)
    db.flush()
    t = ConversationThread(
        workspace_id=w.id, type="main", title="Integration conversation"
    )
    db.add(t)
    db.flush()
    db.add(Message(thread_id=t.id, role="user", content=body.prompt))
    db.commit()
    if p.slug in ("github", "slack", "google-drive"):
        guide = seed_guide(p.slug)
        guide.assumptions = [
            f"Audience: {w.audience}. Confirm audience and required read/write capabilities before choosing scopes.",
            "This seed describes registration and external distribution requirements; review may differ for personal or internal use.",
        ]
        persist_guide(db, w, guide)
    return w


def context_package(db, t):
    w = db.get(Workspace, t.workspace_id)
    p = db.get(Provider, w.provider_id)
    messages = [
        {"role": m.role, "content": m.content[:10000]}
        for m in db.scalars(
            select(Message)
            .where(Message.thread_id == t.id, Message.status == "completed")
            .order_by(Message.created_at.desc())
            .limit(20)
        )
    ][::-1]
    if t.type == "step":
        step = db.get(GuideStep, t.step_id)
        guide = guide_dict(db, w, version_id=t.guide_version_id)
        raw_sources = [
            s for s in guide["sources"] if s["id"] in step.data["source_ids"]
        ]
        sources = _chat_sources(raw_sources)
        # Only a bounded parent summary; never another step's history.
        parent = list(
            db.scalars(
                select(Message)
                .where(
                    Message.thread_id == t.parent_thread_id,
                    Message.status == "completed",
                )
                .order_by(Message.created_at)
                .limit(6)
            )
        )
        return {
            "provider": p.name,
            "integration_use_case": w.use_case,
            "audience": w.audience,
            "capabilities": w.capabilities,
            "guide_version": t.guide_version_id,
            "selected_step_id": step.id,
            "selected_step_title": step.data["title"],
            "selected_step": step_dict(db, step),
            "relevant_sources": sources,
            "main_conversation_summary": "\n".join(
                message["content"][:600]
                for message in _chat_messages(
                    [{"role": m.role, "content": m.content} for m in parent],
                    raw_sources,
                )
            )[:2500],
            "step_thread_messages": _chat_messages(messages[-20:], raw_sources),
        }
    guide = guide_dict(db, w) if w.active_guide_version_id else None
    raw_sources = guide.get("sources", []) if guide else []
    return {
        "provider": p.name,
        "integration_use_case": w.use_case,
        "audience": w.audience,
        "capabilities": w.capabilities,
        "guide": _chat_guide(guide),
        "main_thread_messages": _chat_messages(messages[-20:], raw_sources),
    }
