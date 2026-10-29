# Integration Copilot Submission

## Working experience

https://integration-copilot-web-ueqme4aywq-uc.a.run.app

## Source repository

https://github.com/arpandesai0/integration-copilot

## Product summary

Integration Copilot helps developers understand how to configure, test, distribute, and seek approval for provider OAuth applications.

Developers can open reviewed guides for GitHub, Slack, and Google Drive or enter an unfamiliar provider for live, source-backed research. Each guide includes an authentication recommendation, prerequisites, permissions, setup steps, rough timing, blockers, approval considerations, evidence, and a next action.

Developers can also ask questions in the main chat or open a discussion attached to a specific guide step. Step discussions retain their own context and history. A read-only guide can be shared without exposing private conversations.

## Setup and documentation

The repository [README](https://github.com/arpandesai0/integration-copilot#readme) contains:

- Local frontend and backend setup instructions
- Required environment variables
- Google Cloud and Vertex AI configuration
- MongoDB configuration
- Architecture and product decisions
- Deployment instructions
- Test commands
- Evidence methodology
- Current limitations

## Key decisions

- **Chat-first discovery:** Developers can describe an integration goal without knowing the provider's terminology.
- **Authentication choice before instructions:** Reviewed guides distinguish login from API authorization. For example, GitHub separates Sign in with GitHub from a GitHub App, Slack separates Sign in with Slack from workspace installation, and Google separates login from Drive file authorization.
- **Evidence before confidence:** Important claims link to official documentation. Unsupported timing or approval claims remain uncertain rather than being presented as facts.
- **Reviewed and researched paths:** Known providers load immediately. Unfamiliar providers trigger genuine research and structured guide generation.
- **Step-level discussions:** Troubleshooting stays attached to the relevant guide step instead of being mixed into one conversation.
- **Private device-scoped history:** A browser-generated device identifier owns private chats. The backend stores its hash rather than the raw identifier.
- **Safe sharing:** Public links contain guide content and sources but exclude private chats and ownership data.
- **Focused deployment:** The application runs as separate Next.js and FastAPI services on Cloud Run, with MongoDB used for durable chat and application metadata.

## Verification

- 121 backend tests pass.
- Frontend lint, TypeScript checks, and the production build pass.
- All five assignment scenarios were verified against the deployed application.
- Live Linear research completed with streamed progress and persisted evidence.
- Main and step-level assistant responses were verified with live Vertex AI calls.
- MongoDB chat storage and metadata restoration were tested end to end.
- Public-guide privacy and cross-device access isolation were verified.

## Limitations

- Integration Copilot provides setup guidance; it does not register or submit OAuth applications on the developer's behalf.
- It does not store provider client secrets, customer OAuth tokens, or refresh tokens.
- A documented requirement is not labeled as tested unless the corresponding provider flow was actually executed.
- Approval duration varies by provider, scopes, distribution model, organization policy, and reviewer feedback. The reviewed demo guides include clearly labeled inferred planning estimates, not provider SLAs.
- Live research quality depends on available official documentation and the configured Vertex AI service.
- Research jobs run in the backend process and are not yet managed by a durable external job queue.
- Device-based ownership is appropriate for this focused demonstration but is not a replacement for production user accounts and account recovery.
- The deployment is intentionally limited to one backend writer because SQLite is used as an in-process query cache restored from atomic MongoDB snapshots.

## Scope

The submission demonstrates three reviewed providers and live generation for unfamiliar providers. It does not attempt to build the full target library of 100 applications, complete real provider approvals, or provide a production OAuth proxy.
