"use client";

import * as React from "react";
import { sseClient, type SSEConnectionState } from "@/lib/sse";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/components/ui/toast";
import type { SSEPayloadMap } from "@/lib/types";

interface SSEContextValue {
  connectionState: SSEConnectionState;
  subscribe: <K extends keyof SSEPayloadMap>(
    event: K,
    listener: (data: SSEPayloadMap[K]) => void
  ) => () => void;
  reconnect: () => void;
}

const SSEContext = React.createContext<SSEContextValue | null>(null);

export function SSEProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();
  const [connectionState, setConnectionState] =
    React.useState<SSEConnectionState>("disconnected");

  React.useEffect(() => {
    const unsub = sseClient.onStateChange((state) => {
      setConnectionState(state);
    });

    return () => {
      unsub();
    };
  }, []);

  React.useEffect(() => {
    if (isAuthenticated) {
      sseClient.connect();

      // Listen for system alerts to show toasts
      const unsubAlert = sseClient.on("system_alert", (alert) => {
        toast({
          title: "System Alert",
          message: alert.message,
          type: alert.level || "info",
        });
      });

      return () => {
        unsubAlert();
      };
    } else {
      sseClient.disconnect();
    }
  }, [isAuthenticated, toast]);

  const subscribe = React.useCallback(
    <K extends keyof SSEPayloadMap>(
      event: K,
      listener: (data: SSEPayloadMap[K]) => void
    ) => {
      return sseClient.on(event, listener);
    },
    []
  );

  const reconnect = React.useCallback(() => {
    sseClient.disconnect();
    sseClient.connect();
  }, []);

  return (
    <SSEContext.Provider value={{ connectionState, subscribe, reconnect }}>
      {children}
    </SSEContext.Provider>
  );
}

export function useSSE() {
  const context = React.useContext(SSEContext);
  if (!context) {
    throw new Error("useSSE must be used within an SSEProvider");
  }
  return context;
}
