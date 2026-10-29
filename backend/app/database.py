from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    create_engine,
    String,
    Text,
    ForeignKey,
    JSON,
    DateTime,
    Integer,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from app.config import settings


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    website_url: Mapped[str] = mapped_column(String)
    official_domain: Mapped[str] = mapped_column(String)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    oauth_support_status: Mapped[str] = mapped_column(String, default="unknown")


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner: Mapped[str] = mapped_column(String, index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"))
    title: Mapped[str] = mapped_column(String)
    use_case: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String, default="external_customers")
    capabilities: Mapped[str] = mapped_column(
        Text, default="Determine minimum permissions for the requested use case"
    )
    status: Mapped[str] = mapped_column(String, default="not_started")
    active_guide_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    share_slug: Mapped[str] = mapped_column(String, unique=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GuideVersion(Base):
    __tablename__ = "guide_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GuideStep(Base):
    __tablename__ = "guide_steps"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    guide_version_id: Mapped[str] = mapped_column(ForeignKey("guide_versions.id"))
    stable_key: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="not_started")
    data: Mapped[dict] = mapped_column(JSON)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    guide_version_id: Mapped[str] = mapped_column(ForeignKey("guide_versions.id"))
    data: Mapped[dict] = mapped_column(JSON)


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    guide_version_id: Mapped[str] = mapped_column(ForeignKey("guide_versions.id"))
    step_id: Mapped[str | None] = mapped_column(
        ForeignKey("guide_steps.id"), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("sources.id"), nullable=True
    )
    claim_text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String)


class ConversationThread(Base):
    __tablename__ = "threads"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    type: Mapped[str] = mapped_column(String)
    step_id: Mapped[str | None] = mapped_column(
        ForeignKey("guide_steps.id"), nullable=True
    )
    guide_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("guide_versions.id"), nullable=True
    )
    parent_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("threads.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="completed")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResearchRun(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    status: Mapped[str] = mapped_column(String, default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResearchEvent(Base):
    __tablename__ = "research_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StepNote(Base):
    __tablename__ = "step_notes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    step_id: Mapped[str] = mapped_column(ForeignKey("guide_steps.id"))
    thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("threads.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


class PersistedSession(Session):
    def commit(self):
        super().commit()
        from app.metadata_store import schedule_metadata_snapshot

        schedule_metadata_snapshot(engine, Base.metadata)


SessionLocal = sessionmaker(engine, class_=PersistedSession, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
