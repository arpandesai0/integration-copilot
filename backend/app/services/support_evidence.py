"""Keep public OAuth support separate from brand identity or inbound connectors."""

import re
from urllib.parse import urlsplit

from app.schemas import GuideDraft


UNVERIFIED_SUMMARY = (
    "A public OAuth integration for the requested capability could not be verified "
    "from the returned documentation. Product information or connectors to other "
    "services do not establish that this provider offers a public OAuth API."
)


def research_text(value: str) -> str:
    # Quotes from grounded findings may omit Markdown emphasis, not actual words.
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\([A-Z][A-Z0-9-]{1,12}\)", "", value)
    return " ".join(re.sub(r"[^\w]+", " ", value).split()).casefold()


def endpoint_identity(value: str) -> tuple[str, str, str]:
    parsed = urlsplit(value)
    return (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"))


def constrain_oauth_claims(draft: GuideDraft, research: str) -> GuideDraft:
    if draft.authentication_method not in {"oauth2", "oidc"} and draft.steps:
        evidence = draft.workflow_evidence
        source_ids = {source.id for source in draft.sources}
        normalized = research_text(research)
        if (
            draft.authentication_method != "unknown"
            and evidence
            and evidence.source_id in source_ids
            and research_text(evidence.excerpt) in normalized
            and all(step.source_ids for step in draft.steps)
        ):
            return draft
        # A non-OAuth label alone cannot bypass evidence validation.
        return draft.model_copy(update={
            "steps": [],
            "summary": "The requested setup could not be verified from the returned documentation.",
            "recommended_auth_path": "No verified setup path is available yet.",
            "setup_confidence": "unknown",
            "citations": [],
            "clarification_questions": [],
        })
    if draft.oauth_support_status == "unsupported":
        return draft
    if draft.oauth_support_status == "unknown" and not draft.steps:
        return draft
    evidence = draft.oauth_evidence
    research_urls = {
        endpoint_identity(url.rstrip(".,;:)]}"))
        for url in re.findall(r"https?://[^\s<>\"'\`]+", research)
    }
    source_ids = {source.id for source in draft.sources}
    # The synthesis stage cannot promote guesses to support. Endpoint URLs must
    # already occur in the grounded research, with a retained source reference.
    if (
        draft.oauth_support_status == "supported"
        and evidence
        and evidence.source_id in source_ids
        and endpoint_identity(str(evidence.authorization_url)) in research_urls
        and endpoint_identity(str(evidence.token_url)) in research_urls
        and endpoint_identity(str(evidence.authorization_url)) != endpoint_identity(str(evidence.token_url))
    ):
        return draft
    return draft.model_copy(
        update={
            "oauth_support_status": "unknown",
            "summary": UNVERIFIED_SUMMARY,
            "recommended_auth_path": "No verified public OAuth setup path.",
            "setup_confidence": "unknown",
            "approval_confidence": "unknown",
            "estimated_setup_minutes": None,
            "estimated_approval_days": None,
            "assumptions": [],
            "prerequisites": [],
            "approval_requirement": "Not established from the available documentation.",
            "approval_materials": [],
            "while_waiting": [],
            "uncertainties": [
                f"What would you like your app to do with {draft.provider_name}?",
                "Official documentation of the provider's own OAuth authorization and token endpoints is needed before generating setup instructions.",
            ],
            "steps": [],
            "blockers": [],
            "citations": [],
            "sources": [source.model_copy(update={"claims": [], "excerpt": None}) for source in draft.sources],
        }
    )
