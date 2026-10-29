"use client";

import { Children, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { resolveSourceHref, sourceHref } from "@/lib/source-links";
import { CopyButton, CopyableLink } from "./copy-controls";
import { InlineCitation } from "./inline-citations";
export { CopyButton, CopyableLink } from "./copy-controls";
import type { Source } from "@/lib/types";

type MarkdownNode = {
  type: string;
  value?: string;
  url?: string;
  children?: MarkdownNode[];
};

const groundingMarkdownLink =
  /\[([^\]\n]+)\]\((https:\/\/vertexaisearch\.cloud\.google\.com\/[^\s)]+)\)/g;
const groundingUrl =
  /https:\/\/vertexaisearch\.cloud\.google\.com\/[^\s)\]}>\"]+/g;
const isGroundingUrl = (value: string) =>
  value.startsWith("https://vertexaisearch.cloud.google.com/");

function safeResponseMarkdown(value: string, sources: Source[]): string {
  const replacements = new Map<string, string>();
  sources.forEach((source) => {
    if (!isGroundingUrl(source.url)) return;
    const resolved = sourceHref(source);
    if (!isGroundingUrl(resolved)) replacements.set(source.url, resolved);
  });
  const withSafeLinks = value.replace(
    groundingMarkdownLink,
    (_, label: string, href: string) => {
      const resolved = replacements.get(href);
      return resolved
        ? `[${label}](${resolved})`
        : `${label} (source unavailable)`;
    },
  );
  return withSafeLinks.replace(
    groundingUrl,
    (href) => replacements.get(href) || "Source unavailable",
  );
}

// Verified official console entry points; existing links and code stay intact.
function remarkDestinationLinks() {
  return (tree: unknown) => {
    function visit(node: MarkdownNode) {
      if (
        !node.children ||
        ["link", "linkReference", "code", "inlineCode"].includes(node.type)
      )
        return;
      node.children = node.children.flatMap((child): MarkdownNode[] => {
        if (child.type !== "text" || !child.value) {
          visit(child);
          return [child];
        }
        const result: MarkdownNode[] = [];
        const names = /\b(?:Microsoft\s+)?Azure\s+(?:Government\s+)?Portal\b/gi;
        let offset = 0;
        for (const match of child.value.matchAll(names)) {
          const index = match.index!;
          if (index > offset)
            result.push({
              type: "text",
              value: child.value.slice(offset, index),
            });
          result.push({
            type: "link",
            url: /government/i.test(match[0])
              ? "https://portal.azure.us/"
              : "https://portal.azure.com/",
            children: [{ type: "text", value: match[0] }],
          });
          offset = index + match[0].length;
        }
        if (!offset) return [child];
        if (offset < child.value.length)
          result.push({ type: "text", value: child.value.slice(offset) });
        return result;
      });
    }
    visit(tree as MarkdownNode);
  };
}

