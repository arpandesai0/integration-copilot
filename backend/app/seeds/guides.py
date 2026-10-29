"""Conservative seed requirements reviewed against official docs on 2026-10-29.
No provider flow has been executed; documented never means tested.
"""

from app.schemas import Guide
from app.services.source_links import source_link

CHECKED = "2026-10-29T00:00:00Z"
CATALOG = [
    {
        "name": "GitHub",
        "slug": "github",
        "official_domain": "github.com",
        "website_url": "https://github.com",
        "aliases": ["github", "github.com"],
        "oauth_support_status": "supported",
    },
    {
        "name": "Slack",
        "slug": "slack",
        "official_domain": "slack.com",
        "website_url": "https://slack.com",
        "aliases": ["slack", "slack.com"],
        "oauth_support_status": "supported",
    },
    {
        "name": "Google Drive",
        "slug": "google-drive",
        "official_domain": "drive.google.com",
        "website_url": "https://drive.google.com",
        "aliases": ["google drive", "gdrive", "drive.google.com", "google-drive"],
        "oauth_support_status": "supported",
    },
]


def source(id, title, url, claim):
    return source_link(
        {
            "id": id,
            "title": title,
            "url": url,
            "retrieved_at": CHECKED,
            "publisher": url.split("/")[2],
            "claims": [claim],
        }
    )


def step(id, title, description, instructions, sources, url=None, warnings=None):
    return {
        "id": id,
        "title": title,
        "description": description,
        "why_it_matters": description,
        "instructions": instructions,
        "source_ids": sources,
        "verification_status": "documented",
        "action_url": url,
        "warnings": warnings or [],
    }


