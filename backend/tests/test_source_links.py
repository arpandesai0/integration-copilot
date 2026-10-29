import asyncio
from unittest.mock import AsyncMock
from urllib.parse import unquote, urlsplit

import httpx
import pytest
from pydantic import HttpUrl

from app.schemas import EvidenceSource
from app.seeds.guides import seed_guide
from app.services import source_links


def run(coroutine):
    return asyncio.run(coroutine)


def source(**overrides):
    data = dict(
        id="test",
        title="Official docs",
        url="https://docs.example.com/oauth#redirect",
        retrieved_at="2026-10-28T00:00:00Z",
        claims=["Configure a secure redirect callback URI."],
    )
    return EvidenceSource(**(data | overrides))


def test_fragment_preserves_section_and_encodes_directive_characters():
    url = source_links.passage_url(
        "https://docs.example.com/oauth#redirect:~:text=old",
        "Use read-only scopes, then redirect.",
    )
    assert url.startswith("https://docs.example.com/oauth#redirect:~:text=")
    assert "%2D" in url and "%2C" in url
    assert unquote(url.split("text=", 1)[1]) == "Use read-only scopes, then redirect."
    with pytest.raises(ValueError):
        source_links.passage_url(
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/opaque",
            "An exact excerpt",
        )


def test_all_seed_sources_have_reviewed_passage_links_and_old_versions_upgrade(client):
    for provider in ["github", "slack", "google-drive"]:
        guide = seed_guide(provider)
        assert all(
            s.excerpt and s.excerpt_verified and ":~:text=" in str(s.text_fragment_url)
            for s in guide.sources
        )
        workspace = client.post("/api/v1/workspaces", json={"prompt": provider}).json()
        result = client.get(f"/api/v1/workspaces/{workspace['id']}/guide").json()
        assert all(":~:text=" in s["text_fragment_url"] for s in result["sources"])
    old = {"url": "https://docs.slack.dev/app-management/distribution/"}
    assert source_links.source_link(old)["excerpt_verified"] is True


def test_fabricated_fragments_are_not_projected():
    result = source_links.source_link(
        {
            "url": "https://docs.example.com/oauth",
            "excerpt": "invented",
            "text_fragment_url": "https://evil.example/#:~:text=invented",
        }
    )
    assert "text_fragment_url" not in result
    assert "excerpt" not in result


def test_excerpt_requires_actual_document_match_or_relevant_extracted_sentence():
    document = "Welcome to docs.\nUse a secure redirect callback URI for authorization.\nUnrelated text."
    assert source_links.verified_excerpt(document, "not present", []) is None
    assert (
        source_links.verified_excerpt(
            document, "Use a secure redirect callback URI for authorization.", []
        )
        == "Use a secure redirect callback URI for authorization."
    )
    assert (
        source_links.verified_excerpt(
            document, None, ["Configure secure redirect callback URI"]
        )
        == "Use a secure redirect callback URI for authorization."
    )


def test_live_highlight_is_verified_and_redirect_resolved(monkeypatch):
    monkeypatch.setattr(
        source_links,
        "fetch_document",
        AsyncMock(
            return_value=(
                "https://docs.provider.example/oauth",
                "Use a secure redirect callback URI for authorization.",
            )
        ),
    )
    item = source(
        url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/result",
        excerpt="Use a secure redirect callback URI for authorization.",
        excerpt_verified=True,
        text_fragment_url="https://bad.example/",
    )
    run(source_links.enrich_source(item))
    assert item.excerpt_verified
    assert str(item.text_fragment_url).startswith(
        "https://docs.provider.example/oauth#:~:text="
    )


def test_unverified_or_unavailable_passages_fall_back_without_failing(monkeypatch):
    monkeypatch.setattr(
        source_links,
        "fetch_document",
        AsyncMock(side_effect=httpx.ConnectError("Unavailable")),
    )
    item = source(
        excerpt="Fabricated excerpt",
        excerpt_verified=True,
        text_fragment_url="https://bad.example/",
    )
    run(source_links.enrich_source(item))
    assert (
        not item.excerpt_verified
        and item.excerpt is None
        and item.text_fragment_url is None
    )
    assert str(item.url) == "https://docs.example.com/oauth#redirect"


