# Build Specification: Integration Copilot

## 0. Instructions to the Coding Agent

You are a senior full-stack engineer and product designer building a polished MVP for an Associate Product Manager take-home assignment.

**Build the actual working application, not just a prototype, mockup, or architecture document.**

The product is called **Integration Copilot**.

It helps developers and AI agent builders figure out how to create, configure, test, distribute, and obtain approval for OAuth applications across third-party providers.

The core interaction is a **Braintrust-inspired three-panel workspace** consisting of:

1. A left sidebar containing integrations, navigation, and setup steps.
2. A central conversation and actionable OAuth guide.
3. A right-side contextual conversation for discussing individual setup steps.

Developers can ask questions about an individual step without disrupting the main conversation. These discussions should persist, support multiple questions, and remain attached to the relevant step.

Prioritize a functional end-to-end experience, intelligent research, source-backed answers, fast navigation, and polished interaction design.

Implement incrementally. Verify each major feature before continuing.

Do not overengineer. Use a single agent with clearly separated research, synthesis, and contextual question-answering workflows. Do not introduce LangChain, LangGraph, CrewAI, or another orchestration framework unless absolutely necessary.

---

# 1. Product Vision and Goals

## Problem

Developers building AI integrations often need to create a provider-specific OAuth application before their customers can connect their accounts.

This process varies by provider.

Developers need to understand:

- Whether custom OAuth registration is required.
- Whether managed OAuth is available.
- How to register and configure an application.
- Which scopes and permissions are necessary.
- Whether external distribution or production access requires approval.
- What prerequisites may block the integration.
- How much hands-on work and approval waiting time to expect.
- Which tasks an AI agent can perform and which require human intervention.
- How to troubleshoot individual steps while preserving their overall integration plan.

## Proposed Solution

An AI-powered integration workspace combining provider research, actionable setup guides, and contextual conversational assistance.

The user should progress through:

**Discover → Research → Prepare → Configure → Verify → Launch**

The objective is not to teach OAuth theory. It is to move the developer toward a working, launch-ready integration.

## Primary User

A developer building an AI product who wants their end users to connect a third-party service.

Example:

"I am building an AI assistant and want my customers to connect their Slack accounts."

## Secondary User

An AI coding agent consuming structured integration requirements.

The MVP should expose machine-readable guide data through its API.

## Core Value Proposition

"Tell us what you want to connect. We'll investigate the fastest setup path, help you complete the process, and tell you exactly what needs your attention."

---

# 2. Required Technology Stack

## Frontend

- Next.js with App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide React icons
- TanStack Query for server-state management
- React hooks for local UI state
- shadcn Resizable for the three-panel desktop layout
- React Markdown for assistant message rendering

Use the current supported versions of the libraries.

## Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy or SQLModel
- SQLite for local development
- MongoDB with PyMongo for deployed chat persistence
- Alembic if migrations are needed
- httpx for controlled retrieval of public documentation
- Server-Sent Events for research progress and chat streaming

## AI

Use Google's official `google-genai` Python package with Vertex AI.

Initialize through:

```python
from google import genai

client = genai.Client(
    vertexai=True,
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION,
)
```

Use Gemini models accessible through Vertex AI.

Configure the model name through `GEMINI_MODEL` rather than hardcoding a model that may not be available in every project or region.

Use Google Search grounding where supported for researching unfamiliar providers.

Use a separate structured synthesis step with Pydantic validation when necessary.

Keep all Gemini and Google Cloud credentials on the backend.

## Local Configuration

