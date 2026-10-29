"""Conservative seed requirements reviewed against official docs on 2026-10-28.
No provider flow has been executed; documented never means tested.
"""

from app.schemas import Guide
from app.services.source_links import source_link

CHECKED = "2026-10-28T00:00:00Z"
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
            "Hands-on setup and approval duration have not been established for your application."
        ],
        "blockers": [],
    }
    if slug == "github":
        data = {
            **common,
            "provider_name": "GitHub",
            "provider_website": "https://github.com",
            "summary": "Choose GitHub App or OAuth App before registering. GitHub generally recommends GitHub Apps for fine-grained repository permissions and installation-based access.",
            "recommended_auth_path": "Evaluate a GitHub App first; use a custom OAuth App when its user-delegated access model matches your requirements. No managed OAuth service is assumed.",
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
                    "Choose GitHub App or OAuth App",
                    "Match the permission model to the product before registering.",
                    [
                        "Compare fine-grained GitHub App permissions with OAuth user scopes.",
                        "Prefer repository-scoped installations when that fits your integration.",
                    ],
                    ["github-types"],
                ),
                step(
                    "register-app",
                    "Register the application",
                    "Register the chosen application under the appropriate account.",
                    [
                        "For the recommended GitHub App path, open Developer settings → GitHub Apps → New GitHub App and configure its permissions and installation audience.",
                        "For the OAuth App path, open Developer settings → OAuth Apps → New OAuth App.",
                        "Provide the application details and callback URLs for your chosen path.",
                    ],
                    ["github-register", "github-app-register"],
                    "https://github.com/settings/developers",
                ),
                step(
                    "redirect-uri",
                    "Configure the authorization callback",
                    "Your backend must receive and validate the authorization result.",
                    [
                        "Configure the callback endpoint for your deployed backend.",
                        "Implement state validation and the authorization-code exchange server-side.",
                        "Keep client secrets outside browser code.",
                    ],
                    ["github-register", "github-flow"],
                ),
                step(
                    "permissions",
                    "Select minimal permissions",
                    "Permissions should match the operations your customers need.",
                    [
                        "List required repository and account operations.",
                        "Select minimal GitHub App permissions or OAuth scopes for the chosen path.",
                    ],
                    ["github-types", "github-flow"],
                ),
                step(
                    "test-authorization",
                    "Test account and organization access",
                    "Exercise the actual selected authorization path before launch.",
                    [
                        "Authorize using a test account and confirm the minimum API operation succeeds.",
                        "Test denied consent and organization restrictions.",
                        "Do not mark this step complete until you execute those checks.",
                    ],
                    ["github-flow", "github-org"],
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
            "provider_name": "Slack",
            "provider_website": "https://slack.com",
            "summary": "Create a Slack app, choose bot or user permissions, configure an HTTPS callback, and implement OAuth v2 installation. Distribution and Marketplace review depend on your rollout.",
            "recommended_auth_path": "Custom Slack app registration with OAuth v2 for customer workspace installations. Reuse an existing app only if you control it and its permissions match.",
            "difficulty": "Moderate; distribution adds requirements",
            "prerequisites": [
                "A Slack account and a development workspace in which app installation is permitted.",
                "An HTTPS callback endpoint for OAuth.",
            ],
            "approval_requirement": "Unlisted distribution can support early-customer pilots. Apps intended for commercial distribution should be submitted and approved for Slack Marketplace listing. Workspace admin installation policies apply separately.",
            "sources": [
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
                    "Create your Slack app",
                    "Start with an app in a development workspace.",
                    [
                        "Create a new app and choose your development workspace.",
                        "Confirm the workspace permits your app installation.",
                    ],
                    ["slack-create"],
                    "https://api.slack.com/apps",
                ),
                step(
                    "scopes",
                    "Choose bot and user scopes",
                    "Select only permissions needed by your capabilities.",
                    [
                        "Map product features to Slack methods and scopes.",
                        "Keep bot scopes and user scopes distinct.",
                        "Do not combine Sign in with Slack identity scopes with other scopes in the same flow.",
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
            "provider_name": "Google Drive",
            "provider_website": "https://drive.google.com",
            "summary": "Configure a Google Cloud OAuth client and consent experience, choose the narrowest Drive scopes, and assess verification before external launch. Broad restricted scopes can introduce security assessment requirements.",
            "recommended_auth_path": "Custom Google OAuth client for external customer authorization. Prefer drive.file with a file picker when user-selected files satisfy the product.",
            "difficulty": "Scope-dependent; broad Drive access adds review",
            "prerequisites": [
                "A Google Cloud project with Drive API enabled and permission to configure OAuth.",
                "A configured OAuth consent experience and web application redirect endpoint.",
            ],
            "approval_requirement": "Verification depends on audience and requested scopes. Sensitive and restricted scopes add review; restricted data stored or transmitted by servers may require a security assessment. Non-sensitive scopes still have applicable basic verification requirements.",
            "sources": [
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
                    "Prepare your Google Cloud project",
                    "Configure the project that owns your OAuth client.",
                    [
                        "Select a project you control and enable the Drive API.",
                        "Confirm your permissions allow OAuth configuration.",
                    ],
                    ["google-client"],
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
            "register-app": [["github-app-register"], ["github-register"], ["github-register", "github-app-register"]],
            "redirect-uri": [["github-register"], ["github-flow"], ["github-flow"]],
            "permissions": [[], ["github-types", "github-flow"]],
            "test-authorization": [["github-flow"], ["github-org"], []],
            "distribution": [["github-org"], ["github-org", "github-types"]],
        },
        "slack": {s["id"]: [s["source_ids"] for _ in s["instructions"]] for s in data["steps"]},
        "google-drive": {
            "cloud-project": [["google-client"], ["google-client"]],
            "consent": [["google-consent"], ["google-consent"], ["google-consent"]],
            "scopes": [["drive-scopes"], ["drive-scopes"], ["drive-scopes"]],
            "redirect-uri": [["google-client"], ["google-client", "google-web"], ["google-web"]],
            "test-authorization": [["google-consent", "drive-scopes"], ["google-web"], ["drive-scopes"]],
            "verification": [["drive-scopes"], ["drive-scopes"], ["google-consent"]],
        },
    }[slug]
    if slug == "slack":
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
        "slack": {"summary": ["slack-oauth", "slack-distribution"], "recommended_auth_path": ["slack-oauth"], "approval_requirement": ["slack-distribution"]},
        "google-drive": {"summary": ["drive-scopes", "google-client"], "recommended_auth_path": ["drive-scopes", "google-client"], "approval_requirement": ["drive-scopes"]},
    }[slug]
    data["citations"] = [{"field": field, "source_ids": ids} for field, ids in top_sources.items()]
    return Guide.model_validate(data)
