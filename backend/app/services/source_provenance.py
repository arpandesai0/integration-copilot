"""Bounded source resolution and provider-domain alignment, not claim verification.

A matching domain is useful provenance metadata, but does not prove that a page
supports a claim or that the model resolved the provider identity correctly.
"""

import asyncio
import ipaddress
from urllib.parse import urlsplit

from app.services.source_links import fetch_document


def _hostname(url):
    try:
        parsed = urlsplit(str(url))
        host = (parsed.hostname or "").lower().rstrip(".").encode("idna").decode("ascii")
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            pass
        return host.removeprefix("www.") or None
    except (ValueError, UnicodeError):
        return None


def provider_domain_aligned(source_url, provider_website):
    """Match the provider's exact host or its subdomains; never a title or suffix lookalike."""
    source_host = _hostname(source_url)
    provider_host = _hostname(provider_website)
    return bool(
        source_host
        and provider_host
        and (source_host == provider_host or source_host.endswith("." + provider_host))
    )


async def qualify_sources(sources, provider_website, timeout_seconds=4, max_sources=4):
    """Return input-order metadata copies, resolving at most four public documents.

    Every retrieval uses source_links' IP-pinned, redirect-revalidated transport.
    The entire parallel batch shares one bounded timeout. Unfetched sources remain
    unresolved rather than being promoted to official evidence from their title.
    Callers should remove ``document`` before exposing or persisting public data.
    """
    results = [
        {
            **dict(source),
            "canonical_url": None,
            "provenance_status": "unresolved",
            "document": None,
        }
        for source in sources
    ]
    limit = min(4, max(0, max_sources), len(results))
    budget = min(4, max(0, timeout_seconds))
    if not limit or not budget:
        return results

    async def resolve(index):
        try:
            final_url, document = await fetch_document(str(results[index]["url"]))
            if not _hostname(final_url):
                return
            results[index].update(
                canonical_url=final_url,
                document=document,
                provenance_status=(
                    "provider_domain"
                    if provider_domain_aligned(final_url, provider_website)
                    else "other_domain"
                ),
            )
        except Exception:
            # Retrieval failure is absence of qualified evidence, not evidence of
            # unsupported OAuth, and raw transport errors must not become prose.
            return

    tasks = [asyncio.create_task(resolve(index)) for index in range(limit)]
    try:
        _, pending = await asyncio.wait(tasks, timeout=budget)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return results
