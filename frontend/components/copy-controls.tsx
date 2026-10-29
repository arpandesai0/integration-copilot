"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

export function CopyButton({
  value,
  label = "Copy",
  className = "",
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timeout.current) clearTimeout(timeout.current);
    },
    [],
  );

  async function copy() {
    if (timeout.current) clearTimeout(timeout.current);
    try {
      await navigator.clipboard.writeText(value);
      setStatus("copied");
      timeout.current = setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
    }
  }

  return (
    <span className="copy-control">
      <button
        type="button"
        className={`copy-button ${className}`}
        onClick={copy}
        aria-label={status === "copied" ? "Copied" : label}
        title={status === "copied" ? "Copied" : label}
      >
        {status === "copied" ? (
          <Check size={14} aria-hidden="true" />
        ) : (
          <Copy size={14} aria-hidden="true" />
        )}
      </button>
      <span
        role="status"
        aria-live="polite"
        className={status === "error" ? "copy-feedback" : "sr-only"}
      >
        {status === "error"
          ? "Couldn’t copy. Select and copy manually."
          : status === "copied"
            ? "Copied"
            : ""}
      </span>
    </span>
  );
}

export function CopyableLink({
  href,
  children,
  className = "",
  linkClassName = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
  linkClassName?: string;
}) {
  return (
    <span className={`copyable-link ${className}`}>
      <a href={href} target="_blank" rel="noreferrer" className={linkClassName}>
        {children}
      </a>
      <CopyButton value={href} label="Copy link" />
    </span>
  );
}
