/**
 * Real-time SSE (Server-Sent Events) Client
 * Uses fetch with ReadableStream to support Bearer token authentication,
 * automatic exponential backoff reconnection, and typed event dispatching.
 */

import { getAccessToken, isBrowser } from "./auth";
import type { SSEPayloadMap } from "./types";

export type SSEConnectionState = "connected" | "connecting" | "disconnected" | "error";

type EventListener<K extends keyof SSEPayloadMap> = (data: SSEPayloadMap[K]) => void;
type AnyEventListener = (event: string, data: any) => void;

class SSEClient {
  private abortController: AbortController | null = null;
  private retryTimeout: any = null;
  private retryDelayMs = 1000;
  private maxRetryDelayMs = 15000;
  private listeners: Map<string, Set<EventListener<any>>> = new Map();
  private wildcardListeners: Set<AnyEventListener> = new Set();
  private state: SSEConnectionState = "disconnected";
  private stateListeners: Set<(state: SSEConnectionState) => void> = new Set();
  private isExplicitlyClosed = false;

  public getState(): SSEConnectionState {
    return this.state;
  }

  private setState(newState: SSEConnectionState) {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((fn) => fn(newState));
    }
  }

  public onStateChange(listener: (state: SSEConnectionState) => void): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  public connect(): void {
    if (!isBrowser()) return;
    this.isExplicitlyClosed = false;

    if (this.state === "connected" || this.state === "connecting") {
      return;
    }

    this.startStreaming();
  }

  private async startStreaming(): Promise<void> {
    const token = getAccessToken();
    if (!token) {
      this.setState("disconnected");
      return;
    }

    this.setState("connecting");
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    const envUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const isRemote =
      typeof window !== "undefined" &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1";
    const baseUrl =
      isRemote && (envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))
        ? ""
        : envUrl;
    const url = `${baseUrl}/api/live/events?token=${encodeURIComponent(token)}`;

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "text/event-stream",
          "Cache-Control": "no-cache",
        },
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`SSE HTTP error: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body in SSE stream");
      }

      this.setState("connected");
      this.retryDelayMs = 1000; // Reset backoff on successful connection

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          this.parseBlock(block);
        }
      }

      // Stream completed normally, reconnect
      if (!this.isExplicitlyClosed) {
        this.scheduleReconnect();
      }
    } catch (err: any) {
      if (err.name === "AbortError" || this.isExplicitlyClosed) {
        this.setState("disconnected");
        return;
      }
      this.setState("error");
      this.scheduleReconnect();
    }
  }

  private parseBlock(block: string) {
    if (!block.trim()) return;
    const lines = block.split("\n");
    let eventName = "message";
    let dataStr = "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.substring(6).trim();
      } else if (line.startsWith("data:")) {
        dataStr = line.substring(5).trim();
      }
    }

    if (!dataStr) return;

    try {
      const parsedData = JSON.parse(dataStr);
      this.dispatchEvent(eventName, parsedData);
    } catch {
      // In case data is a plain string
      this.dispatchEvent(eventName, dataStr);
    }
  }

  private dispatchEvent(eventName: string, data: any) {
    // Specific listeners
    const handlers = this.listeners.get(eventName);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (e) {
          console.error(`Error in SSE listener for [${eventName}]:`, e);
        }
      });
    }

    // Wildcard listeners
    this.wildcardListeners.forEach((handler) => {
      try {
        handler(eventName, data);
      } catch (e) {
        console.error("Error in wildcard SSE listener:", e);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.isExplicitlyClosed) return;

    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
    }

    this.setState("connecting");
    this.retryTimeout = setTimeout(() => {
      this.retryDelayMs = Math.min(this.retryDelayMs * 2, this.maxRetryDelayMs);
      this.startStreaming();
    }, this.retryDelayMs);
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.setState("disconnected");
  }

  public on<K extends keyof SSEPayloadMap>(
    event: K,
    listener: EventListener<K>
  ): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(listener);

    return () => {
      this.listeners.get(event)?.delete(listener);
    };
  }

  public onAny(listener: AnyEventListener): () => void {
    this.wildcardListeners.add(listener);
    return () => {
      this.wildcardListeners.delete(listener);
    };
  }
}

export const sseClient = new SSEClient();
