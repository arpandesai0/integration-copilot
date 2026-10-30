# Integration Copilot

An integration workspace for developers building products that connect to third-party services. It turns an integration goal into a source-backed setup guide and keeps troubleshooting conversations attached to individual steps.

Build requirements: [docs/agents/AGENT.md](docs/agents/AGENT.md). Execution checklist: [docs/agents/IMPLEMENTATION_STAGES.md](docs/agents/IMPLEMENTATION_STAGES.md).

## Local setup

Requirements: Node.js 20.9+ (a current supported LTS is recommended), npm, Python 3.11+, [uv](https://docs.astral.sh/uv/), and MongoDB Atlas (or local MongoDB) for durable application storage. Google Cloud access is required for live research and assistant answers. SQLite is retained as a process-local query cache and is restored from MongoDB at startup.

Run the setup commands from the repository root:

```sh
make setup
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Configure `backend/.env`:

```dotenv
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
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

Enable the Vertex AI API and grant the authenticated identity the necessary Vertex AI permissions. In a hosted environment, use an attached service account or workload identity. Keep credentials out of frontend variables and source control. Model selection is defined in `backend/app/config.py`: grounded research, chat, and intent routing use Flash-family models, while final guide synthesis uses `gemini-3.1-pro-preview`. A fast, tool-free scope check asks for genuinely missing requirements before searching; explicit data or action goals bypass generic clarification. Research is bounded to 240 seconds overall, with up to 150 seconds for search and 75 seconds for synthesis, plus optional passage verification. Chat allows 180 seconds; clarification routing and replies allow 60 and 90 seconds respectively. These limits are configurable in the backend environment.

Ensure the coded models are available in your project and region. The local `backend/.env` takes precedence over inherited shell settings for deployment configuration such as project and location; without that file, deployment environment variables apply. Restart the backend after editing configuration.

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
    API --> Cache[(SQLite query cache)]
    API --> Mongo[(MongoDB durable chats + metadata)]
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

The current full check passes 121 backend tests plus frontend lint, TypeScript, and the production build. Backend tests cover ownership, privacy, evidence validation, explicit authentication-versus-API-access choices, scoped conversation histories, mocked research success, interruptions, freshness, retry/reconnection, and grounding-link sanitization. A live Atlas snapshot-and-restore check reproduced 975 rows across all 11 metadata tables in a fresh database. Browser checks against development and production servers cover actual workspace interactions and real cloud error handling. Live Vertex research and both main/step chat answers are verified using the selected project.

On 2026-10-29, all five formal assignment scenarios passed against Cloud Run: the seeded Slack flow; Linear identity resolution, clarification, and genuine research with 12 streamed events; isolated multi-turn step discussions; an approval-time answer that explicitly withheld undocumented timing; and persisted step/discussion state with a public guide that excluded private chat content. The run exposed a stale provisional-provider matching conflict, which was fixed, regression-tested, deployed, and reverified. Production test chats were deleted after the checks.

The optional “Save finding to step” action has a confirmed-note API and rendering support, but its UI action is deferred. Actual provider OAuth registration and approval flows have not been completed. A checked implementation task is not evidence of a successful provider approval.

Run project checks with:

```sh
make check
```

## Google Cloud deployment

The tracked [`cloud/deploy-gcp.sh`](cloud/deploy-gcp.sh) script provisions the
runtime service accounts, grants the Cloud Run Builder role to the project build
identity, stores the MongoDB Atlas URI in Secret Manager, and deploys the
backend and frontend as separate Cloud Run services. Run it with:

```sh
PROJECT_ID=your-project-id \
GCLOUD_ACCOUNT=your-account@example.com \
cloud/deploy-gcp.sh
```

MongoDB stores chat documents directly and durable snapshots of all relational
metadata. The backend restores its SQLite query cache from the current atomic
MongoDB snapshot on startup. The deployment is intentionally capped at one
backend instance because this cache-and-snapshot design is single-writer.

The script is safe to rerun: named service accounts, secrets, repositories, and
Cloud Run services are reused. It also reuses the current MongoDB secret version.
Secret rotation requires both `ROTATE_MONGODB_SECRET=1` and `MONGODB_URI`.
Successful deployments create normal Cloud Run revisions and container image
versions, not duplicate services.

For evaluator stability, the script keeps one backend instance warm and verifies
MongoDB initialization, the provider API, and the frontend after deployment.
This incurs Cloud Run minimum-instance usage. Override it with
`BACKEND_MIN_INSTANCES=0` when cold starts are acceptable; MongoDB restoration
keeps data durable across revisions and instance replacement.

## Deployment

Deploy the frontend as a Node.js Next.js application and the backend as a Python ASGI service. Set the frontend's `NEXT_PUBLIC_API_URL` at build time, configure the backend's `FRONTEND_URL` to its exact browser origin, and use HTTPS in deployment. Allow the deployment host in MongoDB Atlas Network Access and store `MONGODB_URI` only in the backend secret manager.

Use the Atlas SRV URI through `MONGODB_URI`; never commit the real password. The optional `docker compose up -d mongo` command starts local MongoDB, which can be selected with `MONGODB_URI=mongodb://localhost:27017`. Chat records are indexed by the hashed device ID, thread, and creation time.

`GUIDE_FRESHNESS_DAYS` defaults to 30; older or undated evidence is flagged for refresh. CORS allows the exact frontend origins and the `X-Device-ID` header; the deployment script configures both Cloud Run-generated frontend URL aliases without using a wildcard. A device ID identifies one browser profile; clearing site storage intentionally starts a new private workspace identity.

Run the backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000` from `backend/`. Run `npm run build` followed by `npm start` from `frontend/`. Provide Google Cloud identity, model configuration, and the MongoDB URI to the backend only.

Deployed frontend: https://integration-copilot-web-ueqme4aywq-uc.a.run.app

Deployed API: https://integration-copilot-api-ueqme4aywq-uc.a.run.app

Source repository: https://github.com/arpandesai0/integration-copilot

Redeploying the same Cloud Run service in the same project and region keeps
these service URLs stable. Cloud Run creates a new internal revision name for
each deployment.

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