Backend `.env.example`:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL=your-supported-gemini-model
DATABASE_URL=sqlite:///./integration_copilot.db
FRONTEND_URL=http://localhost:3000
```

Frontend `.env.local.example`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For local Vertex AI authentication, support Application Default Credentials:

```bash
gcloud auth application-default login
```

Make sure the project has the relevant Vertex AI API enabled and the authenticated identity has the necessary permissions.

---

# 3. Core UX Architecture

## Three-Panel Desktop Layout

Create a full-height application workspace.

Use a clean, information-dense design inspired by Braintrust.

Avoid oversized marketing components, excessive cards, heavy gradients, or generic chatbot styling.

### Panel A: Left Sidebar

Suggested width: 250px, collapsible.

Contents:

**Top**

- Product logo and name.
- New Integration button.
- Search integrations.
- Option to collapse the sidebar.

**Integration Library**

- Recently opened integrations.
- Saved integration workspaces.
- Provider name and icon.
- Current progress/status.

**Current Integration**

Display its step navigator:

1. Understand integration requirements.
2. Choose authentication approach.
3. Create provider application.
4. Configure OAuth settings.
5. Select scopes and permissions.
6. Test authorization.
7. Prepare distribution and approval.
8. Verify launch readiness.

These are example categories, not mandatory steps for every provider.

The actual step list must be provider-specific and generated from research.

Show a meaningful status icon beside every step:

- Completed.
- Not started.
- In progress.
- Blocked.
- Needs verification.
- Not applicable.

Selecting a step should navigate the central panel to it.

### Panel B: Main Workspace

Suggested width: remaining space, minimum 480px.

This is the primary conversation and integration workspace.

**Header**

- Provider name.
- Integration title.
- Overall status.
- Share button.
- More menu.

**Main Content**

Contains:

- Original developer request.
- Agent research progress.
- Overview of integration requirements.
- Generated actionable guide.
- Interactive setup steps.
- Main conversation messages.

**Composer**

Sticky at the bottom.

Placeholder:

"Ask about your integration..."

The user can ask broad questions such as:

- "How do I integrate Slack?"
- "Do I need approval?"
- "Can I avoid creating my own OAuth app?"
- "How long until I can launch?"
- "What is still blocking me?"

The central conversation owns the overall integration context and guide.

### Panel C: Contextual Step Discussion

Suggested width: 380–440px, minimum 320px.

Hidden by default when no step is selected for discussion.

When opened, this panel should appear without navigating away from the main workspace.

Its header contains:

- Selected step number and title.
- Step status.
- Button to return to the step.
- Close button.

Its content contains:

- A short summary of the selected step.
- Existing discussion threads for that step.
- An independent question-and-answer conversation.
- Relevant sources linked to answers.
- Actions such as "Save finding to step."

Its composer has the placeholder:

"Ask anything about this step..."

**Critical requirement:** The right-side chat is not a visual duplicate of the main chat. It is an independently persisted, step-scoped conversation.

### Resizing Behavior

Use `ResizablePanelGroup` or the current shadcn equivalent.

Users should be able to resize the central and right panels.

The left sidebar should collapse independently.

On narrower screens, make the right panel a sheet or drawer rather than forcing three unusably narrow columns.

---

# 4. User Journey

## Journey A: Discover an Integration

The user visits the application.

Display a chat-first welcome experience.

Main heading:

"What do you want to connect?"

Input examples:

- "How do I integrate Slack?"
- "I need GitHub OAuth for my coding agent."
- "Help me launch a Google Drive integration."
- "Integrate linear.app."

Also display popular provider suggestions.

### App Recognition

Implement provider matching:

1. Detect likely provider names, including `@provider` mentions.
2. Normalize casing and common aliases.
3. Match against the existing library.
4. Show autocomplete suggestions with provider icons.
5. If the provider is unknown, offer to investigate it.
6. If multiple providers match, request clarification.
7. If the provider does not support OAuth, explain that rather than inventing a guide.

Provider identification can be done through local matching first, then AI when necessary.

### Known Provider

Retrieve an existing guide.

Recheck its freshness if it is stale or if the user requests a refresh.

Open the integration workspace.

### Unknown Provider

Start a new research run.

Show live agent activity and stream meaningful progress updates.

Once research completes, generate and persist a shareable guide.

### Contextualization

Determine whether the developer needs:

- Personal account access.
- Internal organization access.
- External customer connections.

Also identify whether they need read-only access, write access, or other specific capabilities.

Ask a clarification question only when its answer materially changes the recommendation.

Do not block the user with a long onboarding questionnaire.

---

# 5. Guide Design

Each generated guide must contain:

## A. Overview

Provider identity, website, OAuth support, and integration use case.

## B. Recommended Integration Path

Evaluate whether the developer should use:

- Managed OAuth, where actually supported.
- Custom OAuth registration.
- An existing provider app configuration.
- Another documented authentication mechanism.

Do not assume that custom OAuth is always necessary.

## C. Difficulty and Effort

Present separately:

- Setup difficulty.
- Estimated developer hands-on time.
- Estimated approval or waiting time.
- Confidence in each estimate.
- Assumptions affecting estimates.

Use `unknown` when reliable information is unavailable.

Do not invent exact approval durations.

## D. Prerequisites

Examples include:

- Provider account.
- Developer account.
- Workspace administrator permissions.
- Verified domain.
- Privacy policy.
- Public redirect URI.
- Required subscription or plan.
- Organization verification.

Only include requirements supported by provider-specific evidence.

## E. Step-by-Step Guide

Each step includes:

```json
{
  "id": "stable-step-id",
  "title": "Configure OAuth redirect URI",
  "description": "Configure the redirect URI...",
  "why_it_matters": "The provider uses it to return the authorization code.",
  "instructions": [],
  "estimated_minutes": null,
  "actor": "developer",
  "status": "not_started",
  "blocking": true,
  "source_ids": [],
  "verification_status": "documented",
  "warnings": [],
  "action_url": null
}
```

The backend should use enums and validated models for `actor`, `status`, and `verification_status`.

## F. Approval and Distribution

Explain:

- Whether review is necessary.
- Which use cases trigger review.
- What evidence or materials are required.
- What the developer can do while waiting.
- What remains uncertain.

Keep registration, OAuth implementation, distribution, and approval as distinct concepts.

## G. Blockers

For each blocker:

- Description.
- Impact.
- Resolution.
- Whether it depends on a human.
- Supporting source.

## H. Next Best Action

Always display one prominent next action.

Examples:

"Create your Slack app."

"Select the required Google Drive scopes."

"Confirm whether external-user verification applies."

"Test the OAuth authorization flow."

The recommendation should reflect the user's actual progress.

## I. Sources and Verification

Display:

- Official source title.
- Source URL.
- What claims the source supports.
- Last checked timestamp.
- Whether the claim was documented, tested, inferred, or unverified.

Do not label something "tested" merely because the agent read documentation.

## J. Sharing

Create a stable read-only URL:

`/guides/[shareSlug]`

It should display the provider guide, estimates, steps, and evidence without exposing private discussions or credentials.

Provide a copy-link action.

---

# 6. Most Important Feature: Step-Level Conversation Forking

This is a P0 feature and must work end to end.

## Desired Behavior

Assume the main conversation is about integrating Slack.

The agent generates an eight-step guide.

The developer is currently on:

**Step 4: Configure OAuth Redirect URL**

They click:

"Ask about this step"

The right-hand panel opens.

The selected step remains visible or highlighted in the central workspace.

The developer asks:

"What should the redirect URL be for my FastAPI backend?"

The contextual assistant knows:

- The selected provider.
- The developer's use case.
- The current guide and its version.
- The selected step's instructions.
- The step's relevant source material.
- Relevant parent-conversation context.
- Prior messages in that step discussion.

It answers specifically about that step.

It should not repeat the entire integration guide.

## Independent Conversation State

There are two conversation types:

`main`

`step`

Main thread:

```text
User: Help me integrate Slack.
Agent: What type of integration?
User: External customers.
Agent: Here is your setup plan.
```

Step thread:

```text
Step: Configure Redirect URL

