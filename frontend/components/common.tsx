"use client";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { Provider } from "@/lib/types";
export function BrandMark({ size = 27 }: { size?: number }) {
  return (
    <span
      className="brand-mark"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path
          d="M9 5H5v14h4M15 5h4v14h-4M9 12h6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="square"
        />
      </svg>
    </span>
  );
}
function providerIconUrl(provider?: Provider): string | undefined {
  const name = provider?.name.trim().toLowerCase();
  // Keep recognizable product icons local and available without network calls.
  if (name === "jira" || name === "atlassian jira")
    return "/providers/jira.ico";
  if (name === "xbox" || name === "microsoft xbox")
    return "/providers/xbox.ico";
  if (!provider?.official_domain) return undefined;
  try {
    const url = new URL(
      provider.official_domain.includes("://")
        ? provider.official_domain
        : `https://${provider.official_domain}`,
    );
    // Never load provisional user input, IP addresses or local-network names.
    if (
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      url.port ||
      !/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(
        url.hostname,
      ) ||
      /(?:^|\.)(?:localhost|local|internal|test|invalid|example|onion)$/i.test(
        url.hostname,
      )
    )
      return undefined;
    return `https://${url.hostname}/favicon.ico`;
  } catch {
    return undefined;
  }
}

export function ProviderIcon({
  provider,
  size = 30,
}: {
  provider?: Provider;
  size?: number;
}) {
  const slug = provider?.slug || "";
  const brand = provider?.name.trim().toLowerCase() || "";
  const iconUrl = providerIconUrl(provider);
  const [failedUrl, setFailedUrl] = useState<string>();
  const hasIcon = iconUrl && failedUrl !== iconUrl;
  return (
    <span
      className={`provider-icon provider-${slug}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {brand === "discord" ? (
        <svg
          viewBox="0 0 24 24"
          width={size * 0.72}
          height={size * 0.72}
          fill="#5865F2"
        >
          <path d="M20.32 4.37a19.8 19.8 0 0 0-4.89-1.52 13.8 13.8 0 0 0-.62 1.28 18.3 18.3 0 0 0-5.62 0 13 13 0 0 0-.63-1.28 19.7 19.7 0 0 0-4.89 1.52C.58 9.05-.38 13.62.05 18.12a19.9 19.9 0 0 0 5.99 3.03 14.6 14.6 0 0 0 1.28-2.1 12.9 12.9 0 0 1-2.02-.97l.5-.39c3.9 1.8 8.13 1.8 11.98 0l.51.39c-.65.39-1.33.71-2.03.97.37.73.8 1.43 1.28 2.1a19.8 19.8 0 0 0 6-3.03c.5-5.22-.84-9.75-3.22-13.75ZM8.02 15.35c-1.17 0-2.13-1.08-2.13-2.41s.94-2.42 2.13-2.42 2.15 1.09 2.13 2.42c0 1.33-.94 2.41-2.13 2.41Zm7.96 0c-1.17 0-2.13-1.08-2.13-2.41s.94-2.42 2.13-2.42 2.15 1.09 2.13 2.42c0 1.33-.94 2.41-2.13 2.41Z" />
        </svg>
      ) : brand === "linkedin" ? (
        <svg
          viewBox="0 0 24 24"
          width={size * 0.68}
          height={size * 0.68}
          fill="#0A66C2"
        >
          <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12Zm1.78 13.02H3.56V9h3.56v11.45Z" />
        </svg>
      ) : brand === "spotify" ? (
        <svg
          viewBox="0 0 24 24"
          width={size * 0.72}
          height={size * 0.72}
          fill="#1ED760"
        >
          <path d="M12 0a12 12 0 1 0 0 24 12 12 0 0 0 0-24Zm5.5 17.3a.75.75 0 0 1-1.03.25c-2.83-1.73-6.39-2.12-10.58-1.16a.75.75 0 1 1-.33-1.46c4.58-1.05 8.52-.6 11.7 1.34.35.22.46.68.24 1.03Zm1.47-3.27a.94.94 0 0 1-1.29.31c-3.24-1.99-8.18-2.56-12.01-1.4a.94.94 0 1 1-.55-1.8c4.38-1.33 9.82-.69 13.54 1.6.44.27.58.85.31 1.29Zm.13-3.41C15.21 8.31 8.79 8.1 5.08 9.2a1.13 1.13 0 1 1-.64-2.16c4.26-1.26 11.36-1.01 15.82 1.64a1.13 1.13 0 0 1-1.16 1.94Z" />
        </svg>
      ) : slug === "github" ? (
        <svg
          viewBox="0 0 24 24"
          width={size * 0.68}
          height={size * 0.68}
          fill="currentColor"
        >
          <path d="M12 .75a11.25 11.25 0 0 0-3.56 21.92c.56.1.77-.24.77-.54v-2.1c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.68.08-.68 1.13.08 1.72 1.16 1.72 1.16 1 1.72 2.63 1.22 3.27.93.1-.73.39-1.22.71-1.5-2.5-.28-5.13-1.25-5.13-5.56 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.99 0 0 .95-.3 3.1 1.16A10.8 10.8 0 0 1 12 6.16c.96 0 1.92.13 2.82.38 2.15-1.46 3.1-1.16 3.1-1.16.61 1.56.23 2.71.11 2.99.72.79 1.16 1.8 1.16 3.03 0 4.32-2.64 5.28-5.15 5.56.4.35.76 1.04.76 2.1v3.07c0 .3.21.65.77.54A11.25 11.25 0 0 0 12 .75Z" />
        </svg>
      ) : slug === "slack" ? (
        <svg viewBox="0 0 24 24" width={size * 0.72} height={size * 0.72}>
          <g fill="#36C5F0">
            <rect x="2" y="9" width="8" height="4" rx="2" />
            <path d="M8 2a2 2 0 0 1 2 2v4H8a2 2 0 0 1 0-4Z" />
          </g>
          <g fill="#2EB67D">
            <rect x="11" y="2" width="4" height="8" rx="2" />
            <path d="M22 8a2 2 0 0 1-2 2h-4V8a2 2 0 0 1 4 0Z" />
          </g>
          <g fill="#ECB22E">
            <rect x="14" y="11" width="8" height="4" rx="2" />
            <path d="M16 22a2 2 0 0 1-2-2v-4h2a2 2 0 0 1 0 4Z" />
          </g>
          <g fill="#E01E5A">
            <rect x="9" y="14" width="4" height="8" rx="2" />
            <path d="M2 16a2 2 0 0 1 2-2h4v2a2 2 0 0 1-4 0Z" />
          </g>
        </svg>
      ) : slug === "google-drive" ? (
        <svg viewBox="0 0 24 24" width={size * 0.75} height={size * 0.75}>
          <path fill="#2684FC" d="m8 15-4 7h16l4-7Z" />
          <path fill="#00AC47" d="M8 1 0 15l4 7L16 1Z" />
          <path fill="#FFBA00" d="M16 1H8l12 21 4-7Z" />
          <path fill="#0066DA" d="m8 15-4 7-4-7Z" />
          <path fill="#00832D" d="M8 1h8l-4 7Z" />
          <path fill="#EA4335" d="m16 15 4 7 4-7Z" />
        </svg>
      ) : hasIcon ? (
        // Native images allow official-domain favicons without a server proxy.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={iconUrl}
          alt=""
          width={Math.round(size * 0.76)}
          height={Math.round(size * 0.76)}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailedUrl(iconUrl)}
          style={{ objectFit: "contain", borderRadius: 2 }}
        />
      ) : (
        <span style={{ fontSize: size * 0.43, fontWeight: 600 }}>
          {provider?.name?.slice(0, 1) || "+"}
        </span>
      )}
    </span>
  );
}
export const titleCase = (text?: string) =>
  text
    ? text.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase())
    : "Unknown";
export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div
      style={{
        padding: 36,
        display: "flex",
        gap: 9,
        alignItems: "center",
        color: "var(--muted)",
      }}
    >
      <Loader2 size={16} className="spinner" />
      {label}
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div role="alert" className="error">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}