def test_document_parser_ignores_script_and_style_content():
    parser = source_links.DocumentText()
    parser.feed(
        "<script>fake requirement</script><style>hidden</style><p>Actual <strong>provider</strong> requirement.</p>"
    )
    assert (
        source_links.normalized("".join(parser.parts)) == "Actual provider requirement."
    )


def test_retrieval_pins_validated_ip_and_original_tls_hostname(monkeypatch):
    async def addresses(host):
        assert host == "docs.example.com"
        return ["93.184.216.34"]

    monkeypatch.setattr(source_links, "public_addresses", addresses)
    captured = []

    class Transport:
        async def handle_async_request(self, request):
            captured.append(request)
            return httpx.Response(200, content=b"ok")

        async def aclose(self):
            pass

    transport = source_links.PublicDocumentTransport()
    run(transport.transport.aclose())
    transport.transport = Transport()
    run(
        transport.handle_async_request(
            httpx.Request("GET", "https://docs.example.com/oauth")
        )
    )
    request = captured[0]
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "docs.example.com"
    assert request.extensions["sni_hostname"] == "docs.example.com"
    assert request.headers["connection"] == "close"


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "https://user:pass@example.com", "https://example.com:8443"],
)
def test_unsafe_url_forms_rejected_before_dns(url):
    transport = source_links.PublicDocumentTransport()
    with pytest.raises(ValueError):
        run(transport.handle_async_request(httpx.Request("GET", url)))
    run(transport.aclose())


def test_private_and_mixed_dns_destinations_rejected(monkeypatch):
    async def lookup(*args, **kwargs):
        return [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ]

    async def check():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
        with pytest.raises(ValueError, match="private"):
            await source_links.public_addresses("rebind.example")

    run(check())


def test_enrichment_budget_clears_untrusted_model_fields_beyond_budget(monkeypatch):
    guide = seed_guide("github")
    for item in guide.sources:
        item.url = HttpUrl("https://docs.example.com/oauth")
        item.text_fragment_url = HttpUrl("https://bad.example/")
        item.excerpt_verified = True
    monkeypatch.setattr(
        source_links,
        "fetch_document",
        AsyncMock(side_effect=httpx.ConnectError("Unavailable")),
    )
    run(source_links.enrich_guide_sources(guide))
    assert source_links.fetch_document.await_count == 4
    assert all(
        not s.excerpt_verified and s.text_fragment_url is None for s in guide.sources
    )


def test_contextual_passages_target_the_selected_step_without_model_schema_fields():
    result = source_links.source_link(
        {"url": "https://docs.slack.dev/authentication/installing-with-oauth/"}
    )
    scopes = unquote(result["step_text_fragment_urls"]["scopes"])
    redirect = unquote(result["step_text_fragment_urls"]["redirect-uri"])
    assert "Bot scopes should be added" in scopes
    assert "redirect_uri must use HTTPS" in redirect
    assert scopes != redirect
    assert (
        "step_text_fragment_urls"
        not in EvidenceSource.model_json_schema()["properties"]
    )


def test_dynamic_step_passage_must_match_retrieved_text(monkeypatch):
    from app.schemas import Step

    monkeypatch.setattr(
        source_links,
        "fetch_document",
        AsyncMock(
            return_value=(
                "https://docs.example.com/oauth",
                "Configure the exact redirect callback URI in the dashboard.",
            )
        ),
    )
    item = source(claims=[])
    step = Step(
        id="redirect-uri",
        title="Configure callback",
        description="Configure redirect callback URI",
        instructions=[],
        source_ids=[item.id],
    )
    run(source_links.enrich_source(item, [step]))
    assert item.excerpt_verified
    assert "redirect-uri" in item.step_text_fragment_urls
    assert "Configure%20the%20exact" in str(
        item.step_text_fragment_urls["redirect-uri"]
    )
    assert source_links.source_link(item.model_dump(mode="json"))[
        "step_text_fragment_urls"
    ]
