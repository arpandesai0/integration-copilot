from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from app.config import settings
from app.database import (
    Base,
    engine,
    SessionLocal,
    ResearchRun,
    ResearchEvent,
    Workspace,
    Message,
)
from app.services.core import seed_catalog
from app.api import router


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_catalog(db)
        for message in db.scalars(select(Message).where(Message.status == "streaming")):
            message.status = "incomplete"
        # Local tasks cannot survive process restart; make this observable and retryable.
        for run in db.scalars(
            select(ResearchRun).where(ResearchRun.status == "running")
        ):
            run.status = "failed"
            run.error_message = (
                "Research was interrupted by a server restart. Please retry."
            )
            db.add(
                ResearchEvent(
                    research_run_id=run.id,
                    event_type="research_failed",
                    payload={"message": run.error_message},
                )
            )
            w = db.get(Workspace, run.workspace_id)
            w.status = "research_failed"
        db.commit()
    yield


app = FastAPI(title="Integration Copilot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


@app.middleware("http")
async def check_origin(request: Request, call_next):
    if request.method in ("POST", "PATCH", "DELETE", "PUT"):
        origin = request.headers.get("origin")
        if origin and origin != settings.frontend_url:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        if (
            request.headers.get("content-length", "").isdigit()
            and int(request.headers["content-length"]) > 32000
        ):
            return JSONResponse({"detail": "Request is too large"}, status_code=413)
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/"):
        # Deleted chats and revoked share links must not survive in HTTP caches.
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai_configured": bool(settings.google_cloud_project and settings.gemini_model),
    }


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Pydantic normally echoes rejected input; keep possible credentials out of responses.
    return JSONResponse(
        {
            "detail": [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
        status_code=422,
    )


app.include_router(router)
