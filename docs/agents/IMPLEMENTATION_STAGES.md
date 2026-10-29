# Integration Copilot — Implementation Stages

Source of truth: [AGENT.md](./AGENT.md), especially sections 14–20.

Follow these stages in order. Verify each stage before proceeding. Check a task only after it has been implemented and verified; record actual checks and remaining gaps in the README. Status below reflects implementation and verification on 2026-10-29. The formal five-scenario production demo remains intentionally open.

The repository now contains a runnable frontend and backend. Local developer verification notes are kept outside version control under `docs/dev/`.

## Stage overview

| Stage | Outcome | Target | Depends on |
| --- | --- | --- | --- |
| 1 | Frontend and backend run and communicate | 30 minutes | — |
| 2 | Interactive three-panel workspace | 60 minutes | 1 |
| 3 | Persisted workspaces, guides, and discussions | 45 minutes | 2 |
| 4 | Real, source-backed provider research | 90 minutes | 3 |
| 5 | Main chat and independent step discussions | 60 minutes | 4 |
| 6 | Actionable, trackable, shareable guides | 45 minutes | 5 |
| 7 | Verified demo and deployment documentation | 60 minutes | 6 |

Total target: 390 minutes (6.5 hours). These are planning estimates, not measured implementation times. Preserve working research and step discussions if time becomes constrained; defer optional polish first.

## Product updates

The user’s subsequent UI direction supersedes the original multi-discussion controls: each step now opens one reusable sub-chat with saved history. The sidebar checklist was replaced by numbered reading progress in the main conversation. Legacy thread data remains stored. Manual step-status controls and completion counters were subsequently removed at the user’s request; reading progress is automatic and assistant guidance follows user-reported progress.

## Current status

| Stage | Status |
| --- | --- |
| 1–3 | Implemented; health, browser interactions, persistence, and isolation verified |
| 4 | Implemented; mocked tests and successful live Linear research verified after applying the selected project |
| 5 | Thread/context behavior tested; persistence, failure handling, and successful live main/step answers verified |
| 6 | Implemented and verified; optional finding-save UI deferred |
| 7 | Cloud Run deployment is live; durable MongoDB metadata restoration is implemented and locally verified; formal production demo is pending |

## Stage 1 — Project scaffold

**Deliverable:** A runnable Next.js frontend and FastAPI backend with documented local configuration.

- [x] Create `frontend/` with App Router, TypeScript, Tailwind, shadcn/ui, Lucide, TanStack Query, and React Markdown.
- [x] Install the shadcn components needed for resizable panels, sidebar, sheets, forms, and dialogs.
- [x] Create `backend/` with Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy or SQLModel, `google-genai`, and httpx.
- [x] Configure environment loading, local CORS, a health endpoint, and the frontend API client.
- [x] Add backend `.env.example`, frontend `.env.local.example`, dependency manifests, and `.gitignore`.
- [x] Keep Google Cloud configuration backend-only; configure the model through `GEMINI_MODEL`.

**Verification gate:** Start both services, render the homepage, and successfully call the backend health endpoint from the frontend. Confirm secrets and local environment files are excluded from version control.

## Stage 2 — Three-panel workspace

**Deliverable:** The primary workspace interaction works with temporary mock data.

- [x] Build the integration sidebar with search, saved integrations, collapse control, and provider-specific step navigation.
- [x] Build the main panel with workspace header, guide, conversation, and sticky composer.
- [x] Build a separate contextual discussion panel with selected-step details, thread list, and composer.
- [x] Add panel resizing, selected-step highlighting, and navigation from the sidebar to the relevant guide step.
- [x] Make “Ask about this step” open the contextual panel and focus its composer while preserving central content and scroll position.
- [x] Support closing the panel and use a sheet or drawer on narrow screens.
- [x] Add welcome, empty, loading, and error states with a compact neutral design.

**Verification gate:** Open and close discussions for different steps, resize panels, collapse the sidebar, and check a narrow viewport. The main conversation remains visible and separate from step chat. Mock content is acceptable only as temporary scaffolding.

## Stage 3 — Database and persistence

**Deliverable:** Workspace and discussion state survives navigation and reloads.

- [x] Implement the section 8 entities: Provider, Workspace, GuideVersion, GuideStep, Source, ClaimEvidence, ConversationThread, Message, ResearchRun, ResearchEvent, and StepNote.
- [x] Use validated enums, nullable unknown estimates, relational constraints for guide metadata, and MongoDB persistence for chats.
- [x] Preserve stable step keys across guide versions and retain discussions attached to historical or removed steps.
- [x] Add a persistent browser device UUID, hash it on the server, and enforce the resulting ownership key for private workspace, thread, message, and mutation endpoints.
- [x] Seed the provider catalog with names, domains, aliases, and icons for GitHub, Slack, and Google Drive.
- [x] Implement provider lookup and workspace creation/list/loading, guide retrieval, thread creation/listing, and message persistence under `/api/v1`.
- [x] Require a valid step, workspace, guide version, and parent main thread for step discussions.
- [x] Connect TanStack Query to persisted data; restore selected step and active discussion through `?step=…&thread=…`.

**Verification gate:** Create a workspace, persist main and step messages, reload, and restore the active discussion. Verify another anonymous session cannot access private state and invalid cross-workspace thread references are rejected. Inspect the OpenAPI contract at `/docs`.

## Stage 4 — Real agent research

**Deliverable:** An unfamiliar provider produces a validated, persisted guide using genuine research calls.

