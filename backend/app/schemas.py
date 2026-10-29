import re
from enum import Enum
from typing import Literal
from pydantic.json_schema import SkipJsonSchema
from pydantic import BaseModel, Field, HttpUrl, model_validator, field_validator


class StepStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"
    needs_verification = "needs_verification"
    not_applicable = "not_applicable"


class Actor(str, Enum):
    developer = "developer"
    agent = "agent"
    human = "human"
    administrator = "administrator"
    provider = "provider"


class Verification(str, Enum):
    documented = "documented"
    tested = "tested"
    inferred = "inferred"
    unverified = "unverified"


class EvidenceSource(BaseModel):
    id: str
    title: str
    url: HttpUrl
    publisher: str = ""
    source_type: str = "official_documentation"
    retrieved_at: str
    claims: list[str] = Field(default_factory=list)
    excerpt: str | None = Field(default=None, max_length=240)
    text_fragment_url: HttpUrl | None = None
    excerpt_verified: bool = False
    step_text_fragment_urls: SkipJsonSchema[dict[str, HttpUrl]] = Field(
        default_factory=dict
    )


class StepCitation(BaseModel):
    field: Literal["description", "instructions", "warnings"]
    index: int | None = Field(default=None, ge=0)
    source_ids: list[str] = Field(min_length=1)
    scope: Literal["claim", "step"] = "claim"


class GuideCitation(BaseModel):
    field: Literal["summary", "recommended_auth_path", "approval_requirement", "prerequisites", "approval_materials", "while_waiting", "uncertainties"]
    index: int | None = Field(default=None, ge=0)
    source_ids: list[str] = Field(min_length=1)


def validate_citations(owner, citations, scalar_fields, source_ids):
    for citation in citations:
        if not set(citation.source_ids) <= set(source_ids):
            raise ValueError("Unknown citation evidence")
        if citation.field in scalar_fields:
            if citation.index is not None:
                raise ValueError("Scalar citations cannot have an index")
        elif citation.index is None or citation.index >= len(getattr(owner, citation.field)):
            raise ValueError("Citation index is missing or out of range")


class Step(BaseModel):
    id: str
    title: str
    description: str
    why_it_matters: str = ""
    instructions: list[str]
    estimated_minutes: int | None = Field(default=None, ge=0)
    actor: Actor = Actor.developer
    status: StepStatus = StepStatus.not_started
    blocking: bool = True
    source_ids: list[str] = Field(default_factory=list)
    verification_status: Verification = Verification.unverified
    warnings: list[str] = Field(default_factory=list)
    action_url: HttpUrl | None = None
    citations: list[StepCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def citation_evidence(self):
        validate_citations(self, self.citations, {"description"}, self.source_ids)
        return self


class Blocker(BaseModel):
    description: str
    impact: str
    resolution: str
    human_required: bool = True
    source_ids: list[str] = Field(default_factory=list)


class Guide(BaseModel):
    provider_name: str
    provider_website: HttpUrl
    oauth_support_status: Literal["supported", "unsupported", "unknown"] = "unknown"
    authentication_method: Literal["oauth2", "oidc", "oidc_sdk", "saml", "api_key", "hmac", "other", "unknown"] = "oauth2"
    summary: str
    clarification_questions: list[str] = Field(default_factory=list, max_length=3)
    recommended_auth_path: str
    difficulty: str
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_approval_days: int | None = Field(default=None, ge=0)
    setup_confidence: str = "unknown"
    approval_confidence: str = "unknown"
    assumptions: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    approval_requirement: str
    approval_materials: list[str] = Field(default_factory=list)
    while_waiting: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    steps: list[Step]
    sources: list[EvidenceSource]
    citations: list[GuideCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence(self):
        if self.oauth_support_status == "unsupported" and self.steps and self.authentication_method in {"oauth2", "oidc"}:
            raise ValueError(
                "Unsupported OAuth providers cannot have OAuth setup steps"
            )
        ids = {s.id for s in self.sources}
        if len(ids) != len(self.sources):
            raise ValueError("Duplicate source IDs")
        if len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("Duplicate step IDs")
        validate_citations(self, self.citations, {"summary", "recommended_auth_path", "approval_requirement"}, ids)
        for step in self.steps:
            if not set(step.source_ids) <= ids:
                raise ValueError("Unknown step evidence")
            if step.verification_status == Verification.tested:
                raise ValueError("Research cannot establish tested status")
            if (
                step.verification_status == Verification.documented
                and not step.source_ids
            ):
                raise ValueError("Documented steps require evidence")
        for blocker in self.blockers:
            if not set(blocker.source_ids) <= ids:
                raise ValueError("Unknown blocker evidence")
        return self


class SourceReference(BaseModel):
    """Model-generated claims reference server-owned source metadata by ID."""

    id: str
    claims: list[str] = Field(default_factory=list)
    excerpt: str | None = Field(default=None, max_length=240)
    # Accept old full-source responses without asking the model to copy opaque URLs.
    url: SkipJsonSchema[HttpUrl | None] = None


class OAuthSupportEvidence(BaseModel):
    """Concrete evidence for the provider acting as the OAuth authorization server."""

    source_id: str
    authorization_url: HttpUrl
    token_url: HttpUrl


class WorkflowEvidence(BaseModel):
    source_id: str
    excerpt: str = Field(min_length=20, max_length=500)


class GuideDraft(Guide):
    workflow_evidence: WorkflowEvidence | None = None
    oauth_evidence: OAuthSupportEvidence | None = None
    steps: list[Step] = Field(max_length=6)
    sources: list[SourceReference] = Field(max_length=8)


class SecretSafeInput(BaseModel):
    @field_validator("prompt", "content", "capabilities", check_fields=False)
    @classmethod
    def avoid_credentials(cls, value):
        if value is None:
            return value
        patterns = [
            r'(?i)(?:client[_ -]?secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\s*[:=]\s*["\']?[A-Za-z0-9_./+-]{12,}',
            r"-----BEGIN (?:RSA )?PRIVATE KEY-----",
            r"\bxox[baprs]-[A-Za-z0-9-]{12,}",
            r"\bgh[pousr]_[A-Za-z0-9]{20,}",
        ]
        if any(re.search(pattern, value) for pattern in patterns):
            raise ValueError(
                "Do not submit credentials or client secrets. Remove sensitive values and describe the configuration instead."
            )
        return value


class CreateChat(SecretSafeInput):
    prompt: str = Field(min_length=1, max_length=3000)
    audience: str | None = Field(default=None, max_length=100)
    capabilities: str | None = Field(
        default=None,
        max_length=3000,
    )


class CreateThread(BaseModel):
    type: Literal["main", "step"] = "step"
    step_id: str | None = None
    parent_thread_id: str | None = None
    title: str | None = Field(default=None, max_length=120)


class SendMessage(SecretSafeInput):
    content: str = Field(min_length=1, max_length=12000)


class UpdateStep(BaseModel):
    status: StepStatus


class CreateNote(SecretSafeInput):
    content: str = Field(min_length=1, max_length=3000)
    thread_id: str | None = None
    confirmed: bool = False
