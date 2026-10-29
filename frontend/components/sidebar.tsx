"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ChevronLeft,
  PanelLeft,
  Plus,
  Search,
  FolderOpen,
  Trash2,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Thread, Workspace } from "@/lib/types";
import { BrandMark, ErrorBox, ProviderIcon } from "./common";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "./ui/dialog";

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const query = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<Workspace | null>(null);
  const deleteChat = useMutation({
    mutationFn: (target: Workspace) =>
      api(`/chats/${target.id}`, { method: "DELETE" }),
    onSuccess: async (_, target) => {
      const savedThreads =
        query.getQueryData<Thread[]>(["threads", target.id]) || [];
      const keys = [
        ...["workspace", "guide", "threads", "research-request"].map((key) => [
          key,
          target.id,
        ]),
        ...savedThreads.map((thread) => ["messages", thread.id]),
      ];
      await Promise.all(
        keys.map((queryKey) => query.cancelQueries({ queryKey })),
      );
      if (pathname === `/chats/${target.id}`) router.replace("/");
      keys.forEach((queryKey) => query.removeQueries({ queryKey }));
      query.setQueryData<Workspace[]>(["workspaces"], (saved = []) =>
        saved.filter((item) => item.id !== target.id),
      );
      query.invalidateQueries({ queryKey: ["workspaces"] });
      setDeleteTarget(null);
    },
  });
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api<Workspace[]>("/chats"),
  });
  const filtered = workspaces.filter((w) =>
    (w.title + " " + w.provider.name)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <aside className={`app-sidebar${collapsed ? " is-collapsed" : ""}`}>
      <div className="sidebar-brand">
        <Link
          href="/"
          aria-label="Integration Copilot home"
          className="brand-lockup"
        >
          <BrandMark />
          {!collapsed && (
            <span>
              Integration <strong>Copilot</strong>
            </span>
          )}
        </Link>
        {!collapsed && (
          <button
            className="icon-btn"
            aria-label="Collapse sidebar"
            onClick={() => setCollapsed(true)}
          >
            <ChevronLeft size={15} />
          </button>
        )}
      </div>
      {collapsed ? (
        <nav className="sidebar-collapsed-nav">
          <button
            className="icon-btn"
            aria-label="Expand sidebar"
            onClick={() => setCollapsed(false)}
          >
            <PanelLeft size={19} />
          </button>
          <Link className="icon-btn" href="/" aria-label="New integration">
            <Plus size={19} />
          </Link>
        </nav>
      ) : (
        <>
          <div className="sidebar-actions" style={{ paddingTop: 16 }}>
            <Link className="btn sidebar-new" href="/">
              <Plus size={15} />
              New integration<kbd>⌘ K</kbd>
            </Link>
            <div className="sidebar-search">
              <Search size={14} />
              <input
                aria-label="Search saved integrations"
                placeholder="Search integrations"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <nav className="sidebar-scroll" aria-label="Integration navigation">
            <div className="sidebar-section-title">
              <span>Your integrations</span>
              <span>{workspaces.length.toString().padStart(2, "0")}</span>
            </div>
            {filtered.map((w) => (
              <div
                key={w.id}
                className={`integration-nav-item${pathname === `/chats/${w.id}` ? " is-active" : ""}`}
              >
                <Link
                  href={`/chats/${w.id}`}
                  className="integration-nav-link"
                >
                  <ProviderIcon provider={w.provider} size={27} />
                  <span className="integration-nav-copy">
                    <strong>{w.provider.name}</strong>
                    <small>
                      {w.status === "ready"
                        ? "Setup guide"
                        : w.status === "awaiting_clarification"
                          ? "Needs a few details"
                          : w.status === "research_failed"
                            ? "Research needs attention"
                            : "Researching integration"}
                    </small>
                  </span>
                </Link>
                <button
                  className="icon-btn sidebar-delete-chat"
                  aria-label={`Delete ${w.provider.name} chat`}
                  title="Delete chat"
                  onClick={() => {
                    deleteChat.reset();
                    setDeleteTarget(w);
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {!filtered.length && (
              <div className="sidebar-empty">
                <FolderOpen size={19} />
                <p>
                  {search
                    ? "No matching integrations"
                    : "Your integrations will appear here."}
                </p>
              </div>
            )}
          </nav>
        </>
      )}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open && !deleteChat.isPending) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Delete {deleteTarget?.provider.name} chat?
            </DialogTitle>
            <DialogDescription>
              This removes the integration, its messages, and step chats. Its
              shared guide link will stop working. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deleteChat.error && <ErrorBox error={deleteChat.error} />}
          <DialogFooter>
            <button
              className="btn"
              disabled={deleteChat.isPending}
              onClick={() => setDeleteTarget(null)}
            >
              Cancel
            </button>
            <button
              className="btn destructive"
              disabled={deleteChat.isPending}
              onClick={() => deleteTarget && deleteChat.mutate(deleteTarget)}
            >
              {deleteChat.isPending && (
                <Loader2 className="spinner" size={13} />
              )}
              {deleteChat.isPending ? "Deleting…" : "Delete chat"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
