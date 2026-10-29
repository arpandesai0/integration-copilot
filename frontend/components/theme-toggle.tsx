"use client";
import { useSyncExternalStore } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    (listener) => {
      window.addEventListener("copilot-theme", listener);
      window.addEventListener("storage", listener);
      return () => {
        window.removeEventListener("copilot-theme", listener);
        window.removeEventListener("storage", listener);
      };
    },
    () => document.documentElement.dataset.theme || "dark",
    () => "dark",
  );
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    window.dispatchEvent(new Event("copilot-theme"));
    try {
      localStorage.setItem("copilot-theme", next);
    } catch {}
  };
  return (
    <button
      className="icon-btn"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      onClick={toggleTheme}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
