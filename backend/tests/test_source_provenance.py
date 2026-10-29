import asyncio
import time

import pytest

from app.services import source_provenance


def test_domain_alignment_uses_hostname_boundaries_not_titles_or_paths():
    aligned = source_provenance.provider_domain_aligned
    assert aligned("https://docs.vendor.com/oauth", "https://www.vendor.com/")
    assert aligned("https://vendor.com/oauth", "https://vendor.com/")
    assert not aligned("https://notvendor.com/oauth", "https://vendor.com/")
    assert not aligned("https://vendor.com.attacker.org/", "https://vendor.com/")
    assert not aligned("https://attacker.org/vendor.com", "https://vendor.com/")
    assert not aligned("https://vendor.com@attacker.org/", "https://vendor.com/")
    assert not aligned("http://vendor.com/", "https://vendor.com/")
    assert not aligned("https://127.0.0.1/", "https://127.0.0.1/")


def test_resolves_grounding_redirect_and_preserves_original_metadata(monkeypatch):
    source = {"id": "s1", "title": "Search result", "url": "https://vertexaisearch.cloud.google.com/opaque"}
    async def fetch(url):
        assert url == source["url"]
        return "https://docs.vendor.com/oauth", "Official authentication documentation."
    monkeypatch.setattr(source_provenance, "fetch_document", fetch)
    result = asyncio.run(source_provenance.qualify_sources([source], "https://www.vendor.com"))[0]
    assert result["canonical_url"] == "https://docs.vendor.com/oauth"
    assert result["document"] == "Official authentication documentation."
    assert result["provenance_status"] == "provider_domain"
    assert result["url"] == source["url"]
    assert "canonical_url" not in source


def test_official_looking_title_does_not_qualify_other_domain(monkeypatch):
    async def fetch(url):
        return "https://community.example/oauth", "Vendor OAuth guide."
    monkeypatch.setattr(source_provenance, "fetch_document", fetch)
    result = asyncio.run(source_provenance.qualify_sources([
        {"id": "s1", "title": "Official Vendor OAuth Documentation", "url": "https://search.example/result"}
    ], "https://vendor.com"))[0]
    assert result["provenance_status"] == "other_domain"


def test_failed_fetch_remains_unresolved_without_leaking_exception(monkeypatch):
    async def fetch(url):
        raise ValueError("private destination or sensitive transport detail")
    monkeypatch.setattr(source_provenance, "fetch_document", fetch)
    result = asyncio.run(source_provenance.qualify_sources([
        {"id": "s1", "url": "https://vendor.com/oauth"}
    ], "https://vendor.com"))[0]
    assert result["provenance_status"] == "unresolved"
    assert result["canonical_url"] is None
    assert result["document"] is None
    assert "sensitive" not in str(result)


def test_parallel_batch_capped_at_four_and_timeout_cancels_pending(monkeypatch):
    calls, cancelled = [], []
    async def fetch(url):
        calls.append(url)
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled.append(url)
            raise
    monkeypatch.setattr(source_provenance, "fetch_document", fetch)
    started = time.monotonic()
    results = asyncio.run(source_provenance.qualify_sources([
        {"id": str(i), "url": f"https://vendor.com/{i}"} for i in range(7)
    ], "https://vendor.com", timeout_seconds=0.02, max_sources=20))
    assert time.monotonic() - started < 0.5
    assert len(calls) == len(cancelled) == 4
    assert len(results) == 7
    assert all(item["provenance_status"] == "unresolved" for item in results)


def test_no_fetch_with_zero_budget(monkeypatch):
    async def fetch(url):
        raise AssertionError("Must not fetch")
    monkeypatch.setattr(source_provenance, "fetch_document", fetch)
    result = asyncio.run(source_provenance.qualify_sources([
        {"id": "s1", "url": "https://vendor.com"}
    ], "https://vendor.com", timeout_seconds=0))
    assert result[0]["provenance_status"] == "unresolved"
