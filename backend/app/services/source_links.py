"""Verified passage links with bounded, DNS-pinned public-document retrieval."""

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx
from pydantic import HttpUrl

# Short passages checked against official documentation on 2026-10-29.
# These also upgrade existing seed versions without a database migration.
SEED_EXCERPTS = {
    "https://docs.slack.dev/reference/methods/chat.postMessage/": "chat:write",
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps": "GitHub Apps use fine-grained permissions",
    "https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app": "You can register a GitHub App under your personal account",
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app": 'In "Authorization callback URL", type the callback URL of your app.',
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps": "GitHub's OAuth implementation supports the standard authorization code grant type",
    "https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/about-oauth-app-access-restrictions": "Users can request owner approval for OAuth apps they'd like to use",
    "https://docs.slack.dev/authentication/installing-with-oauth/": "The redirect_uri must use HTTPS.",
    "https://docs.slack.dev/authentication/sign-in-with-slack/": "The flow is based on the OpenID Connect standard",
    "https://docs.slack.dev/app-management/distribution/": "apps intended for commercial distribution should be submitted and approved for listing in the Slack Marketplace",
    "https://docs.slack.dev/app-management/quickstart-app-settings/": "Select the Workspace where you'll be developing your app.",
    "https://developers.google.com/workspace/drive/api/guides/api-specific-auth": "Whenever possible, use non-sensitive scopes",
    "https://developers.google.com/workspace/guides/configure-oauth-consent": "Configuring your app's OAuth consent screen defines what is displayed to users and app reviewers",
    "https://developers.google.com/workspace/guides/create-credentials": "Requires your app to request and receive consent from the user.",
    "https://developers.google.com/identity/protocols/oauth2/web-server": "It is designed for applications that can store confidential information and maintain state.",
    "https://developers.google.com/identity/openid-connect/openid-connect": "your application can get permission to use other Google APIs on behalf of the user",
}


# Reuse short reviewed passages for matching steps; other steps retain the page link.
SEED_STEP_EXCERPTS = {
    "https://docs.slack.dev/authentication/sign-in-with-slack/": {
        "create-app": SEED_EXCERPTS[
            "https://docs.slack.dev/authentication/sign-in-with-slack/"
        ]
    },
    "https://docs.slack.dev/authentication/installing-with-oauth/": {
        "scopes": "Bot scopes should be added",
        "redirect-uri": "The redirect_uri must use HTTPS.",
        "authorization": "Your app obtains an access token in three steps:",
        "test-installation": "Your app obtains an access token in three steps:",
    },
    "https://docs.slack.dev/app-management/distribution/": {
        "distribution": SEED_EXCERPTS[
            "https://docs.slack.dev/app-management/distribution/"
        ]
    },
    "https://docs.slack.dev/app-management/quickstart-app-settings/": {
        "create-app": SEED_EXCERPTS[
            "https://docs.slack.dev/app-management/quickstart-app-settings/"
        ]
    },
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps": {
        key: "GitHub Apps use fine-grained permissions"
        for key in ("choose-app", "permissions")
    },
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app": {
        "register-app": "Click New OAuth App.",
        "redirect-uri": SEED_EXCERPTS[
            "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app"
        ],
    },
    "https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app": {
        "register-app": "Click New GitHub App."
    },
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps": {
        "redirect-uri": "The redirect_uri parameter is optional.",
        "test-authorization": SEED_EXCERPTS[
            "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps"
        ],
    },
    "https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/about-oauth-app-access-restrictions": {
        key: SEED_EXCERPTS[
            "https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/about-oauth-app-access-restrictions"
        ]
        for key in ("test-authorization", "distribution")
    },
    "https://developers.google.com/workspace/drive/api/guides/api-specific-auth": {
        "scopes": "Whenever possible, use non-sensitive scopes",
        "test-authorization": "Whenever possible, use non-sensitive scopes",
        "verification": "If you store restricted scope data on servers (or transmit), then you must go through a security assessment.",
    },
    "https://developers.google.com/workspace/guides/configure-oauth-consent": {
        key: SEED_EXCERPTS[
            "https://developers.google.com/workspace/guides/configure-oauth-consent"
        ]
        for key in ("consent", "test-authorization", "verification")
    },
    "https://developers.google.com/workspace/guides/create-credentials": {
        "cloud-project": "Click Application type",
        "redirect-uri": "Under Authorized redirect URIs, click Add URI.",
    },
    "https://developers.google.com/identity/protocols/oauth2/web-server": {
        key: SEED_EXCERPTS[
            "https://developers.google.com/identity/protocols/oauth2/web-server"
        ]
        for key in ("redirect-uri", "test-authorization")
    },
    "https://developers.google.com/identity/openid-connect/openid-connect": {
        "cloud-project": SEED_EXCERPTS[
            "https://developers.google.com/identity/openid-connect/openid-connect"
        ]
    },
}


def normalized(text):
    return " ".join(text.split())


def passage_url(url, excerpt):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Only public HTTPS source links are supported")
    # A grounding redirect is not the page on which the browser highlights text.
    if parsed.hostname == "vertexaisearch.cloud.google.com":
        raise ValueError("Resolve grounding redirects before adding a passage")
    section = parsed.fragment.split(":~:", 1)[0]
    fragment = section + ":~:text=" + quote(excerpt, safe="").replace("-", "%2D")
    return urlunsplit(parsed._replace(fragment=fragment))


