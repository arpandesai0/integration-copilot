# Integration Copilot

An integration workspace for developers building products that connect to third-party services. It turns an integration goal into a source-backed setup guide and keeps troubleshooting conversations attached to individual steps.

Build requirements: [docs/agents/AGENT.md](docs/agents/AGENT.md). Execution checklist: [docs/agents/IMPLEMENTATION_STAGES.md](docs/agents/IMPLEMENTATION_STAGES.md).

## Local setup

Requirements: Node.js 20.9+ (a current supported LTS is recommended), npm, Python 3.11+, [uv](https://docs.astral.sh/uv/), and MongoDB Atlas (or local MongoDB) for durable chat storage. Google Cloud access is required for live research and assistant answers; local guide metadata uses SQLite by default.

```sh
make setup
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Configure `backend/.env`:

```dotenv
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL=your-supported-gemini-model
DATABASE_URL=sqlite:///./integration_copilot.db
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@YOUR_CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=integration_copilot
FRONTEND_URL=http://localhost:3000
```

Configure `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Authenticate using Application Default Credentials:

```sh
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

Enable the Vertex AI API and grant the authenticated identity the necessary Vertex AI permissions. In a hosted environment, use an attached service account or workload identity. Keep credentials out of frontend variables and source control. `GEMINI_SYNTHESIS_MODEL` optionally selects a faster model for formatting researched evidence; it falls back to `GEMINI_MODEL`. `GEMINI_CHAT_MODEL` optionally selects a faster model for streamed main/step replies, falling back to `GEMINI_MODEL`. `GEMINI_RESEARCH_MODEL` separately selects the model for focused grounded searches (also falls back to `GEMINI_MODEL`); the local setup uses `gemini-3.5-flash-lite` for both. A fast, tool-free scope check asks for missing requirements before searching. The local setup currently uses a verified `gemini-3.5-flash-lite` formatter while retaining the primary research/chat model. Research is bounded to 240 seconds overall, with up to 150 seconds for search and 75 seconds for synthesis, plus optional passage verification. Chat allows 180 seconds; clarification routing and replies allow 60 and 90 seconds respectively. These limits are configurable in the backend environment.

Select a model available in your project and region; the application deliberately does not assume a universal model name. The local `backend/.env` takes precedence over inherited shell settings; without that file, deployment environment variables apply. Restart the backend after editing configuration.

Start these in separate terminals:

```sh
make backend
```

```sh
make frontend
```

Open http://localhost:3000. Backend API documentation is at http://localhost:8000/docs. The browser creates a persistent UUID in local storage and sends it as `X-Device-ID`; only its SHA-256 hash is used to partition private workspaces and MongoDB chat documents.

## Architecture and product decisions

```mermaid
flowchart LR
    UI[Next.js workspace] --> API[FastAPI API]
    API --> Metadata[(SQLite metadata)]
    API --> Mongo[(MongoDB chat storage)]
    API --> Agent[One agent service]
    Agent --> Research[Grounded provider research]
    Agent --> Synthesis[Validated guide synthesis]
    Agent --> Main[Main integration assistant]
    Agent --> Step[Step discussion assistant]
    Agent --> Vertex[Google Gen AI SDK / Vertex AI]
```

The frontend uses App Router, TypeScript, Tailwind, shadcn/ui primitives, Lucide, TanStack Query, and React Markdown. Its visual direction draws on Composio’s public site: charcoal surfaces, electric-blue actions, Geist typography, and restrained developer-console layouts. The backend uses FastAPI, Pydantic v2, SQLAlchemy, httpx, and Google's official `google-genai` SDK. SSE carries research progress and conversation responses. Both seeded and live guides render as the first assistant turn after the user request. The left-side reading rail is vertical, and compact auto-growing composers use Enter to send and Shift+Enter for a newline.

Chat-first discovery lets developers describe goals without knowing provider terminology. Structured guides make requirements actionable and shareable. Step discussions preserve troubleshooting context without fragmenting the main plan. Source-backed claims distinguish documented requirements from estimates and uncertainty. One agent service with separate modes keeps research, synthesis, and focused assistance understandable without an orchestration framework.

The main assistant receives the overall integration context and progress. A step assistant receives the selected guide version and step, relevant evidence, compact parent context, and its own thread history. Each step opens one simple sub-chat and resumes its saved history; messages remain private to the workspace. A public share link exposes guide content only.

## Provider examples and evidence

GitHub demonstrates the OAuth App versus GitHub App choice. Slack demonstrates scopes, installation, and distribution versus Marketplace review. Google Drive demonstrates scope sensitivity, consent configuration, and external-user verification. Unknown providers require real grounded research rather than a seeded answer.

Research resolves provider identity, gathers actual source metadata, synthesizes a validated guide, and persists its version and progress events. Official provider documentation is preferred. Sources appear beside the fields and individual instructions they support, with compact numbered references instead of source lists at step/message ends. Source links use browser text fragments for verified exact passages, including step-specific passages. Unverified quotes are discarded and links fall back to the original source rather than generating a false highlight. Unsupported claims and uncertain durations remain explicitly unknown; documentation retrieval alone is never proof that an OAuth setup was tested.

## Checks and implementation status

Implemented: provider discovery, three-panel workspace, persisted guides and automatic reading progress, independent main and step conversations, a single reusable sub-chat per step, research/chat SSE, source disclosures, freshness checks, copyable links/code/steps and technical response formatting, verified passage links, unified user/agent chat for seeded and researched guides, public read-only sharing, sidebar-only chat deletion, responsive discussion drawers, and persisted light/dark themes.

The current full check passes 115 backend tests plus frontend lint, TypeScript, and the production build. Backend tests cover ownership, privacy, evidence validation, scoped conversation histories, mocked research success, interruptions, freshness, retry/reconnection, and grounding-link sanitization. Browser checks against development and production servers cover actual workspace interactions and real cloud error handling. Live Vertex research and both main/step chat answers are now verified using the selected project. Linear generated a persisted five-step guide with 16 source records. An earlier inherited project produced billing errors; local configuration now takes precedence and the backend has been restarted.

The optional “Save finding to step” action has a confirmed-note API and rendering support, but its UI action is deferred. MongoDB Atlas deployment, container builds, deployment, and actual provider OAuth flows have not been verified. A checked implementation task is not evidence of a successful deployment.

Run project checks with:

```sh
make check
```

## Deployment

Deploy the frontend as a Node.js Next.js application and the backend as a Python ASGI service. Set the frontend's `NEXT_PUBLIC_API_URL` at build time, configure the backend's `FRONTEND_URL` to its exact browser origin, and use HTTPS in deployment. Allow the deployment host in MongoDB Atlas Network Access and store `MONGODB_URI` only in the backend secret manager.

Use the Atlas SRV URI through `MONGODB_URI`; never commit the real password. The optional `docker compose up -d mongo` command starts local MongoDB, which can be selected with `MONGODB_URI=mongodb://localhost:27017`. Chat records are indexed by the hashed device ID, thread, and creation time.

`GUIDE_FRESHNESS_DAYS` defaults to 30; older or undated evidence is flagged for refresh. CORS must allow the exact frontend origin and the `X-Device-ID` header. A device ID identifies one browser profile; clearing site storage intentionally starts a new private workspace identity.

Run the backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000` from `backend/`. Run `npm run build` followed by `npm start` from `frontend/`. Provide Google Cloud identity, model configuration, and the MongoDB URI to the backend only. Mount persistent storage for the remaining SQLite guide metadata until it is migrated to MongoDB.

No deployed URL or remote repository has been created in this session.

## Scope and future work

The product guides setup; it does not store OAuth client secrets, manage customer OAuth tokens, submit provider approvals, or perform credential-based browser automation. Anonymous sessions are an MVP ownership mechanism rather than full user accounts. Local research tasks are in-process and do not provide durable background execution across restarts or multiple workers.

Future improvements include durable research jobs, explicit schema migrations, authenticated accounts, broader provider coverage, and stronger evidence freshness monitoring. Real provider approval and production OAuth proxying remain outside this MVP.

## Demo flow

1. Open the homepage and select Slack, GitHub, or Google Drive for an instant seeded guide.
2. Open “Ask about this step,” send a question, and continue the discussion. Live answers require working Vertex AI billing and permissions; failures remain explicit and persisted.
3. Open another step and return to the original discussion; reload to verify restoration.
4. Scroll through the guide using its numbered reading-progress rail. Ask the main assistant what to do next; no checklist updates are required.
5. Share the guide and open its URL in a separate browser session. Conversations and private notes stay private.
6. Enter an unfamiliar provider such as Linear to run actual grounded research. This was verified with real Linear research using the configured Vertex project.
