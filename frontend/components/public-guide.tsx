"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, LockKeyhole } from "lucide-react";
import { API_URL } from "@/lib/api";
import { ThemeToggle } from "./theme-toggle";
import type { Guide } from "@/lib/types";
import { GuideView } from "./guide";
import { BrandMark, ErrorBox, Loading, ProviderIcon } from "./common";
export function PublicGuide({ slug }: { slug: string }) {
  const guide = useQuery({
    queryKey: ["public-guide", slug],
    queryFn: async () => {
      const response = await fetch(`${API_URL}/api/v1/guides/${slug}`);
      if (response.status === 404) return null;
      if (!response.ok)
        throw new Error("Could not load this shared guide. Please try again.");
      return response.json() as Promise<Guide>;
    },
    retry: 0,
  });
  return (
    <div style={{ minHeight: "100dvh", background: "var(--panel)" }}>
      <header
        className="workspace-topbar"
        style={{
          height: 64,
          borderBottom: "1px solid var(--border)",
          padding: "0 30px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Link
          href="/"
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          <BrandMark size={27} />
          Integration Copilot
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="badge">
            <LockKeyhole size={10} />
            Read-only guide
          </span>
          <ThemeToggle />
        </div>
      </header>
      <main style={{ maxWidth: 920, margin: "0 auto", padding: "44px 35px" }}>
        {guide.isPending ? (
          <Loading />
        ) : guide.error ? (
          <ErrorBox error={guide.error} />
        ) : !guide.data ? (
          <section>
            <h1>This shared guide is unavailable</h1>
            <p className="muted">
              The link may be incorrect, or its original chat may have been
              deleted. Open the chat and use Share guide to get its current
              link.
            </p>
            <Link className="btn" href="/">
              Back to integrations
            </Link>
          </section>
        ) : (
          <>
            <div
              style={{
                display: "flex",
                gap: 9,
                alignItems: "center",
                marginBottom: 25,
              }}
            >
              <ProviderIcon provider={guide.data.provider} />
              <span style={{ fontSize: 13 }}>
                {guide.data.provider.name} integration guide
              </span>
            </div>
            <GuideView guide={guide.data} readOnly />
            <Link className="btn primary" href="/">
              Create your own integration <ArrowUpRight size={12} />
            </Link>
          </>
        )}
      </main>
    </div>
  );
}
