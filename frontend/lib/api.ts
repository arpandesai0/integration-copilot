import type { StreamEvent } from "./types";
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEVICE_ID_KEY = "integration-copilot-device-id";

function deviceId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  let id = window.localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = window.crypto.randomUUID();
    window.localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

function requestHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  result.set("Content-Type", "application/json");
  const id = deviceId();
  if (id) result.set("X-Device-ID", id);
  return result;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    credentials: "include",
    headers: requestHeaders(options.headers),
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail || data);
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
export async function stream(
  path: string,
  options: RequestInit,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
) {
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    credentials: "include",
    headers: requestHeaders(options.headers),
    signal,
  });
  if (!r.ok) {
    let error = `Request failed (${r.status})`;
    try {
      const data = await r.json();
      error = data.detail || error;
    } catch {}
    throw Error(error);
  }
  if (!r.body) throw Error("This response did not contain a stream.");
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (block: string) => {
    let event = "message";
    const lines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) lines.push(line.slice(5).trimStart());
    }
    if (!lines.length) return;
    try {
      onEvent({ event, data: JSON.parse(lines.join("\n")) });
    } catch (e) {
      if (e instanceof SyntaxError) return;
      throw e;
    }
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        dispatch(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
      }
      if (done) {
        if (buffer.trim()) dispatch(buffer);
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
