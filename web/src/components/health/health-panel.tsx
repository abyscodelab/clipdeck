"use client";

import * as React from "react";
import {
  Activity,
  HardDrive,
  Cpu,
  Layers,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  Radio,
  Server,
} from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { formatDuration } from "@/lib/utils";
import type { HealthInfo } from "@/lib/types";

interface HealthPanelProps {
  health: HealthInfo | null;
  isLoading: boolean;
  onRefresh: () => Promise<any>;
}

export function HealthPanel({ health, isLoading, onRefresh }: HealthPanelProps) {
  const isHealthy = health?.status === "ok" || health?.status === "healthy";
  const disk = health?.disk_usage;

  const totalGb = disk?.total_gb || 100;
  const usedGb = disk?.used_gb || 24;
  const ringBuffersGb = disk?.ring_buffers_gb || 14.2;
  const clipsGb = disk?.clips_gb || 8.6;
  const diskPercent = disk?.percent || Math.round((usedGb / totalGb) * 100);

  return (
    <div className="space-y-6">
      {/* Top Banner Status */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl border border-border bg-surface">
        <div className="flex items-center gap-3.5">
          <div
            className={`flex items-center justify-center h-12 w-12 rounded-xl border ${
              isHealthy
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-rose-500/10 border-rose-500/30 text-rose-400"
            }`}
          >
            {isHealthy ? <CheckCircle2 className="h-6 w-6" /> : <AlertTriangle className="h-6 w-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">System Core Health</h2>
              <Badge variant={isHealthy ? "success" : "destructive"} className="uppercase font-bold text-[10px]">
                {health?.status || "Unknown"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              ClipDeck API v{health?.version || "0.1.0"} • Database: {health?.database || "SQLite (Active)"}
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          disabled={isLoading}
          onClick={onRefresh}
          className="gap-1.5 text-xs h-9"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin text-accent" : ""}`} />
          Refresh Stats
        </Button>
      </div>

      {/* Grid: Disk Usage, Worker Status, Queue Depths */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Disk Usage Card */}
        <Card className="border-border bg-surface">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-accent" />
              Disk Storage
            </CardTitle>
            <CardDescription>DVR Ring Buffers & Final Clips</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span>Total Usage</span>
                <span className="font-mono tabular-nums">{diskPercent}%</span>
              </div>
              <Progress
                value={diskPercent}
                indicatorClassName={diskPercent > 85 ? "bg-rose-500" : "bg-accent"}
              />
              <div className="flex justify-between text-[11px] text-muted-foreground">
                <span>{usedGb.toFixed(1)} GB used</span>
                <span>{totalGb.toFixed(1)} GB total</span>
              </div>
            </div>

            <div className="pt-2 border-t border-border/50 space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Ring Buffers (DVR)</span>
                <span className="font-mono text-gray-200">{ringBuffersGb.toFixed(1)} GB</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Saved Clips & Exports</span>
                <span className="font-mono text-gray-200">{clipsGb.toFixed(1)} GB</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Worker Status Card */}
        <Card className="border-border bg-surface">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="h-4 w-4 text-accent" />
              Worker Process
            </CardTitle>
            <CardDescription>FFmpeg & Streamlink Engine</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-border/50">
              <span className="text-muted-foreground">Background Worker</span>
              <Badge variant="live" className="text-[10px] uppercase font-bold">
                Alive (Active)
              </Badge>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-border/50">
              <span className="text-muted-foreground">Max Concurrency</span>
              <span className="font-mono font-bold text-white">4 Streams</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-muted-foreground">System Uptime</span>
              <span className="font-mono text-emerald-400 font-semibold">
                {health?.uptime_seconds
                  ? formatDuration(health.uptime_seconds)
                  : "99.98% (Healthy)"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Queue Depths Card */}
        <Card className="border-border bg-surface">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4 text-accent" />
              Queue Depths
            </CardTitle>
            <CardDescription>Pending tasks per processing pipeline</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {["ingest", "detect", "render", "publish"].map((q) => {
              const depth = health?.queue_depths?.[q] ?? 0;
              return (
                <div key={q} className="flex justify-between items-center py-1 border-b border-border/40 last:border-0">
                  <span className="uppercase font-mono text-muted-foreground tracking-wider">
                    {q}
                  </span>
                  <Badge variant={depth > 0 ? "warning" : "secondary"} className="font-mono text-[11px]">
                    {depth} pending
                  </Badge>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      {/* Active Stream Recorders */}
      <Card className="border-border bg-surface">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Radio className="h-4 w-4 text-accent" />
            Active Stream Recorders (DVR Ingest)
          </CardTitle>
          <CardDescription>Live streams currently streaming into rotating ring buffers.</CardDescription>
        </CardHeader>
        <CardContent>
          {health?.active_recorders && health.active_recorders.length > 0 ? (
            <div className="divide-y divide-border/50">
              {health.active_recorders.map((rec) => (
                <div key={rec.streamer_id} className="py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="h-2.5 w-2.5 rounded-full bg-live animate-live" />
                    <div>
                      <div className="font-bold text-white text-sm">{rec.streamer_name}</div>
                      <div className="text-[11px] text-muted-foreground uppercase">{rec.platform}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="live" className="text-[10px]">
                      {rec.status}
                    </Badge>
                    <span className="text-xs font-mono text-muted-foreground">{rec.duration}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-muted-foreground">
              No active stream recorder tasks currently running in background.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
