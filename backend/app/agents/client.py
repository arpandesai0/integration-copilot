from google import genai
from google.genai import types
from app.config import settings


class AIUnavailable(Exception):
    pass


def client():
    if not settings.google_cloud_project or not settings.gemini_model:
        raise AIUnavailable(
            "Configure GOOGLE_CLOUD_PROJECT and GEMINI_MODEL on the backend to enable live research and conversations."
        )
    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        http_options=types.HttpOptions(
            timeout=int(settings.chat_timeout_seconds * 1000), retry_options=types.HttpRetryOptions(attempts=2)
        ),
    )


def safe_error(exc):
    if isinstance(exc, AIUnavailable):
        return str(exc)
    # Never forward raw SDK errors, request metadata, project IDs, or credentials.
    code = getattr(exc, "code", None)
    if code in (401, 403) or "PERMISSION_DENIED" in str(exc):
        return "Vertex AI access was denied. Check project billing, API enablement, and the authenticated identity’s permissions, then retry."
    if code == 429:
        return "Vertex AI is temporarily rate limited. Wait a moment and retry."
    return "The AI request could not complete. Check backend model configuration and connectivity, then retry."
