"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Copy,
  ExternalLink,
  Loader2,
  RefreshCw,
  Share2,
  BookOpen,
  X,
} from "lucide-react";
import { sourceHref } from "@/lib/source-links";
import { api, stream } from "@/lib/api";
import type {
  Guide,
  Step,
  Thread,
  Workspace as WorkspaceType,
} from "@/lib/types";
import { Sidebar } from "./sidebar";
import { ThemeToggle } from "./theme-toggle";
import { ErrorBox, Loading, titleCase } from "./common";
import { GuideScrollProgress } from "./guide-scroll-progress";
import { GuideView, needsClarification } from "./guide";
import { Composer, Messages } from "./chat";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "./ui/resizable";
import { Sheet, SheetContent, SheetTitle } from "./ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
export function Workspace({ id }: { id: string }) {
  const query = useQueryClient();
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const selectedId = params.get("step") || undefined;
  const threadId = params.get("thread") || undefined;
  const [panelOpen, setPanelOpen] = useState(!!selectedId);
  const [narrow, setNarrow] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [mutationError, setMutationError] = useState<unknown>();
  const activeByStep = useRef<Record<string, string>>({});
  const scroll = useRef<HTMLDivElement>(null);
  const workspace = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => api<WorkspaceType>(`/workspaces/${id}`),
  });
  const guide = useQuery({
    queryKey: ["guide", id],
    queryFn: () => api<Guide>(`/workspaces/${id}/guide`),
    enabled: !!workspace.data?.guide_available,
    retry: 0,
  });
  const threads = useQuery({
    queryKey: ["threads", id],
    queryFn: () => api<Thread[]>(`/workspaces/${id}/threads`),
    enabled: !!workspace.data,
  });
  const linkedThread = threads.data?.find(
    (t) => t.id === threadId && t.type === "step",
  );
  const currentStep = guide.data?.steps.find(
    (s) =>
      s.id === selectedId ||
      (linkedThread?.step_stable_key &&
        s.stable_key === linkedThread.step_stable_key),
  );
  const selected: Step | undefined =
    currentStep ||
    (linkedThread && linkedThread.step_id === selectedId
      ? {
          id: selectedId!,
          stable_key: linkedThread.step_stable_key || selectedId!,
          title: linkedThread.title,
          description:
            "This discussion belongs to an earlier guide version. Its assistant continues using that version’s step requirements and evidence.",
          instructions: [],
          status: "needs_verification",
          actor: "developer",
          source_ids: [],
          warnings: [],
        }
      : undefined);
  const matchesStep = (thread: Thread, step: Step) =>
    thread.type === "step" &&
    (thread.step_id === step.id ||
      (!!thread.step_stable_key && thread.step_stable_key === step.stable_key));
  const activeThread =
    selected && linkedThread && matchesStep(linkedThread, selected)
      ? linkedThread
      : undefined;
  const mainThreadId =
    workspace.data?.main_thread_id ||
    threads.data?.find((t) => t.type === "main")?.id;
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1050px)");
    const listener = () => setNarrow(media.matches);
    listener();
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPanelOpen(false);
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        router.push("/");
        setTimeout(
          () => document.getElementById("integration-search")?.focus(),
          100,
        );
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [router]);
  const navigate = (stepId: string, thread?: string) => {
    const next = new URLSearchParams();
    next.set("step", stepId);
    if (thread) next.set("thread", thread);
    router.replace(`${pathname}?${next}`, { scroll: false });
    if (thread) activeByStep.current[stepId] = thread;
  };
  const createThread = useMutation({
    mutationFn: async (step: Step) => {
      const saved = await query.ensureQueryData<Thread[]>({
        queryKey: ["threads", id],
        queryFn: () => api<Thread[]>(`/workspaces/${id}/threads`),
      });
      const existing = saved.find((thread) => matchesStep(thread, step));
      if (existing) return existing;
      return api<Thread>(`/workspaces/${id}/threads`, {
        method: "POST",
        body: JSON.stringify({
          type: "step",
          step_id: step.id,
          parent_thread_id: mainThreadId,
          title: step.title,
        }),
      });
    },
    onSuccess: (thread, step) => {
      query.setQueryData<Thread[]>(["threads", id], (saved = []) =>
        saved.some((item) => item.id === thread.id)
          ? saved
          : [...saved, thread],
      );
      navigate(step.id, thread.id);
      setPanelOpen(true);
    },
    onError: setMutationError,
  });
  const openStep = (step: Step, discuss = false) => {
    const remembered = activeByStep.current[step.id];
    const existing =
      threads.data?.find((t) => t.id === remembered && matchesStep(t, step)) ||
      threads.data?.find((t) => matchesStep(t, step));
    navigate(step.id, existing?.id);
    document
      .getElementById(`step-${step.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (discuss) {
      setPanelOpen(true);
      if (!existing && !createThread.isPending) createThread.mutate(step);
    } else if (panelOpen && !existing) {
      /* Keep this step's empty discussion visible. */
    }
  };
  if (workspace.isPending) return <Loading />;
  if (workspace.error)
    return (
      <main style={{ maxWidth: 650, margin: "70px auto", padding: 30 }}>
        <ErrorBox error={workspace.error} />
        <Link className="btn" href="/" style={{ marginTop: 15 }}>
          <ArrowLeft size={13} /> Return home
        </Link>
      </main>
    );
  const w = workspace.data;
  const g = guide.data;
  const needsContext =
    !!(g && needsClarification(g)) ||
    (!g &&
      [
        "research_failed",
        "research_cancelled",
        "awaiting_clarification",
      ].includes(w.status));
  const discussion = selected ? (
    <section className="step-subchat" aria-label="Step sub-chat">
      <header className="step-subchat-header">
        <div>
          <div className="label">
            Step{" "}
            {currentStep
              ? String(
                  (g?.steps.findIndex((s) => s.id === selected.id) ?? 0) + 1,
                ).padStart(2, "0")
              : "chat"}
          </div>
          <h2>{selected.title}</h2>
        </div>
        <button
          className="icon-btn"
          aria-label="Close step discussion"
          onClick={() => setPanelOpen(false)}
        >
          <X size={16} />
        </button>
      </header>
      <div className="step-subchat-messages">
        {createThread.isError && !activeThread ? (
          <>
            <ErrorBox error={createThread.error} />
            <button
              className="btn"
              onClick={() => createThread.mutate(selected)}
            >
              Retry
            </button>
          </>
        ) : activeThread ? (
          <>
            {activeThread.guide_version_id !== g?.id && (
              <p className="muted" style={{ fontSize: 12 }}>
                Using this chat’s original guide context.
              </p>
            )}
            <Messages
              threadId={activeThread.id}
              sources={g?.sources.map((source) => ({
                ...source,
                text_fragment_url: sourceHref(source, selected.stable_key),
              }))}
              emptyText="Ask a question about this step."
              scrollToLatest
            />
          </>
        ) : (
          <p className="muted" style={{ fontSize: 13 }}>
            Opening chat…
          </p>
        )}
      </div>
      <Composer
        key={activeThread?.id || selected.id}
        threadId={activeThread?.id}
        placeholder="Ask anything about this step..."
        autofocus
      />
    </section>
  ) : null;
  return (
    <div className="workspace-shell">
      <Sidebar workspace={w} />
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          background: "var(--panel)",
        }}
      >
        <header className="workspace-toolbar">
          <Link
            href="/"
            className="icon-btn mobile-chat-home"
            aria-label="Back to integrations"
            title="Back to integrations"
          >
            <ArrowLeft size={17} />
          </Link>
          <div className="workspace-toolbar-actions">
            <button
              className="icon-btn"
              aria-label="Share guide"
              title="Share guide"
              disabled={!g || needsClarification(g)}
              onClick={() => setShareOpen(true)}
            >
              <Share2 size={17} />
            </button>
            <ThemeToggle />
          </div>
        </header>
        <ResizablePanelGroup
          orientation="horizontal"
          style={{ flex: 1, minHeight: 0 }}
        >
          <ResizablePanel
            id="main"
            minSize={narrow ? "100%" : "480px"}
            style={{ display: "flex", minWidth: 0 }}
          >
            {g && g.steps.length > 0 && !needsClarification(g) && (
              <GuideScrollProgress steps={g.steps} scrollRef={scroll} />
            )}
            <div className="main-chat-column">
              <div ref={scroll} className="main-chat-scroll">
                <div className="workspace-document">
                  {mutationError !== undefined && (
                    <ErrorBox error={mutationError} />
                  )}
                  <Messages
                    threadId={mainThreadId}
                    sources={g?.sources}
                    guideAnchorMessageId={g?.conversation_anchor_message_id}
                    activity={
                      <Research
                        workspace={w}
                        onReady={() => {
                          query.invalidateQueries({
                            queryKey: ["workspace", id],
                          });
                          query.invalidateQueries({
                            queryKey: ["guide", id],
                          });
                          query.invalidateQueries({
                            queryKey: ["workspaces"],
                          });
                        }}
                      />
                    }
                    guide={
                      <>
                        {g?.guide_is_stale && (
                          <div className="guide-notice">
                            Sources may have changed.{" "}
                          </div>
                        )}
                        {guide.isPending && w.guide_available ? (
                          <Loading label="Loading guide…" />
                        ) : guide.error ? (
                          <ErrorBox error={guide.error} />
                        ) : g && !g.clarification_message_id ? (
                          <GuideView
                            guide={g}
                            selectedStep={selectedId}
                            onDiscuss={(step) => openStep(step, true)}
                          />
                        ) : null}
                      </>
                    }
                  />
                </div>
              </div>
              <Composer
                threadId={mainThreadId}
                workspaceId={id}
                disabled={w.status === "researching"}
                clarificationWorkspaceId={needsContext ? id : undefined}
                placeholder={
                  needsContext
                    ? "Tell me what you want to build..."
                    : "Ask about your integration..."
                }
              />
            </div>
          </ResizablePanel>
          {panelOpen && discussion && !narrow && (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel
                id="discussion"
                className="step-discussion-panel"
                defaultSize="37%"
                minSize="320px"
                maxSize="55%"
              >
                {discussion}
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </div>
      {narrow && (
        <Sheet open={panelOpen && !!selected} onOpenChange={setPanelOpen}>
          <SheetContent
            side="right"
            className="w-[min(420px,100vw)] max-w-none gap-0 p-0 [&>button]:hidden"
          >
            <SheetTitle className="sr-only">Step discussion</SheetTitle>
            {discussion}
          </SheetContent>
        </Sheet>
      )}
      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Share this integration guide</DialogTitle>
            <DialogDescription>
              Anyone with this link can read the guide. Your conversations and
              private workspace stay private.
            </DialogDescription>
          </DialogHeader>
          <div
            style={{
              border: "1px solid var(--border)",
              padding: 11,
              borderRadius: 6,
              fontSize: 13,
              overflowWrap: "anywhere",
            }}
            className="mono"
          >
            {typeof window !== "undefined" ? window.location.origin : ""}
            /guides/{g?.share_slug}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              className="flex-1"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${window.location.origin}/guides/${g?.share_slug}`,
                  );
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                } catch {
                  setMutationError(
                    Error(
                      "Copy failed. Select and copy the link from the dialog.",
                    ),
                  );
                }
              }}
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}{" "}
              {copied ? "Copied" : "Copy link"}
            </Button>
            <a
              className="btn"
              href={`/guides/${g?.share_slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Open <ExternalLink size={12} />
            </a>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
function Research({
  workspace,
  onReady,
}: {
  workspace: WorkspaceType;
  onReady: () => void;
}) {
  const query = useQueryClient();
  const requested = useQuery({
    queryKey: ["research-request", workspace.id],
    queryFn: () => Promise.resolve(0),
    initialData: 0,
    staleTime: Infinity,
  });
  const [events, setEvents] = useState<{ name: string; detail: string }[]>([]);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [cancelled, setCancelled] = useState(
    workspace.status === "research_cancelled",
  );
  const [runId, setRunId] = useState<string>();
  const [elapsed, setElapsed] = useState(0);
  const [limit, setLimit] = useState(240);
  const startedAt = useRef(0);
  const subscription = useRef<AbortController | null>(null);
  const [retry, setRetry] = useState(0);
  const starts = useRef(
    new Map<
      string,
      Promise<{
        id: string;
        status: string;
        started_at?: string;
        timeout_seconds?: number;
      }>
    >(),
  );
  const ready = useRef(onReady);
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(
      () =>
        setElapsed(
          Math.max(0, Math.floor((Date.now() - startedAt.current) / 1000)),
        ),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [busy]);
  async function stopResearch() {
    if (!runId) return;
    try {
      const result = await api<{ status: string }>(
        `/research-runs/${runId}/cancel`,
        { method: "POST" },
      );
      if (result.status === "completed") ready.current();
      else if (result.status === "cancelled") {
        setCancelled(true);
        setError(undefined);
        setEvents([]);
      }
      setBusy(false);
      query.setQueryData(["research-request", workspace.id], 0);
      query.invalidateQueries({ queryKey: ["workspace", workspace.id] });
      query.invalidateQueries({ queryKey: ["workspaces"] });
      subscription.current?.abort();
    } catch (failure) {
      setError(failure);
    }
  }
  useEffect(() => {
    ready.current = onReady;
  }, [onReady]);
  useEffect(() => {
    const refresh = !!requested.data;
    const key = `${workspace.id}-${requested.data}-${retry}`;
    if (
      (workspace.guide_available && !refresh) ||
      (["research_cancelled", "awaiting_clarification"].includes(
        workspace.status,
      ) &&
        !refresh &&
        retry === 0)
    )
      return;
    const abort = new AbortController();
    subscription.current = abort;
    let mounted = true;
    async function run() {
      startedAt.current = Date.now();
      setElapsed(0);
      setCancelled(false);
      setRunId(undefined);
      setBusy(true);
      setError(undefined);
      setEvents([]);
      try {
        // Share the start request across React Strict Mode effect replays.
        // Cleanup disconnects this subscriber; the next setup reconnects to
        // the same persisted run instead of skipping its event stream.
        let pending = starts.current.get(key);
        if (!pending) {
          const existing = query.getQueryData<{
            id: string;
            status: string;
            started_at?: string;
            timeout_seconds?: number;
          }>(["clarification-run", workspace.id]);
          pending = existing
            ? Promise.resolve(existing)
            : api<{
                id: string;
                status: string;
                started_at?: string;
                timeout_seconds?: number;
              }>(`/workspaces/${workspace.id}/research`, {
                method: "POST",
                body: "{}",
              });
          starts.current.set(key, pending);
        }
        const run = await pending;
        if (!mounted) return;
        setRunId(run.id);
        setLimit(run.timeout_seconds || 240);
        if (run.started_at) {
          const timestamp = Date.parse(run.started_at);
          if (Number.isFinite(timestamp)) startedAt.current = timestamp;
        }
        setElapsed(
          Math.max(0, Math.floor((Date.now() - startedAt.current) / 1000)),
        );
        await stream(
          `/research-runs/${run.id}/events`,
          { method: "GET" },
          ({ event, data }) => {
            if (!mounted) return;
            setEvents((old) => [
              ...old,
              {
                name: event,
                detail: String(data.message || data.title || data.url || ""),
              },
            ]);
            if (event === "clarification_needed") {
              setBusy(false);
              setError(undefined);
              setEvents([]);
              query.removeQueries({
                queryKey: ["clarification-run", workspace.id],
              });
              query.setQueryData(["research-request", workspace.id], 0);
              query.invalidateQueries({ queryKey: ["messages"] });
              ready.current();
            }
            if (event === "guide_ready") {
              // Set terminal UI state before cache updates can clean up this
              // subscriber. Both seeded and researched guides then show only
              // the same assistant guide turn, without a stranded spinner.
              setBusy(false);
              setError(undefined);
              setEvents([]);
              query.removeQueries({
                queryKey: ["clarification-run", workspace.id],
              });
              ready.current();
              query.setQueryData(["research-request", workspace.id], 0);
            }
            if (event === "research_cancelled") {
              setBusy(false);
              setCancelled(true);
              setEvents([]);
            }
            if (event === "research_failed")
              throw Error(
                String(
                  data.error ||
                    data.message ||
                    "Research failed. Check backend configuration and retry.",
                ),
              );
          },
          abort.signal,
        );
      } catch (e) {
        if (mounted && !(e instanceof Error && e.name === "AbortError"))
          setError(e);
      } finally {
        if (mounted) setBusy(false);
      }
    }
    void run();
    return () => {
      mounted = false;
      abort.abort();
    };
  }, [
    workspace.id,
    workspace.status,
    workspace.guide_available,
    requested.data,
    retry,
    query,
  ]);
  if (!busy && !error && !events.length && !cancelled) return null;
  if (workspace.guide_available && !busy && !error) return null;
  const errorDetail =
    error instanceof Error ? error.message : error ? String(error) : "";
  const timedOut = /timed?\s*out|timeout|deadline/i.test(errorDetail);
  const accessDenied =
    /access was denied|permission|billing|api enablement|authenticated identity/i.test(
      errorDetail,
    );
  const sourceCount = events.filter(
    (item) => item.name === "source_found",
  ).length;
  const failureMessage = timedOut
    ? "The documentation search took longer than expected."
    : accessDenied
      ? "Research is temporarily unavailable."
      : "I couldn’t complete the documentation search.";

  return (
    <div className="research-reply" aria-live="polite">
      <div className="research-phase">
        {busy ? (
          <Loader2 className="spinner" size={15} />
        ) : error === undefined && !cancelled ? (
          <BookOpen size={15} />
        ) : null}
        <span>
          {cancelled
            ? "Research stopped."
            : error
              ? failureMessage
              : "I’m checking the provider’s documentation and setup requirements."}
        </span>
      </div>
      {busy && (
        <div className="research-timing">
          <span className="muted mono">
            {elapsed}s elapsed · {limit}s limit
          </span>
          <button
            className="icon-btn"
            aria-label="Stop research"
            title="Stop research"
            disabled={!runId}
            onClick={() => void stopResearch()}
          >
            <X size={13} /> Stop
          </button>
        </div>
      )}
      {busy && events.length > 0 && (
        <p className="muted research-current">
          {events[events.length - 1].detail ||
            titleCase(events[events.length - 1].name)}
        </p>
      )}
      {events.length > 0 && (busy || sourceCount > 0) && (
        <details className="research-details">
          <summary>
            Research activity · {sourceCount}{" "}
            {sourceCount === 1 ? "source" : "sources"}
          </summary>
          {events
            .filter((item) => item.name !== "research_failed")
            .map((item, index) => (
              <div key={index}>
                {titleCase(item.name)}
                {item.detail && ` · ${item.detail}`}
              </div>
            ))}
        </details>
      )}
      {(error !== undefined || cancelled) && (
        <>
          <p style={{ margin: "8px 0 0", maxWidth: 600 }}>
            {accessDenied
              ? "The research service couldn’t access its AI provider. Try again once access is restored."
              : "Your request is saved. Try again, or add any details you’d like me to use in the search."}
          </p>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              flexWrap: "wrap",
            }}
          >
            <button
              className="btn"
              style={{ fontSize: 12, padding: "5px 10px" }}
              onClick={() => setRetry((value) => value + 1)}
            >
              <RefreshCw size={12} /> Try again
            </button>
            {errorDetail && (
              <details
                className="research-details"
                style={{ margin: "10px 0 0" }}
              >
                <summary>Technical details</summary>
                <div>{errorDetail}</div>
              </details>
            )}
          </div>
        </>
      )}
    </div>
  );
}
