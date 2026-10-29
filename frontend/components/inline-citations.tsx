"use client";
import type { Source } from "@/lib/types";
import { sourceHref } from "@/lib/source-links";

export function InlineCitation({
  source,
  number,
  stepKey,
  label = "Source",
}: {
  source: Source;
  number: number;
  stepKey?: string;
  label?: string;
}) {
  const href = sourceHref(source, stepKey);
  const description = [
    label,
    source.title,
    source.excerpt,
    source.retrieved_at
      ? `Checked ${new Date(source.retrieved_at).toLocaleDateString()}`
      : null,
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <span className="inline-citation">
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        title={description}
        aria-label={`${label} ${number}: ${source.title}`}
      >
        [{number}]
      </a>
    </span>
  );
}

export function InlineCitations({
  sourceIds,
  sources,
  stepKey,
  label,
}: {
  sourceIds: string[];
  sources: Source[];
  stepKey?: string;
  label?: string;
}) {
  const ids = [...new Set(sourceIds)].filter((id) =>
    sources.some((source) => source.id === id),
  );
  if (!ids.length) return null;
  return (
    <span className="inline-citations">
      {ids.map((id) => {
        const index = sources.findIndex((source) => source.id === id);
        return (
          <InlineCitation
            key={id}
            source={sources[index]}
            number={index + 1}
            stepKey={stepKey}
            label={label}
          />
        );
      })}
    </span>
  );
}
