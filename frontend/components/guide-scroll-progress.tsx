"use client";

import { useEffect, useState, type RefObject } from "react";
import type { Step } from "@/lib/types";

export function GuideScrollProgress({
  steps,
  scrollRef,
}: {
  steps: Step[];
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  const [position, setPosition] = useState({
    active: -1,
    percent: 0,
    completed: false,
  });

  useEffect(() => {
    const viewport = scrollRef.current;
    if (!viewport || !steps.length) return;
    let frame = 0;
    const measure = () => {
      const sections = steps.map((step) =>
        document.getElementById(`step-${step.id}`),
      );
      const first = sections[0];
      const last = sections[sections.length - 1];
      if (!first || !last) return;
      const viewportBounds = viewport.getBoundingClientRect();
      const anchor = viewportBounds.top + 32;
      const firstTop = first.getBoundingClientRect().top;
      const lastTop = last.getBoundingClientRect().top;
      const lastBottom = last.getBoundingClientRect().bottom;
      const atScrollEnd =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight <= 2;
      const completed =
        viewport.scrollTop > 0 &&
        (lastBottom <= viewportBounds.bottom - 32 || atScrollEnd);
      let active = -1;
      sections.forEach((section, index) => {
        if (section && section.getBoundingClientRect().top <= anchor)
          active = index;
      });
      const percent = completed
        ? 100
        : steps.length === 1
          ? active === 0
            ? 100
            : 0
          : Math.min(
              100,
              Math.max(0, ((anchor - firstTop) / (lastTop - firstTop)) * 100),
            );
      setPosition((previous) =>
        previous.active === active &&
        previous.completed === completed &&
        Math.abs(previous.percent - percent) < 0.1
          ? previous
          : { active, percent, completed },
      );
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    viewport.addEventListener("scroll", schedule, { passive: true });
    const resize = new ResizeObserver(schedule);
    resize.observe(viewport);
    if (viewport.firstElementChild) resize.observe(viewport.firstElementChild);
    schedule();
    return () => {
      viewport.removeEventListener("scroll", schedule);
      resize.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [steps, scrollRef]);

  if (!steps.length) return null;
  return (
    <nav className="guide-scroll-progress" aria-label="Guide scroll navigation">
      <div className="guide-scroll-caption">
        <span className="label">Setup</span>
        <span className="mono muted">
          {position.completed
            ? "Completed"
            : position.active < 0
              ? `${steps.length} steps`
              : `Step ${position.active + 1} of ${steps.length}`}
        </span>
      </div>
      <div className="guide-scroll-track">
        <div
          className="guide-scroll-line"
          role="progressbar"
          aria-label="Guide reading progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(position.percent)}
          aria-valuetext={
            position.completed
              ? "Guide completed"
              : position.active < 0
                ? "Guide overview"
                : `Step ${position.active + 1} of ${steps.length}`
          }
        >
          <span style={{ height: `${position.percent}%` }} />
        </div>
        {steps.map((step, index) => (
          <button
            key={step.id}
            className={`guide-scroll-stop${position.completed || index <= position.active ? " is-reached" : ""}`}
            aria-label={`Jump to step ${index + 1}: ${step.title}`}
            aria-current={
              !position.completed && index === position.active
                ? "step"
                : undefined
            }
            title={step.title}
            onClick={() =>
              document
                .getElementById(`step-${step.id}`)
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            <span className="guide-scroll-dot" />
            <span className="mono">{String(index + 1).padStart(2, "0")}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
