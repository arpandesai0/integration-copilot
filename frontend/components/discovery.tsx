"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Globe2,
  Loader2,
  Terminal,
} from "lucide-react";
import { api, API_URL } from "@/lib/api";
import type { Provider, Workspace } from "@/lib/types";
import { Sidebar } from "./sidebar";
import { ThemeToggle } from "./theme-toggle";
import { ProviderIcon, ErrorBox } from "./common";

const providerDescriptions: Record<string, string> = {
  github: "Repository access, app registration, and permissions.",
  slack: "Workspace messaging, OAuth scopes, and distribution.",
  "google-drive": "File access, consent configuration, and verification.",
};

export function Discovery() {
  const [prompt, setPrompt] = useState("");
  const router = useRouter();
  const query = useQueryClient();
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<Provider[]>("/providers"),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch(API_URL + "/health");
      if (!response.ok) throw Error("Integration service unavailable");
      return response.json();
    },
    retry: 0,
  });
  const create = useMutation({
    mutationFn: (value: string) =>
      api<Workspace>("/workspaces", {
        method: "POST",
        body: JSON.stringify({ prompt: value }),
      }),
    onSuccess: (workspace) => {
      query.setQueryData(["workspace", workspace.id], workspace);
      query.setQueryData<Workspace[]>(["workspaces"], (saved = []) =>
        saved.some((item) => item.id === workspace.id)
          ? saved
          : [workspace, ...saved],
      );
      router.push(`/workspaces/${workspace.id}`);
    },
  });
  const catalog = providers.data || [];
  const matches = prompt.trim()
    ? catalog.filter((provider) =>
        [provider.name, provider.slug, ...(provider.aliases || [])].some(
          (value) =>
            value.toLowerCase().includes(prompt.toLowerCase()) ||
            prompt.toLowerCase().includes(value.toLowerCase()),
        ),
      )
    : [];

  return (
    <div className="discovery-shell">
      <Sidebar />
      <main
        className="discovery-main"
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          background: "var(--panel)",
        }}
      >
        <header className="workspace-topbar">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 13,
            }}
          >
            <span>New integration</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              className="service-status mono"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                fontSize: 10,
              }}
            >
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: health.isSuccess
                    ? "var(--success, #60b889)"
                    : "var(--muted)",
                }}
              />
              {health.isSuccess
                ? "SERVICE CONNECTED"
                : health.isError
                  ? "SERVICE UNAVAILABLE"
                  : "CONNECTING"}
            </span>
            <ThemeToggle />
          </div>
        </header>

        <div
          className="discovery-content"
          style={{
            width: "100%",
            maxWidth: 1000,
            margin: "0 auto",
            padding: "28px 40px 24px",
            flexShrink: 0,
          }}
        >
          <div
            className="mono"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              fontSize: 11,
              letterSpacing: ".07em",
              color: "var(--muted)",
              marginBottom: 12,
            }}
          >
            <span
              style={{ width: 7, height: 7, background: "var(--accent)" }}
            />
            INTEGRATION COPILOT
          </div>
          <h1
            style={{
              fontSize: "clamp(28px,3vw,36px)",
              fontWeight: 500,
              lineHeight: 1.15,
              letterSpacing: "-1.7px",
              margin: "0 0 10px",
            }}
          >
            What do you want to connect?
          </h1>
          <p
            className="muted"
            style={{
              fontSize: 14,
              lineHeight: 1.6,
              maxWidth: 600,
              margin: "0 0 20px",
            }}
          >
            Go from an integration idea to a working setup. Get the
            requirements, setup steps, and answers in one place.
          </p>

          <form
            className="integration-prompt"
            onSubmit={(event) => {
              event.preventDefault();
              if (prompt.trim() && !create.isPending)
                create.mutate(prompt.trim());
            }}
            style={{
              border: "1px solid var(--border)",
              borderRadius: 6,
              background: "var(--raised, var(--background))",
              overflow: "visible",
              position: "relative",
            }}
          >
            <label
              htmlFor="integration-search"
              className="mono"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 11,
                color: "var(--muted)",
                padding: "12px 16px 0",
              }}
            >
              <Terminal size={14} /> DESCRIBE YOUR INTEGRATION
            </label>
            <textarea
              id="integration-search"
              aria-label="Describe your integration"
              placeholder="e.g. Help my customers connect their Slack accounts"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  if (prompt.trim() && !create.isPending)
                    create.mutate(prompt.trim());
                }
              }}
              style={{
                display: "block",
                width: "100%",
                minHeight: 56,
                height: 56,
                padding: "10px 16px",
                border: 0,
                resize: "none",
                outline: "none",
                background: "transparent",
                fontSize: 14,
                lineHeight: 1.5,
              }}
            />
            <div
              className="prompt-actions"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "8px 12px 8px 16px",
                borderTop: "1px solid var(--border)",
              }}
            >
              <span
                className="muted"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                }}
              >
                <Globe2 size={13} /> Start with an app name or website
              </span>
              <button
                className="btn primary"
                disabled={!prompt.trim() || create.isPending}
                type="submit"
                style={{ minHeight: 32, padding: "6px 11px", fontSize: 12 }}
              >
                {create.isPending ? (
                  <Loader2 size={14} className="spinner" />
                ) : null}
                Create integration <ArrowRight size={14} />
              </button>
            </div>
            {matches.length > 0 && (
              <div
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 5,
                  overflow: "hidden",
                  marginTop: 6,
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  zIndex: 10,
                  boxShadow: "0 8px 24px #0003",
                }}
              >
                {matches.map((provider) => (
                  <button
                    key={provider.id}
                    className="provider-match"
                    type="button"
                    onClick={() => create.mutate(prompt || provider.name)}
                    disabled={create.isPending}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      textAlign: "left",
                      padding: "13px 16px",
                      border: 0,
                      borderBottom: "1px solid var(--border)",
                      background: "var(--raised, var(--background))",
                    }}
                  >
                    <ProviderIcon provider={provider} size={28} />
                    <strong style={{ fontSize: 13, fontWeight: 500 }}>
                      {provider.name}
                    </strong>
                    <span
                      className="muted"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        marginLeft: "auto",
                        fontSize: 11,
                      }}
                    >
                      Open guide <ArrowUpRight size={13} />
                    </span>
                  </button>
                ))}
              </div>
            )}
          </form>
          {create.error && (
            <div style={{ marginTop: 12 }}>
              <ErrorBox error={create.error} />
            </div>
          )}
          {(health.isError || providers.isError) && (
            <div className="error" style={{ marginTop: 12 }}>
              Unable to reach the integration service. Start the backend and
              refresh this page.
            </div>
          )}

          <section
            style={{ marginTop: 24 }}
            aria-labelledby="provider-library-title"
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
                marginBottom: 12,
              }}
            >
              <h2
                id="provider-library-title"
                style={{ fontSize: 14, fontWeight: 500, margin: 0 }}
              >
                Start with a provider
              </h2>
              <span
                className="mono muted"
                style={{ fontSize: 10, letterSpacing: ".035em" }}
              >
                RESEARCHED GUIDES
              </span>
            </div>
            <div
              className="provider-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0,1fr))",
                gap: 12,
              }}
            >
              {catalog.slice(0, 3).map((provider) => (
                <button
                  key={provider.id}
                  className="provider-card"
                  aria-label={`${provider.name} OAuth setup guide`}
                  disabled={create.isPending}
                  onClick={() =>
                    create.mutate(`Help me integrate ${provider.name}`)
                  }
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    padding: 14,
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    background: "var(--panel)",
                    textAlign: "left",
                    minHeight: 126,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      width: "100%",
                      marginBottom: 12,
                    }}
                  >
                    <ProviderIcon provider={provider} size={28} />
                    <ArrowUpRight size={15} className="muted" />
                  </div>
                  <span
                    style={{ fontSize: 13, fontWeight: 500, marginBottom: 5 }}
                  >
                    {provider.name}
                  </span>
                  <span
                    className="muted"
                    style={{ fontSize: 12, lineHeight: 1.5 }}
                  >
                    {providerDescriptions[provider.slug] ||
                      "Authentication, configuration, and launch requirements."}
                  </span>
                </button>
              ))}
              {providers.isPending &&
                [0, 1, 2].map((index) => (
                  <div
                    className="skeleton"
                    style={{ height: 126 }}
                    key={index}
                  />
                ))}
            </div>
          </section>

          <p
            className="muted"
            style={{ fontSize: 12, lineHeight: 1.5, margin: "16px 0 0" }}
          >
            Another provider? Enter its name or website above to check
            integration support.
          </p>
        </div>
      </main>
    </div>
  );
}
