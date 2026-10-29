"use client";
import { ArrowUpRight, BookOpen, MessageSquare } from "lucide-react";
import type { ClaimCitation, Guide, Source, Step } from "@/lib/types";
import { CopyButton, CopyableLink, ResponseContent } from "./response-content";
import { InlineCitations } from "./inline-citations";
import { titleCase } from "./common";

export function needsClarification(guide: Guide): boolean {
  if (typeof guide.clarification_needed === "boolean")
    return guide.clarification_needed;
  return (
    !!guide.clarification_needed ||
    (guide.steps.length === 0 &&
      (guide.oauth_support_status ??
        guide.provider.oauth_support_status ??
        "unknown") === "unknown")
  );
}

function clarificationQuestion(guide: Guide): string {
  const explicit = guide.clarification_questions
    ?.find((question) => question.trim())
    ?.trim();
  if (
    explicit &&
    explicit !== "Which provider capability do you need to access?"
  )
    return explicit;
  const question = guide.uncertainties?.find(
    (item) => item.trim().endsWith("?") && item.trim().length <= 240,
  );
  return (
    (question !== "Which provider capability do you need to access?"
      ? question
      : undefined) ||
    `What would you like your integration with ${guide.provider.name} to do?`
  );
}

export function GuideView({
  guide,
  selectedStep,
  onDiscuss,
  readOnly = false,
}: {
  guide: Guide;
  selectedStep?: string;
  onDiscuss?: (s: Step) => void;
  readOnly?: boolean;
}) {
  if (needsClarification(guide)) {
    return (
      <div className="guide-clarification">
        <ResponseContent>{clarificationQuestion(guide)}</ResponseContent>
        {readOnly && (
          <p className="muted" style={{ marginTop: 12 }}>
            This request needs clarification before a setup guide can be
            prepared.
          </p>
        )}
      </div>
    );
  }

  if (guide.steps.length === 0) {
    return (
      <div className="guide-limitation">
        <ResponseContent
          sources={guide.sources}
          trailing={citationNote(
            guide.citations,
            "summary",
            undefined,
            guide.sources,
          )}
        >
          {guide.summary}
        </ResponseContent>
      </div>
    );
  }

  return (
    <article className="guide-view">
      {readOnly && guide.guide_is_stale && (
        <div className="guide-notice">
          This guide needs a freshness check. Sources have not been checked
          within {guide.freshness_days || 30} days. Confirm current requirements
          before proceeding.
        </div>
      )}
      <header
        className="guide-overview"
        style={{ paddingBottom: 26, borderBottom: "1px solid var(--border)" }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 16,
          }}
        >
          <span className="label">Integration guide</span>
          <span className="badge mono">
            v{guide.version_number.toString().padStart(2, "0")}
          </span>
        </div>
        <h1
          style={{
            fontSize: "clamp(27px, 2.4vw, 34px)",
            fontWeight: 550,
            letterSpacing: "-1.2px",
            lineHeight: 1.2,
            margin: "0 0 14px",
          }}
        >
          Set up {guide.provider.name}
        </h1>
        <div
          className="muted"
          style={{ fontSize: 14, lineHeight: 1.75, margin: 0 }}
        >
          <ResponseContent
            sources={guide.sources}
            trailing={citationNote(
              guide.citations,
              "summary",
              undefined,
              guide.sources,
            )}
          >
            {guide.summary}
          </ResponseContent>
        </div>
        <details className="guide-estimates" open>
          <summary>Effort &amp; approval estimates</summary>
          <div
            className="guide-metrics"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3,minmax(0,1fr))",
              marginTop: 25,
              border: "1px solid var(--border)",
              borderRadius: 5,
              overflow: "hidden",
            }}
          >
            <Metric label="Complexity" value={titleCase(guide.difficulty)} />
            <Metric
              label="Hands-on time"
              value={
                guide.estimated_setup_minutes == null
                  ? "Not established"
                  : `~${guide.estimated_setup_minutes} minutes`
              }
            />
            <Metric
              label="Approval wait"
              value={
                guide.estimated_approval_days == null
                  ? "Not established"
                  : `~${guide.estimated_approval_days} days`
              }
            />
          </div>
        </details>
        <div
          className="muted"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontSize: 12,
            marginTop: 13,
          }}
        >
          <BookOpen size={13} /> {guide.sources.length} supporting sources{" "}
          <span style={{ margin: "0 3px" }}>·</span> Setup confidence:{" "}
          {titleCase(guide.setup_confidence)}
        </div>
      </header>
      <section
        style={{ padding: "24px 0", borderBottom: "1px solid var(--border)" }}
      >
        <h2 className="label" style={{ margin: "0 0 10px" }}>
          Recommended approach
        </h2>
        <ResponseContent
          sources={guide.sources}
          trailing={citationNote(
            guide.citations,
            "recommended_auth_path",
            undefined,
            guide.sources,
          )}
        >
          {guide.recommended_auth_path}
        </ResponseContent>
        <DetailList
          title="Before you begin"
          items={guide.prerequisites}
          field="prerequisites"
          citations={guide.citations}
          sources={guide.sources}
        />
        <DetailList
          title="Assumptions behind this guide"
          items={guide.assumptions}
        />
      </section>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: 24,
          marginBottom: 14,
        }}
      >
        <h2
          style={{
            fontSize: 17,
            letterSpacing: "-.3px",
            fontWeight: 550,
            margin: 0,
          }}
        >
          Setup steps
        </h2>
        <span className="muted mono" style={{ fontSize: 12 }}>
          {guide.steps.length} steps
        </span>
      </div>
      {guide.steps.map((step, i) => (
        <section
          className={`guide-step${selectedStep === step.id ? " is-selected" : ""}`}
          id={`step-${step.id}`}
          key={step.id}
          style={{
            scrollMarginTop: 20,
            border: "1px solid",
            borderColor:
              selectedStep === step.id ? "var(--accent)" : "var(--border)",
            borderRadius: 5,
            marginBottom: 14,
            overflow: "hidden",
            background: "var(--panel)",
          }}
        >
          <div
            className="guide-step-header"
            style={{
              padding: "19px 20px 15px",
              display: "flex",
              alignItems: "flex-start",
              gap: 13,
            }}
          >
            <span
              className="mono"
              style={{
                width: 28,
                height: 28,
                border: "1px solid var(--border)",
                borderRadius: 4,
                background: "var(--raised)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                color: "var(--muted)",
                fontSize: 11,
              }}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h3
                style={{
                  fontSize: 14,
                  fontWeight: 550,
                  lineHeight: 1.5,
                  margin: "2px 0 7px",
                }}
              >
                {step.title}
              </h3>
              <div
                className="muted"
                style={{ fontSize: 13, lineHeight: 1.7, margin: 0 }}
              >
                <ResponseContent
                  sources={guide.sources}
                  trailing={citationNote(
                    step.citations,
                    "description",
                    undefined,
                    guide.sources,
                    step.stable_key,
                  )}
                >
                  {step.description}
                </ResponseContent>
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 7,
                  marginTop: 12,
                }}
              >
                <StepOwner actor={step.actor} />
                {step.estimated_minutes != null && (
                  <span className="badge mono">
                    {step.estimated_minutes} min
                  </span>
                )}
              </div>
            </div>
            <CopyButton
              value={step.instructions
                .map((instruction, index) => `${index + 1}. ${instruction}`)
                .join("\n\n")}
              label="Copy step instructions"
              className="step-copy"
            />
          </div>
          <div
            className="guide-step-body"
            style={{ padding: "0 20px 20px 61px" }}
          >
            <ol
              className="instruction-list"
              style={{
                fontSize: 13,
                lineHeight: 1.85,
                paddingLeft: 17,
                margin: "0 0 14px",
                color: "var(--foreground)",
              }}
            >
              {step.instructions.map((instruction, n) => (
                <li
                  key={n}
                  style={{
                    marginBottom: 7,
                    overflowWrap: "anywhere",
                    paddingLeft: 3,
                  }}
                >
                  <ResponseContent
                    technical
                    sources={guide.sources}
                    trailing={citationNote(
                      step.citations,
                      "instructions",
                      n,
                      guide.sources,
                      step.stable_key,
                    )}
                  >
                    {instruction}
                  </ResponseContent>
                </li>
              ))}
            </ol>
            {step.warnings.map((warning, n) => (
              <div
                key={n}
                className="guide-warning"
                style={{
                  fontSize: 12,
                  lineHeight: 1.75,
                  margin: "12px 0",
                  borderLeft: "2px solid #a78036",
                  paddingLeft: 12,
                  color: "var(--muted)",
                }}
              >
                <ResponseContent
                  technical
                  sources={guide.sources}
                  trailing={citationNote(
                    step.citations,
                    "warnings",
                    n,
                    guide.sources,
                    step.stable_key,
                  )}
                >
                  {warning}
                </ResponseContent>
              </div>
            ))}
            {step.notes?.map((note) => (
              <div
                key={note.id}
                style={{
                  background: "var(--raised)",
                  border: "1px solid var(--border)",
                  padding: 12,
                  fontSize: 13,
                  lineHeight: 1.7,
                  margin: "12px 0",
                }}
              >
                <strong>Saved finding:</strong>{" "}
                <ResponseContent technical sources={guide.sources}>
                  {note.content}
                </ResponseContent>
              </div>
            ))}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginTop: 15,
              }}
            >
              {!readOnly && (
                <button className="btn" onClick={() => onDiscuss?.(step)}>
                  <MessageSquare size={13} /> Ask about this step
                </button>
              )}
              {step.action_url && (
                <CopyableLink
                  href={step.action_url}
                  className="action-copy-link"
                  linkClassName="btn"
                >
                  Open provider console <ArrowUpRight size={13} />
                </CopyableLink>
              )}
            </div>
          </div>
        </section>
      ))}
      <section
        style={{
          borderTop: "1px solid var(--border)",
          padding: "28px 0",
          marginTop: 30,
        }}
      >
        <h2
          style={{
            fontSize: 17,
            fontWeight: 550,
            letterSpacing: "-.3px",
            margin: "0 0 14px",
          }}
        >
          Distribution & approval
        </h2>
        <ResponseContent
          sources={guide.sources}
          trailing={citationNote(
            guide.citations,
            "approval_requirement",
            undefined,
            guide.sources,
          )}
        >
          {guide.approval_requirement}
        </ResponseContent>
        <div className="muted" style={{ fontSize: 12, lineHeight: 1.8 }}>
          Approval estimate confidence: {titleCase(guide.approval_confidence)}
        </div>
        <DetailList
          title="Approval materials"
          items={guide.approval_materials}
          field="approval_materials"
          citations={guide.citations}
          sources={guide.sources}
        />
        <DetailList
          title="While you wait"
          items={guide.while_waiting}
          field="while_waiting"
          citations={guide.citations}
          sources={guide.sources}
        />
        <DetailList
          title="Uncertainties"
          items={guide.uncertainties}
          field="uncertainties"
          citations={guide.citations}
          sources={guide.sources}
        />
        {!!guide.blockers.length && (
          <>
            <h3 style={{ fontSize: 14, margin: "24px 0 12px" }}>
              Potential blockers
            </h3>
            {guide.blockers.map((b, i) => (
              <div
                key={i}
                style={{
                  background: "var(--raised)",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                  padding: 15,
                  fontSize: 13,
                  lineHeight: 1.8,
                  color: "var(--muted)",
                  marginBottom: 12,
                }}
              >
                {typeof b === "string" ? (
                  b
                ) : (
                  <>
                    <strong style={{ color: "var(--foreground)" }}>
                      {b.description}
                    </strong>
                    <InlineCitations
                      sourceIds={b.source_ids || []}
                      sources={guide.sources}
                      label="Blocker evidence"
                    />
                    <div>Impact: {b.impact || "Unknown"}</div>
                    <div>
                      Resolution: {b.resolution || "Needs investigation"}
                    </div>
                    <div>
                      {b.human_required
                        ? "Requires human action"
                        : "Agent assistance possible"}
                    </div>
                  </>
                )}
              </div>
            ))}
          </>
        )}
      </section>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "15px 16px",
        borderRight: "1px solid var(--border)",
        background: "var(--raised)",
        minWidth: 0,
      }}
    >
      <div className="label" style={{ marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.6, fontWeight: 500 }}>
        {value}
      </div>
    </div>
  );
}