def source_link(source):
    """Project existing seeds; preserve only previously verified dynamic excerpts."""
    result = dict(source)
    base = urlunsplit(urlsplit(str(result["url"]))._replace(fragment=""))
    seed = SEED_EXCERPTS.get(base)
    if seed:
        result.update(
            excerpt=seed,
            text_fragment_url=passage_url(str(result["url"]), seed),
            excerpt_verified=True,
        )
        result["step_text_fragment_urls"] = {
            key: passage_url(str(result["url"]), excerpt)
            for key, excerpt in SEED_STEP_EXCERPTS.get(base, {}).items()
        }
    elif not result.get("excerpt_verified"):
        result.pop("text_fragment_url", None)
        result.pop("excerpt", None)
        result.pop("step_text_fragment_urls", None)
    return result


class DocumentText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "li", "h1", "h2", "h3", "div", "tr", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "li", "h1", "h2", "h3", "div", "tr", "br"):
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


async def public_addresses(host):
    try:
        answers = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM),
            timeout=3,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise ValueError("Source DNS unavailable") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or any(
        not ipaddress.ip_address(address).is_global for address in addresses
    ):
        raise ValueError("Source resolves to a private destination")
    return addresses


class PublicDocumentTransport(httpx.AsyncBaseTransport):
    """Connect to the already checked IP; TLS SNI and Host remain the original host."""

    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        parsed = urlsplit(str(request.url))
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Only public HTTPS documentation is allowed")
        addresses = await public_addresses(parsed.hostname)
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers={
                **dict(request.headers),
                "host": parsed.hostname,
                "connection": "close",
            },
            extensions={**request.extensions, "sni_hostname": parsed.hostname},
        )
        return await self.transport.handle_async_request(pinned)

    async def aclose(self):
        await self.transport.aclose()


async def fetch_document(url):
    current = urlunsplit(urlsplit(url)._replace(fragment=""))
    async with httpx.AsyncClient(
        transport=PublicDocumentTransport(),
        timeout=5,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for _ in range(4):
            async with client.stream(
                "GET",
                current,
                headers={
                    "Accept": "text/html,text/plain",
                    "User-Agent": "IntegrationCopilot/0.1 documentation-evidence",
                },
            ) as response:
                if response.is_redirect:
                    current = urljoin(current, response.headers["location"])
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not any(
                    kind in content_type
                    for kind in ("text/html", "text/plain", "text/markdown")
                ):
                    raise ValueError("Source is not a text document")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise ValueError("Source exceeds document size limit")
                parser = DocumentText()
                parser.feed(body.decode("utf-8", errors="replace"))
                return current, "".join(parser.parts)
    raise ValueError("Too many source redirects")


def verified_excerpt(document, candidate, claims):
    text = normalized(document)
    if candidate:
        candidate = normalized(candidate)
        # At most a short citation excerpt, rather than a copied document.
        if 15 <= len(candidate) <= 240 and len(candidate.split()) <= 25:
            match = re.search(re.escape(candidate), text, re.IGNORECASE)
            if match:
                return text[match.start() : match.end()]
    keywords = set(re.findall(r"[a-z]{4,}", " ".join(claims).lower())) - {
        "that",
        "with",
        "this",
        "from",
        "your",
        "have",
        "their",
        "will",
        "must",
    }
    candidates = []
    for paragraph in document.splitlines():
        paragraph = normalized(paragraph)
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            words = sentence.split()
            if 5 <= len(words) <= 25 and len(sentence) <= 240:
                overlap = len(
                    keywords & set(re.findall(r"[a-z]{4,}", sentence.lower()))
                )
                if overlap >= 2:
                    candidates.append((overlap, sentence))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


async def enrich_source(source, steps=()):
    data = source.model_dump(mode="json")
    data.pop("text_fragment_url", None)
    data["excerpt_verified"] = False
    mapped = source_link(data)
    if mapped.get("text_fragment_url"):
        source.excerpt = mapped["excerpt"]
        source.text_fragment_url = HttpUrl(mapped["text_fragment_url"])
        source.excerpt_verified = True
        source.step_text_fragment_urls = {
            key: HttpUrl(url)
            for key, url in mapped.get("step_text_fragment_urls", {}).items()
        }
        return
    candidate = source.excerpt
    source.excerpt = None
    source.text_fragment_url = None
    source.excerpt_verified = False
    source.step_text_fragment_urls = {}
    try:
        final_url, document = await asyncio.wait_for(
            fetch_document(str(source.url)), timeout=7
        )
        for step in steps:
            excerpt_for_step = verified_excerpt(
                document, None, [step.description, *step.instructions]
            )
            if excerpt_for_step:
                source.step_text_fragment_urls[step.id] = HttpUrl(
                    passage_url(final_url, excerpt_for_step)
                )
        source.excerpt_verified = bool(source.step_text_fragment_urls)
        excerpt = verified_excerpt(document, candidate, source.claims)
        if excerpt:
            source.excerpt = excerpt
            source.text_fragment_url = HttpUrl(passage_url(final_url, excerpt))
            source.excerpt_verified = True
    except (ValueError, OSError, httpx.HTTPError, asyncio.TimeoutError):
        pass  # A normal source/section link is preferable to a fabricated highlight.


async def enrich_guide_sources(guide):
    # Bound work per research run; lack of a passage must never fail guide generation.
    for index, source in enumerate(guide.sources):
        source.text_fragment_url = None
        source.excerpt_verified = False
        source.step_text_fragment_urls = {}
        if index >= 4:
            source.excerpt = None
    await asyncio.gather(
        *(
            enrich_source(
                source, [step for step in guide.steps if source.id in step.source_ids]
            )
            for source in guide.sources[:4]
        )
    )
