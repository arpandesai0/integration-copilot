# Assignment agent evaluation — 29 October 2026

This is an internal diagnostic evaluation and prompt/workflow tuning pass, not model-weight training or a claim of production accuracy.

## Dataset and method

The separate evaluation agent built 26 baseline cases from `docs/agents/AGENT.md` and the subsequent product feedback. They cover provider ambiguity, typos, OAuth versus sign-in, repeated auth answers, thanks, known seeded guides, minimum scopes, distribution/review, step-level troubleshooting, injection, unfamiliar supported providers, gated providers, and an invented provider. Dialpad SAML was added as a 27th regression after the reported chat exposed an OAuth-only assumption.

Runner: `backend/evals/run_assignment_eval.py`; cases: `backend/evals/cases.json`. Live evaluation uses the configured Vertex models and a temporary SQLite database. User records were not used as the eval database. Results preserve model outputs, timing, source metadata and structural checks. These checks are proxies, not factual-correctness scores. The baseline and intermediate failed runs are retained.

Example rerun:

```sh
cd backend
.venv/bin/python evals/run_assignment_eval.py --label local-check --ids chat_thanks,chat_slack_scope,research_google_login,research_jira_tickets,research_dialpad_saml
```

## Baseline findings

The original 26-case baseline had 21 automated passes and five failures. One failure was a rubric error: explicitly refusing a malicious URL was penalized for quoting the rejected URL. Refusals also do not need external citations. These checks were corrected; original results were not overwritten.

Observed product failures included:

- A Slack bot-message question could not answer `chat:write` because its supplied guide lacked the method documentation. Added the official [chat.postMessage reference](https://docs.slack.dev/reference/methods/chat.postMessage/) and reviewed source passage.
- Legitimate OAuth endpoints with query parameters could be rejected as a different endpoint. Matching now compares scheme, authority and exact path, retaining the rejection of invented endpoint prefixes.
- Source-evidence quotations could fail because Markdown emphasis or acronym expansions were omitted. Matching tolerates those formatting differences, while preserving words and negation checks. This is research consistency, not independent document verification.
- SDK-based identity flows and SAML were incorrectly required to supply OAuth code-exchange endpoints. Added explicit authentication methods and separate documented workflow evidence. Non-OAuth labels cannot bypass evidence checks.
- Some short chat replies had very high latency: the baseline thanks case took 64.31 seconds, including 64.20 seconds to first token. Configurable `GEMINI_CHAT_MODEL` now uses the locally configured fast model; the primary model remains the fallback elsewhere.
- Main-thread messages from older clients could bypass clarification and answer in ordinary prose. Pending or unverified requests now route server-side through streamed clarification and investigation.
- Generated live estimates sometimes asserted unsupported approval durations. Live synthesis no longer persists numeric time estimates without a dedicated reviewed estimate-evidence mechanism.

## Handoff and complete workflows

Clarification determines the actual goal and protocol. Once sufficient, it hands off to the investigation workflow with the exact user answers. Investigation performs focused source lookup and structured synthesis; successful supported cases render setup stages rather than an ordinary chat paragraph. The synthesis instructions require registration/prerequisites, configuration, implementation, and end-to-end verification, with protocol-appropriate details.

Both reported records were regenerated with previous versions retained:

- Dialpad SAML: four stages; initial corrected investigation 12.27 seconds.
- Google OIDC: four stages after completeness tuning; 14.22 seconds.

Dialpad's official [SAML setup documentation](https://help.dialpad.com/hc/en-us/articles/55093970091803-Integrating-JumpCloud-SAML-SSO-with-Dialpad) supports SP/IdP metadata exchange, attribute mapping, assignments and login testing. Lack of public OAuth endpoints is not evidence against that SAML workflow.

## Final targeted reruns

These are six targeted cases, not a rerun of all 27 cases.

| Case | Result | Observed duration |
| --- | --- | --- |
| Brief thanks | Pass | 1.74 s |
| Minimum Slack bot-message scope | Pass | 2.91 s |
| Injection refusal | Pass under corrected rubric | 2.32 s |
| Google sign-in workflow | Pass | 15.46 s |
| Jira ticket-access workflow | Pass | 17.85 s |
| Dialpad SAML workflow | Pass | 15.36 s |

Artifacts: `backend/evals/results/chat-final-reviewed.json` and `backend/evals/results/research-final.json`. The reviewed chat artifact changes only rubric scoring; it retains the original output and timing in `chat-final.json`.

Validation: 114 backend tests passed. Frontend lint, typecheck and production build passed. Browser fixtures verified both repaired guides render four actionable stages. Regression tests cover older-client handoff, genuine streaming, cancellation, exact endpoint paths with query strings, evidence negation, and documented SAML without OAuth endpoints.

## Remaining findings and limits

- Manual baseline review found some PSN/Relyance conclusions citing community or unrelated-vendor sources. A conservative support label alone does not make such claims reliable. Provider-authority verification remains a separate unresolved finding; do not count these as factual passes.
- The invented-provider baseline returned a no-source research failure instead of an ideal provider-identity clarification. Its graceful UI is present, but its agent-level fallback remains to improve.
- The eval subagent stopped at its usage limit after saving its baseline and partial edits. The root agent completed the handoff fixes, targeted reruns and report. The full baseline suite was not rerun after all changes.
- Timings are samples from this local project, not latency guarantees. Citation presence and retained source IDs do not prove that every sentence is supported, or that the real integration was executed/tested.
