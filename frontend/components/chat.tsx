"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Loader2 } from "lucide-react";
import { api, stream } from "@/lib/api";
import type { Message, Source } from "@/lib/types";
import { ResponseContent } from "./response-content";
import { ErrorBox } from "./common";

export function MessageBubble({
  message,
  sources = [],
}: {
  message: Message;
  sources?: Source[];
}) {
  const isUser = message.role === "user";
  return (
    <article
      className={`chat-message ${isUser ? "chat-message-user" : "chat-message-assistant"}`}
      aria-label={isUser ? "Your message" : "Integration Copilot response"}
    >
      <div className={isUser ? "chat-user-bubble" : "chat-agent-response"}>
        <div className="markdown">
          {message.content ? (
            <ResponseContent sources={isUser ? [] : sources}>
              {message.content}
            </ResponseContent>
          ) : message.status === "streaming" ? (
            <span className="muted" role="status">
              Thinking…
            </span>
          ) : null}
        </div>
        {!isUser && message.status === "incomplete" && (
          <p className="chat-message-status muted">Response interrupted</p>
        )}
      </div>
    </article>
  );
}

export function Messages({
  threadId,
  sources = [],
  emptyText,
  scrollToLatest = false,
  guide,
  guideAnchorMessageId,
  hiddenMessageId,
  activity,
}: {
  threadId?: string;
  sources?: Source[];
  emptyText?: string;
  scrollToLatest?: boolean;
  guide?: ReactNode;
  guideAnchorMessageId?: string | null;
  hiddenMessageId?: string | null;
  activity?: ReactNode;
}) {
  const end = useRef<HTMLDivElement>(null);
  const {
    data: messages = [],
    isPending,
    error,
  } = useQuery({
    queryKey: ["messages", threadId],
    queryFn: () => api<Message[]>(`/threads/${threadId}/messages`),
    enabled: !!threadId,
  });
  const hasGuide = guide !== undefined && guide !== null;
  const pinned = useRef(true);
  const previous = useRef<{ thread?: string; loaded: boolean; count: number }>({
    loaded: false,
    count: 0,
  });
  useEffect(() => {
    const marker = end.current;
    if (!marker) return;
    let viewport = marker.parentElement;
    while (
      viewport &&
      !/(auto|scroll)/.test(getComputedStyle(viewport).overflowY)
    )
      viewport = viewport.parentElement;
    if (!viewport) return;
    const container = viewport;
    const rememberPosition = () => {
      pinned.current =
        container.scrollHeight - container.scrollTop - container.clientHeight <
        80;
    };
    rememberPosition();
    container.addEventListener("scroll", rememberPosition, { passive: true });
    return () => container.removeEventListener("scroll", rememberPosition);
  }, [threadId, isPending, hasGuide]);
  useEffect(() => {
    if (!threadId || isPending) return;
    if (previous.current.thread !== threadId)
      previous.current = { thread: threadId, loaded: false, count: 0 };
    if (!previous.current.loaded) {
      previous.current = {
        thread: threadId,
        loaded: true,
        count: messages.length,
      };
      // A restored main conversation starts at its guide, even with saved follow-ups.
      if (scrollToLatest && !hasGuide)
        end.current?.scrollIntoView({ block: "nearest" });
      return;
    }
    const sentQuestion =
      messages.length > previous.current.count &&
      messages[messages.length - 1]?.role === "user";
    if ((scrollToLatest || hasGuide) && (sentQuestion || pinned.current)) {
      if (sentQuestion) pinned.current = true;
      end.current?.scrollIntoView({ block: "nearest" });
    }
    previous.current.count = messages.length;
  }, [messages, threadId, isPending, scrollToLatest, hasGuide]);
  if (error) return <ErrorBox error={error} />;
  if (isPending && threadId)
    return <p className="muted chat-empty">Loading conversation…</p>;
  if (emptyText && !messages.length && !guide)
    return <p className="muted chat-empty">{emptyText}</p>;
  const visibleMessages = messages.filter(
    (message) => message.id !== hiddenMessageId,
  );
  const anchorIndex = guideAnchorMessageId
    ? visibleMessages.findIndex(
        (message) => message.id === guideAnchorMessageId,
      )
    : -1;
  const firstUser = guide
    ? anchorIndex >= 0
      ? anchorIndex
      : visibleMessages.findIndex((message) => message.role === "user")
    : -1;
  const beforeGuide =
    firstUser >= 0 ? visibleMessages.slice(0, firstUser + 1) : [];
  const afterGuide =
    firstUser >= 0 ? visibleMessages.slice(firstUser + 1) : visibleMessages;
  return (
    <div className="chat-thread">
      {beforeGuide.map((message) => (
        <MessageBubble key={message.id} message={message} sources={sources} />
      ))}
      {guide && (
        <section
          className="chat-message chat-message-assistant chat-guide-turn"
          aria-label="Integration Copilot guide"
        >
          {guide}
        </section>
      )}
      {afterGuide.map((message) => (
        <MessageBubble key={message.id} message={message} sources={sources} />
      ))}
      {activity}
      <div ref={end} />
    </div>
  );
}