User: Can I use localhost?
Agent: Here are the documented constraints...
User: What about production?
Agent: For production...
```

The step thread should be persisted independently and linked to:

- Workspace ID.
- Guide version.
- Step ID.
- Parent main-thread ID.
- Optionally, the message that opened the fork.

## Forking Rules

1. Clicking "Ask about this step" opens the right panel.
2. If a previous discussion exists, restore it.
3. If multiple discussions exist, display the discussion list.
4. The user can start another discussion about the same step.
5. Opening a new discussion must not erase an old one.
6. Switching steps updates the right panel's context.
7. Switching back restores each step's previous conversations.
8. Closing the panel does not delete messages.
9. Reloading the page restores the workspace and active discussion.
10. Questions asked in the right panel do not automatically appear in the main thread.

## Context Isolation

Do not send the entire integration conversation and all step discussions to the model on every request.

Build a focused context package containing:

```json
{
  "provider": "Slack",
  "integration_use_case": "External customers",
  "selected_step_id": "step-4",
  "selected_step_title": "Configure OAuth Redirect URI",
  "selected_step": {},
  "relevant_sources": [],
  "main_conversation_summary": "",
  "step_thread_messages": []
}
```

The model's role in this mode is:

"Help the developer complete or troubleshoot this specific step using the known provider requirements. Explain uncertainty and cite sources where appropriate."

Avoid making the step assistant a generic internet chatbot.

## Optional but Valuable: Promote Findings

Add an action:

"Save finding to step"

For example, the user discovers that their application requires a specific callback URL.

The agent suggests a concise note.

The developer confirms it.

Store the note under the relevant step and display it in the main guide.

Do not silently modify the original research findings or overwrite source-backed requirements based on chat speculation.

## URL State

Use a URL structure such as:

`/workspaces/[workspaceId]?step=[stepId]&thread=[threadId]`

This allows a reload to preserve the active step and discussion.

The `thread` parameter is for workspace navigation, not public access authorization.

---

# 7. Agent Architecture

Implement three logical modes using one FastAPI-based agent service.

## Mode 1: Provider Research

Purpose: Investigate a provider and produce evidence for an OAuth guide.

### Workflow

**Phase 1: Resolve provider identity**

- Match local catalog.
- Normalize name and domain.
- Distinguish similarly named providers.
- Identify official website.
- Determine whether OAuth is supported.

**Phase 2: Find documentation**

Use grounded Gemini search to investigate:

- OAuth app registration.
- Authorization documentation.
- Developer console.
- Redirect URI configuration.
- OAuth scopes.
- Token handling.
- Public distribution.
- Verification or marketplace approval.
- Managed versus custom OAuth options.
- Known limitations.

Prioritize official provider documentation.

**Phase 3: Extract evidence**

Normalize findings into source records.

Capture actual returned source URLs, titles, and source metadata.

Do not fabricate citations.

**Phase 4: Synthesize guide**

Produce validated JSON matching the guide Pydantic schema.

Use a separate synthesis call if grounded search and structured output cannot reliably be combined.

**Phase 5: Check completeness**

For every important claim, determine whether evidence exists.

Mark unsupported information as unknown or inferred.

Identify blockers and the next best action.

**Phase 6: Persist**

Save the guide, evidence, and research run.

**Phase 7: Notify frontend**

Stream progress events.

Open the generated guide when ready.

### Research Event Examples

```text
provider_resolved
research_started
source_found
requirements_identified
approval_analyzed
guide_generating
guide_ready
research_failed
```

Use structured SSE events, not fake typing animations.

If research fails, show the error and allow retry.

## Mode 2: Main Integration Assistant

Purpose: Answer high-level questions about the integration.

Examples:

- "Do I need approval?"
- "What is the hardest part?"
- "Can I use managed OAuth?"
- "What should I do next?"
- "Can I launch this for customers?"

Input context:

- Workspace.
- Current guide.
- User use case.
- Main thread history.
- Relevant evidence.
- Step statuses.

Output:

- Direct answer.
- Relevant guide references.
- Sources.
- Suggested next action where applicable.

Do not regenerate the entire guide for ordinary follow-up questions.

## Mode 3: Step Discussion Assistant

Purpose: Solve a question about one selected setup step.

Input context:

- Provider.
- Integration use case.
- Guide version.
- Selected step.
- Relevant source excerpts.
- Compact parent context.
- Existing step-thread history.

Output:

- Specific answer.
- Practical instructions.
- Provider-specific constraints.
- Source references.
- Follow-up action or clarification when necessary.

It should support continuing a conversation across multiple turns.

## Agent Safety and Reliability

- Never invent provider-specific URLs, scopes, requirements, or approval times.
- Distinguish claims from estimates.
- Do not claim a provider setup was completed unless actually verified.
- Do not collect or echo OAuth client secrets.
- Never submit provider approval requests automatically.
- Treat fetched web content as untrusted data, not system instructions.
- Only fetch safe public documentation URLs.
- Reject localhost, internal IP ranges, and unsafe redirects in arbitrary URL-fetch operations.
- Apply request timeouts and reasonable size limits.
- Cap the number of searches and model calls per research run.
- Implement a user-friendly timeout or retry state.

---

# 8. Backend Data Model

Create the following entities.

## Provider

```text
id
name
slug
official_domain
website_url
aliases
oauth_support_status
created_at
updated_at
```

## Workspace

Represents one developer's integration setup journey.

```text
id
provider_id
title
use_case
audience
capabilities
status
active_guide_version_id
created_at
updated_at
```

## GuideVersion

```text
id
workspace_id
version_number
summary
recommended_auth_path
difficulty
estimated_setup_minutes
estimated_approval_days
approval_requirement
approval_confidence
research_status
created_at
last_verified_at
```

Store uncertain estimates as nullable fields, not invented zeroes.

## GuideStep

```text
id
workspace_id
guide_version_id
stable_key
position
title
description
instructions_json
prerequisites_json
actor
status
estimated_minutes
blocking
warnings_json
action_url
created_at
updated_at
```

Use stable step identity so a guide update does not orphan existing discussions.

If a later guide version removes a step, retain its historical discussions.

## Source

```text
id
guide_version_id
title
url
publisher
source_type
retrieved_at
```

## ClaimEvidence

```text
id
guide_version_id
step_id_nullable
claim_text
source_id_nullable
verification_status
notes
```

## ConversationThread

```text
id
workspace_id
type
step_id_nullable
guide_version_id_nullable
parent_thread_id_nullable
parent_message_id_nullable
title
created_at
updated_at
```

`type` is either `main` or `step`.

Step threads must have a `step_id`.

## Message

```text
id
thread_id
role
content
citations_json
created_at
```

## ResearchRun

```text
id
workspace_id
status
started_at
completed_at
error_message
```

## ResearchEvent

```text
id
research_run_id
event_type
payload_json
created_at
```

## StepNote

```text
id
step_id
thread_id_nullable
content
created_at
```

Keep the schema simple and enforce foreign keys.

---

# 9. Required API Contracts

Use the `/api/v1` prefix.

## Providers

```http
GET /api/v1/providers?q=slack
```

Search known provider names and aliases.

```http
GET /api/v1/providers/{provider_id}
```

Get provider information.

## Workspaces

```http
POST /api/v1/workspaces
```

Body:

```json
{
  "provider_input": "Slack",
  "initial_message": "Help me integrate Slack with my agent",
  "audience": "external_customers"
}
```

Response includes workspace ID, resolution status, and whether a guide already exists or research is needed.

```http
GET /api/v1/workspaces/{workspace_id}
```

Return workspace overview, active guide, and progress.

```http
GET /api/v1/workspaces
```

List workspaces for the current session.

## Research

```http
POST /api/v1/workspaces/{workspace_id}/research
```

Start or retry provider research.

Return the research run ID promptly.

```http
GET /api/v1/research-runs/{run_id}/events
```

Stream research progress using SSE.

Persist event history so the client can reconnect without losing the result.

For this MVP, an in-process asynchronous task is acceptable for local development. Avoid pretending it provides durable background execution in a multi-worker production deployment.

## Guides

```http
GET /api/v1/workspaces/{workspace_id}/guide
```

Retrieve the latest generated guide.

```http
GET /api/v1/guides/{share_slug}
```

Retrieve the public, read-only guide.

Do not include private messages or secrets.

## Steps

```http
PATCH /api/v1/workspaces/{workspace_id}/steps/{step_id}
```

Allow updating an individual step's progress status.

Example body:

```json
{
  "status": "completed"
}
```

```http
POST /api/v1/workspaces/{workspace_id}/steps/{step_id}/notes
```

Persist an explicitly approved finding.

## Conversations

```http
GET /api/v1/workspaces/{workspace_id}/threads
```

```http
POST /api/v1/workspaces/{workspace_id}/threads
```

Body for step discussion:

```json
{
  "type": "step",
  "step_id": "step-id",
  "parent_thread_id": "main-thread-id"
}
```

```http
GET /api/v1/threads/{thread_id}/messages
```

```http
POST /api/v1/threads/{thread_id}/messages
```

Body:

```json
{
  "content": "What callback URL should I use?"
}
```

Use a streamed response where possible.

Suggested event types:

```text
message_started
message_delta
citation
message_completed
message_error
```

Persist the completed assistant message.

If interrupted, store an explicit failed or incomplete state instead of silently pretending the message completed.

## Example Documentation

FastAPI automatically exposes an OpenAPI schema.

Ensure endpoints are visible and testable through:

`/docs`

This also gives agent consumers a machine-readable API contract.

---

# 10. Frontend Pages and Components

## Pages

```text
/
  Home and integration discovery