- [x] Initialize the official Google Gen AI client with Vertex AI, configurable project/location/model, and Application Default Credentials.
- [x] Resolve provider names, aliases, domains, and `@provider` mentions locally before AI fallback; clarify ambiguous matches and handle providers without OAuth.
- [x] Implement one agent service with separate research and structured synthesis workflows; use Google Search grounding where supported.
- [x] Research registration, authentication alternatives, scopes, redirect URIs, testing, distribution, approval, and prerequisites using official documentation first.
- [x] Capture actual source URLs, titles, timestamps, and claim evidence; validate synthesized guide JSON with Pydantic.
- [x] Include all required guide fields from section 5, distinguishing documented, tested, inferred, and unverified claims. Leave unsupported estimates unknown.
- [x] Persist guide versions, research runs, and ordered research events; return the run ID promptly and stream structured SSE progress with reconnection support.
- [x] Add retries, timeouts, call budgets, explicit failure states, stale-guide detection, and user-requested refresh.
- [x] Treat retrieved documentation as untrusted data. Restrict retrieval to safe public URLs, validate redirects, block internal addresses, and enforce response size limits.
- [x] Create evidence-backed seed guides for GitHub, Slack, and Google Drive so known-provider journeys load directly from the database.

**Verification gate:** Research an unfamiliar provider such as Linear with actual model/tool calls, observe real progress, reload its persisted guide, and inspect source support for representative claims. Test research failure/retry, missing evidence, ambiguity, and unsupported OAuth. Reading documentation must never result in a “tested” claim.

**Runtime constraint:** An in-process research task is acceptable locally. Document its limitations; do not represent it as durable multi-worker execution.

## Stage 5 — Chat and discussion forking

**Deliverable:** Main and step assistants answer with distinct context and independently persisted histories.

- [x] Connect main chat to workspace context, current guide, relevant evidence, main history, and progress without regenerating the guide for normal follow-ups.
- [x] Implement focused step context: provider, use case, guide version, selected step, relevant sources, compact main summary, and that thread’s messages.
- [x] Connect right-panel chat to the step assistant with practical answers and source references scoped to the selected step.
- [x] Restore existing discussions, list multiple threads for a step, and allow starting another discussion without overwriting previous threads.
- [x] Preserve histories when switching steps, closing the panel, navigating, or reloading; keep step messages out of the main thread.
- [x] Stream message lifecycle events and citations; persist completed messages and explicit incomplete/failed states when interrupted.
- [x] Verify authorization for both message reads and streamed writes; never treat a URL thread ID as access permission.

**Verification gate:** Ask three related questions about one step, start another discussion on it, switch to another step and ask a question, then return and reload. Each history and active discussion restores correctly. Confirm step requests exclude unrelated discussions and answers use the selected step’s evidence.

## Stage 6 — Actionable guide experience

**Deliverable:** A developer can follow a guide, track progress, and share sanitized guidance.

- [x] Render overview, recommended authentication path, prerequisites, difficulty, separate hands-on/wait estimates, confidence, assumptions, approval requirements, and blockers.
- [x] Render provider-specific instructions, actors, warnings, action URLs, verification labels, and discoverable claim citations with last-checked timestamps.
- [x] Persist step status updates and recalculate sidebar progress, overall status, and next best action without another generation call.
- [x] Implement `/guides/[shareSlug]`, the public guide API, and copy-link action with a stable read-only URL.
- [x] Serialize public guide content explicitly so private discussions, session data, credentials, and internal logs are excluded.
- [ ] If time permits, implement “Save finding to step” with explicit confirmation and a separate note; preserve original source-backed requirements.

**Verification gate:** Complete a step and reload to confirm progress and next action. Open the share URL in a separate session, inspect its payload for private data, and verify public viewers cannot modify the originating workspace. If findings are implemented, verify only explicitly confirmed notes are saved.

## Stage 7 — Validation, polish, and submission

**Deliverable:** A verified end-to-end demo with reproducible setup, deployment, and candid limitations.

- [ ] Run the five scenarios from section 15: existing provider, unknown-provider research, discussion fork, approval uncertainty, and persistence/sharing.
- [x] Verify GitHub, Slack, and Google Drive examples against official sources and record what was checked and when.
- [x] Run meaningful backend tests for context isolation, ownership, persistence, evidence validation, streaming failures, and public serialization.
- [x] Run frontend type, lint, and build checks plus browser checks for the complete journey, responsive layout, loading, and recoverable errors.
- [x] Finish consistent light/dark styling and accessibility; add keyboard shortcuts only if core functionality is complete.
- [x] Configure MongoDB Atlas persistence with backend-only credentials, frontend/backend URLs, device-ID CORS headers, direct chat storage, and atomic snapshots for all remaining metadata.
- [x] Deploy both services to Cloud Run and record stable service URLs in the README. A subsequent deployment is required for the latest metadata-snapshot revision.
- [x] Write the README covering all section 19 requirements: product decisions, architecture, setup, ADC, environment variables, run commands, research flow, conversation scopes, seed providers, evidence methodology, actual checks, limitations, future work, and available deployment URLs.
- [x] Record or document the section 20 demo sequence, including discussion switching, step completion, a main-chat follow-up, and sharing.

**Verification gate:** Complete the core demonstration end to end using real research and persisted conversations. Report checks actually executed and unresolved gaps; a local-only result must not be described as a verified deployment.

## Completion boundary

The MVP is complete only when all acceptance criteria in section 16 of [AGENT.md](./AGENT.md) are satisfied. Optional findings and shortcuts do not block completion. Provider approvals, real OAuth token management, credential-based browser automation, team features, billing, and complex agent orchestration remain out of scope.

For each completed stage, record its implementation date, checks executed, result, and remaining issues in the project README or a linked verification log. Keep unchecked tasks visible until verified.