export function Composer({
  threadId,
  placeholder,
  autofocus = false,
  clarificationWorkspaceId,
  workspaceId,
  disabled = false,
}: {
  threadId?: string;
  placeholder: string;
  autofocus?: boolean;
  clarificationWorkspaceId?: string;
  workspaceId?: string;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const query = useQueryClient();
  const input = useRef<HTMLTextAreaElement>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    if (autofocus) input.current?.focus();
    return () => controller.current?.abort();
  }, [threadId, autofocus]);
  useEffect(() => {
    const field = input.current;
    if (!field) return;
    const resize = () => {
      field.style.height = "24px";
      // A wrapping placeholder must never expand an empty composer.
      if (!field.value) {
        field.style.overflowY = "hidden";
        return;
      }
      const contentHeight = field.scrollHeight;
      field.style.height = `${Math.min(120, Math.max(24, contentHeight))}px`;
      field.style.overflowY = contentHeight > 120 ? "auto" : "hidden";
    };
    resize();
    const container = field.parentElement;
    if (!container) return;
    let width = container.getBoundingClientRect().width;
    let frame = 0;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry || entry.contentRect.width === width) return;
      width = entry.contentRect.width;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(resize);
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [text]);

  async function send() {
    if (!text.trim() || busy || disabled || !threadId) return;
    const content = text.trim();
    setText("");
    setError(undefined);
    setBusy(true);
    const abort = new AbortController();
    controller.current = abort;
    let assistantId = "";
    let streamError: string | undefined;
    let streamCompleted = false;
    query.setQueryData<Message[]>(["messages", threadId], (saved = []) => [
      ...saved,
      {
        id: `pending-user-${Date.now()}`,
        role: "user",
        content,
        status: "completed",
      },
    ]);
    try {
      await stream(
        clarificationWorkspaceId
          ? `/chats/${clarificationWorkspaceId}/clarify`
          : `/threads/${threadId}/messages`,
        { method: "POST", body: JSON.stringify({ content }) },
        ({ event, data }) => {
          if (
            event === "research_started" &&
            (clarificationWorkspaceId || workspaceId)
          ) {
            const researchWorkspaceId = clarificationWorkspaceId || workspaceId;
            query.setQueryData(
              ["clarification-run", researchWorkspaceId],
              data,
            );
            query.setQueryData(
              ["research-request", researchWorkspaceId],
              Date.now(),
            );
            query.invalidateQueries({
              queryKey: ["workspace", researchWorkspaceId],
            });
          }
          if (event === "message_started") {
            assistantId = String(
              data.id || data.message_id || `stream-${Date.now()}`,
            );
            query.setQueryData<Message[]>(
              ["messages", threadId],
              (saved = []) =>
                saved.some((message) => message.id === assistantId)
                  ? saved
                  : [
                      ...saved,
                      {
                        id: assistantId,
                        role: "assistant",
                        content: "",
                        status: "streaming",
                      },
                    ],
            );
          }
          if (event === "message_delta") {
            const chunk = String(data.delta || data.text || data.content || "");
            query.setQueryData<Message[]>(
              ["messages", threadId],
              (saved = []) =>
                saved.map((message) =>
                  message.id === assistantId
                    ? { ...message, content: message.content + chunk }
                    : message,
                ),
            );
          }
          if (event === "citation") {
            query.setQueryData<Message[]>(
              ["messages", threadId],
              (saved = []) =>
                saved.map((message) =>
                  message.id === assistantId
                    ? {
                        ...message,
                        citations: [...(message.citations || []), data],
                      }
                    : message,
                ),
            );
          }
          if (event === "message_error")
            streamError = String(
              data.error ||
                data.message ||
                "The response could not be completed.",
            );
          if (event === "message_completed") {
            streamCompleted = true;
            query.setQueryData<Message[]>(
              ["messages", threadId],
              (saved = []) =>
                saved.map((message) =>
                  message.id === assistantId
                    ? { ...message, status: "completed" }
                    : message,
                ),
            );
          }
        },
        abort.signal,
      );
      if (streamError) throw Error(streamError);
      if (!streamCompleted)
        throw Error("The response was interrupted. Please try again.");
    } catch (failure) {
      if (assistantId && !streamCompleted) {
        query.setQueryData<Message[]>(["messages", threadId], (saved = []) =>
          saved.map((message) =>
            message.id === assistantId
              ? { ...message, status: "incomplete" }
              : message,
          ),
        );
      }
      if (!(failure instanceof Error && failure.name === "AbortError")) {
        setError(failure);
        if (!assistantId) setText(content);
      }
    } finally {
      setBusy(false);
      query.invalidateQueries({ queryKey: ["messages", threadId] });
      query.invalidateQueries({ queryKey: ["threads"] });
      if (clarificationWorkspaceId) {
        query.invalidateQueries({
          queryKey: ["workspace", clarificationWorkspaceId],
        });
        query.invalidateQueries({
          queryKey: ["guide", clarificationWorkspaceId],
        });
        query.invalidateQueries({ queryKey: ["workspaces"] });
      }
    }
  }

  return (
    <div className="chat-composer">
      {error !== undefined && (
        <div className="chat-composer-error">
          <ErrorBox error={error} />
        </div>
      )}
      <form
        className="chat-composer-form"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <textarea
          ref={input}
          className="chat-composer-input"
          aria-label={placeholder}
          placeholder={placeholder}
          rows={1}
          value={text}
          disabled={!threadId || busy || disabled}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.nativeEvent.isComposing &&
              !event.shiftKey
            ) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <button
          type="submit"
          className="chat-send"
          aria-label="Send message"
          title="Send message"
          disabled={!threadId || busy || disabled || !text.trim()}
        >
          {busy ? (
            <Loader2 size={17} className="spinner" />
          ) : (
            <ArrowUp size={18} />
          )}
        </button>
      </form>
    </div>
  );
}
