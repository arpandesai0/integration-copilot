"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    try {
      document.documentElement.dataset.theme =
        localStorage.getItem("copilot-theme") || "dark";
      window.dispatchEvent(new Event("copilot-theme"));
    } catch {}
  }, []);
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 10000 } },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