function StepOwner({ actor }: { actor: string }) {
  const ownership: Record<string, { label: string; description: string }> = {
    developer: {
      label: "You do this",
      description: "This step requires action from you as the developer",
    },
    agent: {
      label: "Agent can do this",
      description: "This step can be handled by the agent",
    },
    human: {
      label: "Human action",
      description: "This step requires a person to take action",
    },
    administrator: {
      label: "Admin action",
      description: "This step requires an administrator to take action",
    },
    provider: {
      label: "Provider action",
      description: "This step depends on action from the provider",
    },
  };
  const owner = ownership[actor] || {
    label: titleCase(actor),
    description: `This step is owned by ${titleCase(actor)}`,
  };
  return (
    <span
      className="badge"
      aria-label={owner.description}
      title={owner.description}
    >
      {owner.label}
    </span>
  );
}

function citationNote(
  citations: ClaimCitation[] | undefined,
  field: string,
  index: number | undefined,
  sources: Source[],
  stepKey?: string,
) {
  const mapped = (citations || []).filter(
    (citation) =>
      citation.field === field && (citation.index ?? undefined) === index,
  );
  if (!mapped.length) return null;
  return (
    <InlineCitations
      sourceIds={mapped.flatMap((citation) => citation.source_ids)}
      sources={sources}
      stepKey={stepKey}
      label={
        mapped.some((citation) => citation.scope === "step")
          ? "Step evidence"
          : "Source"
      }
    />
  );
}

function DetailList({
  title,
  items,
  field,
  citations,
  sources = [],
}: {
  title: string;
  items?: string[];
  field?: string;
  citations?: ClaimCitation[];
  sources?: Source[];
}) {
  return items?.length ? (
    <details style={{ marginTop: 15 }}>
      <summary
        style={{
          fontSize: 12,
          cursor: "pointer",
          color: "var(--muted)",
          lineHeight: 1.6,
        }}
      >
        {title}{" "}
        <span className="mono" style={{ opacity: 0.7, marginLeft: 5 }}>
          {items.length}
        </span>
      </summary>
      <ul
        style={{
          fontSize: 13,
          lineHeight: 1.8,
          paddingLeft: 19,
          color: "var(--muted)",
          margin: "12px 0 0",
        }}
      >
        {items.map((item, i) => (
          <li key={i}>
            <ResponseContent
              technical
              sources={sources}
              trailing={
                field ? citationNote(citations, field, i, sources) : null
              }
            >
              {item}
            </ResponseContent>
          </li>
        ))}
      </ul>
    </details>
  ) : null;
}
