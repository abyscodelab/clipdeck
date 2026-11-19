"use client";

import * as React from "react";
import { Activity } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { HealthPanel } from "@/components/health/health-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import type { HealthInfo } from "@/lib/types";

export default function HealthPage() {
  const {
    data: health = null,
    isLoading,
    mutate,
  } = useApi<HealthInfo>(() => api.health.get(), [], {
    refreshInterval: 10000, // Poll health every 10s
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <Activity className="h-6 w-6 text-accent" />
            Infrastructure & Health
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Real-time diagnostics for background worker containers, queue telemetry, and disk buffers.
          </p>
        </div>

        {isLoading && !health ? (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full rounded-2xl" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Skeleton className="h-44 rounded-xl" />
              <Skeleton className="h-44 rounded-xl" />
              <Skeleton className="h-44 rounded-xl" />
            </div>
          </div>
        ) : (
          <HealthPanel
            health={health}
            isLoading={isLoading}
            onRefresh={() => mutate()}
          />
        )}
      </div>
    </AppShell>
  );
}