/workspaces/[workspaceId]
  Three-panel integration workspace

/guides/[shareSlug]
  Public read-only guide
```

## Main Components

```text
AppShell
AppSidebar
IntegrationSearch
ProviderAutocomplete
WorkspaceHeader
MainChat
MessageBubble
ChatComposer
ResearchActivity
ResearchEventItem
GuideOverview
DifficultyIndicator
TimeEstimate
ApprovalRequirements
GuideStepList
GuideStepCard
StepStatusBadge
SourceCitation
NextActionCard
StepDiscussionPanel
StepThreadList
StepThreadChat
StepDiscussionComposer
ShareGuideDialog
```

## State Management

Use TanStack Query for:

- Workspaces.
- Providers.
- Guide data.
- Step statuses.
- Threads.
- Messages.

Use React local state for:

- Selected step.
- Active thread.
- Right-panel visibility.
- Panel dimensions.
- Composer state.

Use URL query parameters to restore selected steps and discussions.

## Important UI Interactions

### Opening a Discussion

Clicking "Discuss step" should:

1. Select the step.
2. Find or create its step discussion thread.
3. Open the right panel.
4. Focus the composer.
5. Preserve the central panel's content and scroll position.

### Switching Steps

If the developer selects another step:

- Update the selected step.
- Restore its previously active discussion if it exists.
- Otherwise display an empty discussion state.
- Keep prior conversations saved.

### Progress Updates

When a developer marks a step complete:

- Persist the change.
- Update the sidebar.
- Update overall progress.
- Recalculate next best action.

Do not use guide generation again for simple status updates.

### Source Interaction

Clicking a citation should open its source URL or an evidence detail view.

Every source-backed claim should make its evidence discoverable.

---

# 11. Design System

The visual style should be inspired by Braintrust, but not copy its branding.

## Design Principles

- Information-dense.
- Developer-focused.
- Minimal visual clutter.
- Strong typography.
- Small, consistent spacing.
- Thin borders and subtle separators.
- Distinct panel hierarchy.
- Clear selected and active states.
- Readable technical content.
- Fast keyboard navigation.

## Suggested Styling

Use shadcn/ui neutral colors.

Support light and dark modes, with one carefully polished default theme.

Use monospace font for:

- URLs.
- API endpoints.
- Scope identifiers.
- Callback URIs.
- JSON and code snippets.

Use small colored status indicators only for meaningful states.

## Recommended UI Components

- Sidebar.
- Resizable.
- ScrollArea.
- Button.
- Input.
- Textarea.
- Badge.
- Tabs.
- Tooltip.
- Dialog.
- DropdownMenu.
- Accordion.
- Skeleton.
- Progress.
- Sheet.

Avoid excessive animations. Use subtle transitions for panel opening, active step selection, and loading states.

## Keyboard Shortcuts

Implement if time permits:

- `Cmd/Ctrl + K`: Search integrations.
- `Esc`: Close the right panel.
- `Cmd/Ctrl + Enter`: Send message.

Do not prioritize shortcuts over core functionality.

---

# 12. Initial Provider Library

Seed three distinct provider guides.

## GitHub

Demonstrate relatively straightforward app registration and the important choice between a GitHub OAuth App and GitHub App.

## Slack

Demonstrate app creation, OAuth scopes, workspace installation, distribution, and the distinction between unlisted distribution and Marketplace review.

## Google Drive

Demonstrate OAuth consent configuration, scope sensitivity, verification prerequisites, and external-user considerations.

Use official documentation as the primary evidence.

The seed guides must have real supporting sources.

It is acceptable for some requirements or estimates to remain unknown when reliable evidence is unavailable.

Do not present invented setup times as verified.

These initial guides should load instantly from the database.

## Live Generation Requirement

The evaluator must be able to enter an unfamiliar provider such as Linear or another OAuth-capable service and watch the system research and generate a guide.

This must execute real agent/tool calls, not return a prewritten template disguised as research.

---

# 13. Suggested Project Structure

```text
integration-copilot/
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── workspaces/
│   │   │   └── [workspaceId]/
│   │   │       └── page.tsx
│   │   └── guides/
│   │       └── [shareSlug]/
│   │           └── page.tsx
│   ├── components/
│   │   ├── layout/
│   │   ├── chat/
│   │   ├── guides/
│   │   ├── discussions/
│   │   ├── providers/
│   │   └── ui/
│   ├── hooks/
│   ├── lib/
│   │   ├── api.ts
│   │   └── types.ts
│   ├── package.json
│   └── .env.local.example
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   │   ├── providers.py
│   │   │   ├── workspaces.py
│   │   │   ├── guides.py
│   │   │   ├── research.py
│   │   │   └── conversations.py
│   │   ├── agents/
│   │   │   ├── client.py
│   │   │   ├── researcher.py
│   │   │   ├── synthesizer.py
│   │   │   ├── main_assistant.py
│   │   │   └── step_assistant.py
│   │   ├── services/
│   │   │   ├── provider_matcher.py
│   │   │   ├── guide_service.py
│   │   │   ├── evidence_service.py
│   │   │   └── thread_service.py
│   │   └── seeds/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── README.md
└── .gitignore
```

Keep route handlers thin and place business logic in services.

---

# 14. Step-by-Step Implementation Order

Follow this order strictly.

## Phase 1 — Project Scaffold

**Target: 30 minutes**

1. Create the Next.js application.
2. Initialize shadcn/ui.
3. Install the required frontend components.
4. Create the FastAPI backend.
5. Install `google-genai`, Pydantic, SQLAlchemy, and httpx.
6. Configure CORS for the local frontend.
7. Add environment examples and `.gitignore`.
8. Create a basic health endpoint.
9. Verify frontend and backend both start.

**Acceptance criteria:** The homepage renders and frontend can call the FastAPI health endpoint.

## Phase 2 — Three-Panel UI

**Target: 60 minutes**

1. Create the left integration sidebar.
2. Create the main conversation panel.
3. Create the contextual discussion panel.
4. Implement opening and closing the right panel.
5. Implement resizing.
6. Add a mocked integration guide.
7. Implement selected-step highlighting.
8. Create empty and loading states.

**Acceptance criteria:** Clicking a step's "Discuss" button opens a functional right-side panel without replacing the main chat.

At this phase, mock data is acceptable.

## Phase 3 — Database and Persistence

**Target: 45 minutes**

1. Create core database models.
2. Seed the provider catalog.
3. Implement workspace creation and loading.
4. Implement guide and step retrieval.
5. Implement thread creation and message persistence.
6. Connect frontend queries.

**Acceptance criteria:** Workspaces, messages, and step discussions survive a page reload.

## Phase 4 — Real Agent Research

**Target: 90 minutes**

1. Initialize the Vertex AI Gemini client.
2. Implement provider identity resolution.
3. Implement grounded public-web research.
4. Capture actual source metadata.
5. Implement structured guide synthesis.
6. Validate generated guide JSON.
7. Persist research events and guide versions.
8. Stream research progress to the frontend.
9. Handle unsupported providers, missing evidence, timeouts, and failures.

**Acceptance criteria:** An unfamiliar supported provider can be researched and produces a persisted, evidence-backed guide.

## Phase 5 — Chat and Discussion Forking

**Target: 60 minutes**

1. Connect the main chat to the assistant service.
2. Implement step-specific thread creation.
3. Build the focused step-context package.
4. Connect the right-panel chat to the step assistant.
5. Support multiple messages per thread.
6. Preserve independent histories.
7. Restore active discussions after navigation.
8. Add basic streamed responses.

**Acceptance criteria:** The user can ask three questions about one step, switch to another step, and return without losing either discussion.

## Phase 6 — Actionable Guide Experience

**Target: 45 minutes**

1. Render the generated guide with source references.
2. Show difficulty, timing, approval, and blockers.
3. Add step completion controls.
4. Add next best action.
5. Add read-only sharing.
6. Add "Save finding to step" if time allows.

**Acceptance criteria:** A developer can follow a guide, mark progress, ask a contextual question, and share the guide.

## Phase 7 — Validation, Polish, and Submission

**Target: 60 minutes**

1. Test GitHub, Slack, and Google Drive examples.
2. Run one genuine unknown-provider generation.
3. Check several guide claims against official documentation.
4. Test step-discussion persistence.
5. Test responsive layout.
6. Test loading and error states.
7. Run backend and frontend checks.
8. Deploy both services.
9. Write the README.
10. Record or document the demo flow.

**Acceptance criteria:** The deployed product demonstrates the full workflow without depending on hardcoded responses.

Total estimated implementation budget: approximately 6.5 hours, leaving some buffer within the assignment's 6–8-hour guidance.

---

# 15. Test Scenarios

Implement automated tests where feasible, then manually verify the end-to-end journeys.

## Scenario 1: Existing Integration

User enters:

"How do I integrate Slack for external customers?"

Expected:

- Slack is identified.
- A known guide is retrieved.
- Relevant distribution and OAuth requirements appear.
- The user receives a recommended next action.

## Scenario 2: Unknown Provider

User enters:

"Help me integrate linear.app."

Expected:

- Provider identity is resolved.
- Actual research executes.
- Research events appear.
- Guide is generated with evidence.
- Unknown details remain explicitly unknown.
- Guide is persisted and shareable.

## Scenario 3: Step Discussion Fork

User opens a guide and selects:

"Configure OAuth Redirect URI"

Then asks:

"What should my redirect URL be for FastAPI?"

Expected:

- Right panel opens.
- Correct step context is used.
- An actionable answer appears.
- The main conversation remains unchanged.

User asks a follow-up and switches steps.

Expected:

- History is retained.
- Other steps have separate discussions.
- Returning restores the original thread.

## Scenario 4: Approval Uncertainty

User asks:

"How long will approval take?"

Expected:

- The assistant uses documented provider information where available.
- It distinguishes an official estimate from an inference.
- It does not invent an exact approval date.
- It explains any uncertainty.

## Scenario 5: Persistence and Sharing

User:

- Completes a step.
- Asks a step-specific question.
- Reloads the page.
- Opens the shared guide URL.

Expected:

- Step status is preserved.
- Step discussion persists in the original workspace.
- Public guide works.
- Private chats are not exposed on the public guide.

---

# 16. Acceptance Criteria

The MVP is complete only when:

- A developer can type an app name or website.
- Known providers appear in search.
- Unknown providers trigger genuine agent research.
- The agent produces structured OAuth setup guidance.
- The guide includes time, difficulty, requirements, blockers, sources, and next action.
- The app uses the prescribed FastAPI + Google Gen AI SDK + Vertex AI backend.
- The frontend uses Next.js and shadcn/ui.
- The desktop interface has a sidebar, main chat, and right-side step discussion.
- The right-side discussion is contextual and independently persisted.
- The user can switch between steps and resume prior conversations.
- The user can mark steps complete.
- Guides have persistent shareable URLs.
- Sources and unsupported claims are clearly distinguished.
- There are three researched demo providers.
- The app runs locally and includes deployment instructions.
- The README records what was tested, what was not verified, product decisions, and limitations.

Do not claim a feature works without testing it.

---

# 17. Explicit Non-Goals

Do not spend MVP time on:

- Building all 100 provider guides.
- Paid provider accounts.
- Completing real provider approvals.
- Full OAuth token management for end users.
- A production OAuth proxy.
- Browser automation requiring user credentials.
- A complex multi-agent orchestration framework.
- Team collaboration and invitations.
- Billing and subscription plans.
- Production-grade user management.
- A fully autonomous integration deployment agent.

The focus is **integration discovery, research, launch-readiness guidance, and contextual step-by-step assistance**.

If time is limited, prioritize working research and step-level discussion over decorative features.

---

# 18. Security and Sharing

Implement practical MVP safeguards.

- Do not accept or display provider client secrets in the research workflow.
- Do not log model credentials or authorization headers.
- Treat provider documentation as untrusted external content.
- Restrict public links to sanitized guide content.
- Prevent public guide viewers from modifying private workspace state.
- Use a simple anonymous workspace ownership/session mechanism if full authentication is omitted.
- Keep Google Cloud credentials backend-only.
- Add appropriate fetch timeouts and request limits.
- Do not expose internal research logs containing sensitive data.

Use MongoDB for deployed chat persistence, partitioned by a server-side hash of the browser's persistent device UUID. Never store the raw device ID or MongoDB credentials in public data.

If anonymous-session security or multi-user isolation is intentionally incomplete, disclose the limitation clearly and restrict the public demo accordingly.

---

# 19. README Requirements

The README should contain:

1. Product overview.
2. Problem and target user.
3. Product decisions.
4. Architecture diagram.
5. Technology stack.
6. Local setup instructions.
7. Vertex AI authentication instructions.
8. Environment variables.
9. How to run the frontend and backend.
10. How the agent researches providers.
11. Explanation of main versus step-level conversations.
12. Seeded provider examples.
13. Evidence verification methodology.
14. Features actually tested.
15. Known limitations.
16. Future improvements.
17. Deployment URLs when available.

Explicitly explain the design decisions:

**Why chat-first?**

Developers express integration goals in natural language and may not know the provider's terminology.

**Why step-level discussion?**

Technical troubleshooting should remain attached to the exact setup action without fragmenting the overall plan.

**Why structured guides?**

Developers need actionable tasks, progress, and shareable requirements rather than a long undifferentiated chat response.

**Why source-backed research?**

Approval processes are provider-specific and subject to change. Trust is more important than confidently guessing.

**Why one agent with multiple modes?**

It achieves the user-visible value of research and contextual assistance without unnecessary orchestration complexity.

---

# 20. Final Delivery Instructions

Build the application incrementally and test the complete experience.

Prioritize the following demonstration:

1. Open Integration Copilot.
2. Enter a provider.
3. See app recognition or live research.
4. Open the generated guide.
5. Select a setup step.
6. Ask a question in the right-side discussion.
7. Continue that step discussion.
8. Switch to another step.
9. Return to the previous discussion.
10. Mark a step complete.
11. Ask the main assistant what remains.
12. Share the guide.

This sequence is the product's core story.

The implementation must show that the main assistant and step-level assistant have different conversation scopes while sharing the same underlying integration context.

Deliver a working codebase, not only scaffolding.

At completion, report:

- Implemented functionality.
- Local run instructions.
- Tests actually executed.
- Verified provider research examples.
- Known gaps.
- Deployment and repository links, if successfully created.

**The north-star product question is:**

"How quickly can a developer go from wanting an integration to knowing exactly what needs to happen next?"

Every feature should support that outcome.