// Work on parsed text only: existing code, links, and contractions stay intact.
function remarkTechnicalValues() {
  return (tree: unknown) => {
    function visit(node: MarkdownNode) {
      if (
        !node.children ||
        ["link", "linkReference", "code", "inlineCode"].includes(node.type)
      )
        return;
      // GFM parses bare URLs before this transform. Remove only a matching pair
      // of quotes immediately surrounding an autolink, leaving prose untouched.
      node.children.forEach((child, index, siblings) => {
        const before = siblings[index - 1];
        const after = siblings[index + 1];
        if (
          child.type !== "link" ||
          !/^https?:\/\//.test(child.url || "") ||
          child.children?.length !== 1 ||
          child.children[0].value !== child.url ||
          before?.type !== "text" ||
          after?.type !== "text"
        )
          return;
        const quote = before.value?.slice(-1);
        if (
          (quote === "'" || quote === '"') &&
          after.value?.startsWith(quote) &&
          !/\w/.test(before.value?.slice(-2, -1) || "") &&
          !/\w/.test(after.value.slice(1, 2))
        ) {
          before.value = before.value?.slice(0, -1);
          after.value = after.value.slice(1);
        }
      });
      node.children = node.children.flatMap((child) => {
        if (child.type !== "text" || !child.value) {
          visit(child);
          return [child];
        }
        const text = child.value;
        const result: MarkdownNode[] = [];
        const quoted = /(["'])([^\n"']+)\1/g;
        let offset = 0;
        let match: RegExpExecArray | null;
        while ((match = quoted.exec(text)) !== null) {
          const index = match.index;
          const value = match[2];
          // Quote boundaries avoid interpreting apostrophes inside ordinary words.
          if (
            (index > 0 && /\w/.test(text[index - 1])) ||
            /\w/.test(text[index + match[0].length] || "")
          ) {
            quoted.lastIndex = index + 1;
            continue;
          }
          const url = /^https?:\/\/\S+$/.test(value);
          const machine =
            /^[A-Z][A-Z0-9_-]*$/.test(value) ||
            (/^[\w.:/={}<>@+ -]+$/.test(value) &&
              /[_:=/{}<>@]|\w\.\w/.test(value));
          if (!url && !machine) {
            // A rejected prose pair may end at the next value's opening quote.
            quoted.lastIndex = index + 1;
            continue;
          }
          if (index > offset)
            result.push({ type: "text", value: text.slice(offset, index) });
          result.push(
            url
              ? {
                  type: "link",
                  url: value,
                  children: [{ type: "text", value }],
                }
              : { type: "inlineCode", value },
          );
          offset = index + match[0].length;
        }
        if (!offset) return [child];
        if (offset < text.length)
          result.push({ type: "text", value: text.slice(offset) });
        return result;
      });
    }
    visit(tree as MarkdownNode);
  };
}

function plainText(children: ReactNode): string {
  return Children.toArray(children)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number")
        return String(child);
      if (isValidElement<{ children?: ReactNode }>(child))
        return plainText(child.props.children);
      return "";
    })
    .join("");
}

export function ResponseContent({
  children,
  sources = [],
  className = "",
  technical = false,
  trailing,
}: {
  children: string;
  sources?: Source[];
  className?: string;
  technical?: boolean;
  trailing?: ReactNode;
}) {
  const safeChildren = safeResponseMarkdown(children, sources);
  return (
    <div
      className={`markdown response-content ${trailing ? "has-inline-citations" : ""} ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={
          technical
            ? [remarkGfm, remarkTechnicalValues, remarkDestinationLinks]
            : [remarkGfm, remarkDestinationLinks]
        }
        components={{
          a: ({ href, children }) => {
            const original = href || "";
            const index = sources.findIndex(
              (source) =>
                source.url === original ||
                source.text_fragment_url === original ||
                Object.values(source.step_text_fragment_urls || {}).includes(
                  original,
                ),
            );
            return index >= 0 ? (
              <InlineCitation source={sources[index]} number={index + 1} />
            ) : (
              <CopyableLink href={resolveSourceHref(original, sources)}>
                {children}
              </CopyableLink>
            );
          },
          code: ({ children, className }) => {
            const value = plainText(children);
            return /^https?:\/\/\S+$/.test(value) ? (
              <CopyableLink href={resolveSourceHref(value, sources)}>
                <code className="response-inline-code">{children}</code>
              </CopyableLink>
            ) : (
              <code className={`response-inline-code ${className || ""}`}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => {
            const code = Children.toArray(children).find((child) =>
              isValidElement(child),
            );
            const props = isValidElement<{
              children?: ReactNode;
              className?: string;
            }>(code)
              ? code.props
              : undefined;
            const value = plainText(props?.children ?? children);
            const language = /language-([^\s]+)/.exec(
              props?.className || "",
            )?.[1];
            return (
              <div className="response-code-block">
                <div className="response-code-header">
                  <span>{language || "Code"}</span>
                  <CopyButton value={value} label="Copy code" />
                </div>
                <pre>
                  <code className={props?.className}>{value}</code>
                </pre>
              </div>
            );
          },
        }}
      >
        {safeChildren}
      </ReactMarkdown>
      {trailing}
    </div>
  );
}