def seed_guide(slug):
    common = {
        "oauth_support_status": "supported",
        "estimated_setup_minutes": None,
        "estimated_approval_days": None,
        "setup_confidence": "unknown",
        "approval_confidence": "unknown",
        "assumptions": [
            "Assumes a web application connecting external customers. Confirm capabilities before selecting permissions."
        ],
        "uncertainties": [
            "Time values are rough planning estimates for this demo, not provider-published SLAs. Actual setup and approval time depends on scopes, distribution, organization policy, and review feedback."
        ],
        "blockers": [],
    }
    if slug == "github":
        data = {
            **common,
            "estimated_setup_minutes": 75,
            "estimated_approval_days": 7,
            "setup_confidence": "inferred",
            "approval_confidence": "inferred",
            "provider_name": "GitHub",
            "provider_website": "https://github.com",
            "summary": "Choose one path based on the job: use Sign in with GitHub through an OAuth App when you only need user login, or use a GitHub App when the product needs repository or organization API access.",
            "recommended_auth_path": "GitHub App for repository and organization integrations. Use Sign in with GitHub through an OAuth App only when the requirement is login without installation-based repository access.",
            "difficulty": "Depends on app type and repository permissions",
            "prerequisites": [
                "A GitHub account; organization permission if registering under an organization.",
                "A web application with a callback endpoint for the selected authorization flow.",
            ],
            "approval_requirement": "App registration, organization authorization policies, and Marketplace listing are separate. Organization restrictions may require an owner to approve access. A Marketplace listing is a separate distribution decision.",
            "sources": [
                source(
                    "github-types",
                    "GitHub Apps and OAuth Apps",
                    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps",
                    "GitHub Apps offer finer permission and repository selection.",
                ),
                source(
                    "github-app-register",
                    "Register a GitHub App",
                    "https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app",
                    "Register a GitHub App with fine-grained permissions.",
                ),
                source(
                    "github-register",
                    "Create an OAuth App",
                    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app",
                    "Registration includes a homepage and authorization callback URL.",
                ),
                source(
                    "github-flow",
                    "Authorize OAuth Apps",
                    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps",
                    "Web authorization exchanges a code for an access token.",
                ),
                source(
                    "github-org",
                    "OAuth App access restrictions",
                    "https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/about-oauth-app-access-restrictions",
                    "Organization owners can restrict OAuth App access.",
                ),
            ],
            "steps": [
                step(
                    "choose-app",
                    "Choose login or GitHub integration access",
                    "Choose one application model before registering; do not implement both by default.",
                    [
                        "For user login only, choose Sign in with GitHub through an OAuth App and request only identity scopes.",
                        "For repository or organization API access, choose a GitHub App with installation-based, fine-grained permissions.",
                    ],
                    ["github-types"],
                ),
                step(
                    "register-app",
                    "Register the GitHub App",
                    "This guide follows the GitHub App path for repository and organization integration access.",
                    [
                        "Open Developer settings → GitHub Apps → New GitHub App.",
                        "Configure the app identity, installation audience, and callback URL.",
                        "If your product is login-only, stop and use the separate OAuth App flow instead of following the remaining GitHub App steps.",
                    ],
                    ["github-types", "github-app-register"],
                    "https://github.com/settings/developers",
                ),
                step(
                    "redirect-uri",
                    "Configure GitHub App callbacks",
                    "Your backend must handle GitHub App installation and user authorization callbacks securely.",
                    [
                        "Configure the GitHub App callback URL for your deployed backend.",
                        "If the app acts on behalf of a user, implement state validation and the user authorization-code exchange server-side.",
                        "Keep the GitHub App private key and client secret outside browser code.",
                    ],
                    ["github-app-register", "github-types"],
                ),
                step(
                    "permissions",
                    "Select minimal permissions",
                    "Permissions should match the operations your customers need.",
                    [
                        "List required repository and account operations.",
                        "Select the minimum GitHub App repository, organization, and account permissions required by those operations.",
                    ],
                    ["github-types", "github-app-register"],
                ),
                step(
                    "test-authorization",
                    "Test account and organization access",
                    "Exercise the actual selected authorization path before launch.",
                    [
                        "Install the GitHub App on a test account or organization and select only the repositories needed for the test.",
                        "Confirm the minimum API operation succeeds, then test denied installation or organization restrictions.",
                        "Do not mark this step complete until you execute those checks.",
                    ],
                    ["github-types", "github-org"],
                ),
                step(
                    "distribution",
                    "Review organization access and distribution",
                    "Customer organization policies can block installation.",
                    [
                        "Check whether target organizations restrict app access.",
                        "Separate organization owner approval from optional Marketplace listing.",
                    ],
                    ["github-org", "github-types"],
                ),
            ],
        }
    elif slug == "slack":
        data = {
            **common,
            "estimated_setup_minutes": 90,
            "estimated_approval_days": 10,
            "setup_confidence": "inferred",
            "approval_confidence": "inferred",
            "provider_name": "Slack",
            "provider_website": "https://slack.com",
            "summary": "Choose one primary flow: use Sign in with Slack through OpenID Connect for login, or install a Slack app with OAuth v2 when the product needs workspace API access.",
            "recommended_auth_path": "Slack app installation with OAuth v2 for workspace API access. Use Sign in with Slack only for login, in a separate OpenID Connect flow with openid, profile, and email scopes.",
            "difficulty": "Moderate; distribution adds requirements",
            "prerequisites": [
                "A Slack account and a development workspace in which app installation is permitted.",
                "An HTTPS callback endpoint for OAuth.",
            ],
            "approval_requirement": "Unlisted distribution can support early-customer pilots. Apps intended for commercial distribution should be submitted and approved for Slack Marketplace listing. Workspace admin installation policies apply separately.",
            "sources": [
                source(
                    "slack-signin",
                    "Sign in with Slack",
                    "https://docs.slack.dev/authentication/sign-in-with-slack/",
                    "Sign in with Slack is an OpenID Connect login flow and its scopes must not be combined with Slack app API scopes in one authorization flow.",
                ),
                source(
                    "slack-oauth",
                    "Install with OAuth",
                    "https://docs.slack.dev/authentication/installing-with-oauth/",
                    "Slack uses OAuth v2 and HTTPS redirect URLs.",
                ),
                source(
                    "slack-distribution",
                    "App lifecycle and distribution",
                    "https://docs.slack.dev/app-management/distribution/",
                    "Unlisted pilots and commercial Marketplace distribution have different requirements.",
                ),
                source(
                    "slack-message",
                    "chat.postMessage method",
                    "https://docs.slack.dev/reference/methods/chat.postMessage/",
                    "Sending a message as a bot with chat.postMessage requires chat:write; the bot must have access to the target channel.",
                ),
                source(
                    "slack-create",
                    "Create a Slack app",
                    "https://docs.slack.dev/app-management/quickstart-app-settings/",
                    "Slack apps are created and configured for a development workspace.",
                ),
            ],
            "steps": [
                step(
                    "create-app",
                    "Choose the flow and create your Slack app",
                    "Choose login or workspace API access before configuring the app.",
                    [
                        "For login only, use Sign in with Slack through OpenID Connect with openid, profile, and email scopes.",
                        "For workspace data or actions, use Slack app installation with OAuth v2; the remaining steps follow this path.",
                        "Do not combine Sign in with Slack scopes and Slack app API scopes in the same OAuth flow.",
                        "Create a new app and choose your development workspace.",
                        "Confirm the workspace permits your app installation.",
                    ],
                    ["slack-signin", "slack-oauth", "slack-create"],
                    "https://api.slack.com/apps",
                ),
                step(
                    "scopes",
                    "Choose bot and user scopes",
                    "Select only permissions needed by your capabilities.",
                    [
                        "Map product features to Slack methods and scopes.",
                        "Keep bot scopes and user scopes distinct.",
                        "Keep this installation flow separate from any Sign in with Slack login flow.",
                        "For chat.postMessage as a bot, request chat:write and give the bot access to the target channel. Choose additional permissions only for additional operations.",
                    ],
                    ["slack-oauth", "slack-message"],
                    "https://api.slack.com/apps",
                ),
                step(
                    "redirect-uri",
                    "Configure OAuth redirect URL",
                    "Slack returns an authorization code to your backend callback.",
                    [
                        "Add an HTTPS Redirect URL under OAuth & Permissions.",
                        "Use the same redirect URI in authorization and token exchange where required.",
                        "For a local backend, use a secured HTTPS development endpoint and register its exact callback.",
                    ],
                    ["slack-oauth"],
                    "https://api.slack.com/apps",
                    warnings=[
                        "Slack requires HTTPS redirect URLs; do not assume plain HTTP localhost is supported."
                    ],
                ),
                step(
                    "authorization",
                    "Implement OAuth v2 installation",
                    "Installations authorize the selected scopes.",
                    [
                        "Send users to the OAuth v2 authorization endpoint with client ID, requested scopes, and state.",
                        "Validate state on callback and exchange the short-lived code server-side.",
                        "Store tokens securely by workspace installation; never paste secrets into this guide.",
                    ],
                    ["slack-oauth"],
                ),
                step(
                    "test-installation",
                    "Test a development installation",
                    "Check installation and the smallest permitted API action.",
                    [
                        "Install to a permitted development workspace.",
                        "Test denied consent and verify that scopes match actual API access.",
                    ],
                    ["slack-oauth"],
                ),
                step(
                    "distribution",
                    "Prepare distribution and Marketplace review",
                    "Plan rollout according to Slack’s distribution requirements.",
                    [
                        "Review Manage Distribution requirements for installs outside your development workspace.",
                        "Use unlisted distribution only within its documented early-pilot purpose.",
                        "Prepare Marketplace submission for commercial distribution; do not infer an approval date.",
                    ],
                    ["slack-distribution"],
                    "https://docs.slack.dev/app-management/distribution/",
                ),
            ],
        }
    else:
        data = {
            **common,
            "estimated_setup_minutes": 120,
            "estimated_approval_days": 15,
            "setup_confidence": "inferred",
            "approval_confidence": "inferred",
            "provider_name": "Google Drive",
            "provider_website": "https://drive.google.com",
            "summary": "Choose the flow by purpose: use Sign in with Google through OpenID Connect for login, or request Drive OAuth scopes when the product needs access to a user's files.",
            "recommended_auth_path": "Google Drive OAuth authorization for file access, preferably drive.file with Google Picker when user-selected files are sufficient. Use Sign in with Google alone only for login.",
            "difficulty": "Scope-dependent; broad Drive access adds review",
            "prerequisites": [
                "A Google Cloud project with Drive API enabled and permission to configure OAuth.",
                "A configured OAuth consent experience and web application redirect endpoint.",
            ],
            "approval_requirement": "Verification depends on audience and requested scopes. Sensitive and restricted scopes add review; restricted data stored or transmitted by servers may require a security assessment. Non-sensitive scopes still have applicable basic verification requirements.",
            "sources": [
                source(
                    "google-signin",
                    "Sign in with Google using OpenID Connect",
                    "https://developers.google.com/identity/openid-connect/openid-connect",
                    "OpenID Connect authenticates the user; Google API access depends on the additional authorization scopes requested and granted.",
                ),
                source(
                    "drive-scopes",
                    "Choose Google Drive API scopes",
                    "https://developers.google.com/workspace/drive/api/guides/api-specific-auth",
                    "drive.file is non-sensitive; broad Drive scopes are restricted.",
                ),
                source(
                    "google-consent",
                    "Configure OAuth consent",
                    "https://developers.google.com/workspace/guides/configure-oauth-consent",
                    "Configure branding, audience, and data access for your app.",
                ),
                source(
                    "google-client",
                    "Create access credentials",
                    "https://developers.google.com/workspace/guides/create-credentials",
                    "Create a web application OAuth client and authorized redirect URIs.",
                ),
                source(
                    "google-web",
                    "OAuth 2.0 for web server applications",
                    "https://developers.google.com/identity/protocols/oauth2/web-server",
                    "Web server authorization requires matching redirect URI and secure code exchange.",
                ),
            ],
            "steps": [
                step(
                    "cloud-project",
                    "Choose the flow and prepare your Cloud project",
                    "Choose login or Drive file access before configuring the OAuth client.",
                    [
                        "For login only, use Sign in with Google through OpenID Connect with openid, email, and profile.",
                        "For Drive file access, request the minimum Drive OAuth scopes; the remaining steps follow this path.",
                        "Do not request Drive scopes when the product only needs user authentication.",
                        "Select a project you control and enable the Drive API.",
                        "Confirm your permissions allow OAuth configuration.",
                    ],
                    ["google-signin", "drive-scopes", "google-client"],
                    "https://console.cloud.google.com/",
                ),
                step(
                    "consent",
                    "Configure consent and audience",
                    "Your audience controls who can authorize the app.",
                    [
                        "Configure branding, support contacts, and the intended internal or external audience.",
                        "Use test users while developing an external app.",
                        "Declare the scopes the app will request.",
                    ],
                    ["google-consent"],
                ),
                step(
                    "scopes",
                    "Choose the narrowest Drive scopes",
                    "Scope choice changes both user access and review requirements.",
                    [
                        "Evaluate drive.file for files users explicitly select or share with your app.",
                        "Use broad Drive scopes only when product requirements justify them.",
                        "Check the current scope table before committing to restricted access.",
                    ],
                    ["drive-scopes"],
                ),
                step(
                    "redirect-uri",
                    "Create a web OAuth client and callback",
                    "The redirect URI must match the configured client.",
                    [
                        "Create an OAuth client for a web application.",
                        "Register your backend callback as an authorized redirect URI.",
                        "Implement state validation and server-side code exchange; protect credentials.",
                    ],
                    ["google-client", "google-web"],
                ),
                step(
                    "test-authorization",
                    "Test consent and minimum API access",
                    "Validate the chosen audience and scope behavior.",
                    [
                        "Authorize a configured test user and access only the intended files.",
                        "Test denied consent and expired or revoked authorization.",
                        "Confirm your app does not require unnecessarily broad scopes.",
                    ],
                    ["google-consent", "drive-scopes", "google-web"],
                ),
                step(
                    "verification",
                    "Assess verification and launch requirements",
                    "External launch depends on scope and policy compliance.",
                    [
                        "Review basic, sensitive, or restricted verification requirements for your actual scope selection.",
                        "If restricted data is stored or transmitted server-side, assess security-assessment obligations.",
                        "Prepare required branding, policy materials, and scope justifications; timing remains unknown.",
                    ],
                    ["drive-scopes", "google-consent"],
                ),
            ],
        }
    # Reviewed field-level mappings: never fan out multi-source steps arbitrarily.
    instruction_sources = {
        "github": {
            "choose-app": [["github-types"], ["github-types"]],
            "register-app": [["github-app-register"], ["github-app-register"], ["github-types"]],
            "redirect-uri": [["github-app-register"], ["github-types"], ["github-app-register"]],
            "permissions": [[], ["github-types", "github-app-register"]],
            "test-authorization": [["github-types"], ["github-org"], []],
            "distribution": [["github-org"], ["github-org", "github-types"]],
        },
        "slack": {s["id"]: [s["source_ids"] for _ in s["instructions"]] for s in data["steps"]},
        "google-drive": {
            "cloud-project": [["google-signin"], ["drive-scopes"], ["google-signin", "drive-scopes"], ["google-client"], ["google-client"]],
            "consent": [["google-consent"], ["google-consent"], ["google-consent"]],
            "scopes": [["drive-scopes"], ["drive-scopes"], ["drive-scopes"]],
            "redirect-uri": [["google-client"], ["google-client", "google-web"], ["google-web"]],
            "test-authorization": [["google-consent", "drive-scopes"], ["google-web"], ["drive-scopes"]],
            "verification": [["drive-scopes"], ["drive-scopes"], ["google-consent"]],
        },
    }[slug]
    if slug == "slack":
        instruction_sources["create-app"] = [["slack-signin"], ["slack-oauth"], ["slack-signin", "slack-oauth"], ["slack-create"], ["slack-create"]]
        instruction_sources["scopes"] = [["slack-oauth"], ["slack-oauth"], ["slack-oauth"], ["slack-message"]]
    for item in data["steps"]:
        item["citations"] = [
            {"field": "instructions", "index": index, "source_ids": ids}
            for index, ids in enumerate(instruction_sources[item["id"]]) if ids
        ]
        item["citations"] += [
            {"field": "warnings", "index": index, "source_ids": item["source_ids"]}
            for index in range(len(item["warnings"]))
        ]
    top_sources = {
        "github": {"summary": ["github-types"], "recommended_auth_path": ["github-types"], "approval_requirement": ["github-org", "github-types"]},
        "slack": {"summary": ["slack-signin", "slack-oauth"], "recommended_auth_path": ["slack-signin", "slack-oauth"], "approval_requirement": ["slack-distribution"]},
        "google-drive": {"summary": ["google-signin", "drive-scopes"], "recommended_auth_path": ["google-signin", "drive-scopes"], "approval_requirement": ["drive-scopes"]},
    }[slug]
    step_minutes = {
        "github": [10, 15, 15, 15, 10, 10],
        "slack": [15, 15, 15, 20, 10, 15],
        "google-drive": [20, 20, 20, 20, 20, 20],
    }[slug]
    for item, minutes in zip(data["steps"], step_minutes, strict=True):
        item["estimated_minutes"] = minutes
    data["citations"] = [{"field": field, "source_ids": ids} for field, ids in top_sources.items()]
    return Guide.model_validate(data)
