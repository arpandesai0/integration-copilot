import type { Source } from "./types";

export function sourceHref(
  source: Pick<Source, "url" | "text_fragment_url" | "step_text_fragment_urls">,
  stepKey?: string,
): string {
  if (stepKey) return source.step_text_fragment_urls?.[stepKey] || source.url;
  return source.text_fragment_url || source.url;
}

export function resolveSourceHref(
  href: string,
  sources: Source[] = [],
): string {
  const source = sources.find(
    (candidate) =>
      candidate.url === href || candidate.text_fragment_url === href,
  );
  return source ? sourceHref(source) : href;
}
