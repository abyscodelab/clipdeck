"use client";

import * as React from "react";
import Link from "next/link";
import { Film, Play, Clock, Sparkles, Filter, RefreshCw, DollarSign, Layers } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { formatDuration, formatRelativeTime } from "@/lib/utils";
import type { Clip, Streamer } from "@/lib/types";

export default function ClipsPage() {
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [streamerFilter, setStreamerFilter] = React.useState<string>("");

  // Fetch Streamers for filter
  const { data: streamers = [] } = useApi<Streamer[]>(
    () => api.streamers.list(),
    []
  );

  // Fetch Clips
  const {
    data: clips = [],
    isLoading,
    mutate,
  } = useApi<Clip[]>(
    () =>
      api.clips.list({
        status: statusFilter || undefined,
        streamer_id: streamerFilter ? Number(streamerFilter) : undefined,
        limit: 50,
      }),
    [statusFilter, streamerFilter]
  );

  const streamerMap = React.useMemo(() => {
    const map = new Map<number, string>();
    streamers.forEach((s) => map.set(s.id, s.name));
    return map;
  }, [streamers]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Film className="h-6 w-6 text-accent" />
              Vertical Clips (9:16)
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              AI-edited vertical videos formatted with ASS animated subtitles and blurred backgrounds for TikTok, Reels & Shorts.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => mutate()}
            className="gap-1.5 text-xs h-9"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh Clips
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl border border-border bg-surface">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider shrink-0 mr-2">
            <Filter className="h-3.5 w-3.5 text-accent" />
            <span>Filter</span>
          </div>

          <div className="w-full sm:w-48">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="rendered">Rendered & Ready</option>
              <option value="rendering">Rendering</option>
              <option value="editing">AI Editing</option>
              <option value="scoring">Scoring</option>
              <option value="failed">Failed</option>
            </Select>
          </div>

          <div className="w-full sm:w-48">
            <Select
              value={streamerFilter}
              onChange={(e) => setStreamerFilter(e.target.value)}
            >
              <option value="">All Streamers</option>
              {streamers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* Clips Grid */}
        {isLoading && clips.length === 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="w-full aspect-[9/16] rounded-xl" />
                <Skeleton className="h-4 w-3/4 rounded" />
                <Skeleton className="h-3 w-1/2 rounded" />
              </div>
            ))}
          </div>
        ) : clips.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/30 p-12 text-center flex flex-col items-center">
            <Film className="h-10 w-10 text-muted-foreground/60 mb-2" />
            <h3 className="text-base font-semibold text-white">No rendered clips yet</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm mb-4">
              Trigger an &quot;AI Edit&quot; on any detected moment to generate deterministic 9:16 vertical clips with subtitles.
            </p>
            <Link href="/moments">
              <Button size="sm" className="gap-1.5">
                <Sparkles className="h-4 w-4" />
                Browse Detected Moments
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {clips.map((clip) => {
              const streamerName =
                streamerMap.get(clip.streamer_id) || `Streamer #${clip.streamer_id}`;

              const statusVariant = {
                rendered: "success",
                rendering: "warning",
                editing: "default",
                scoring: "warning",
                failed: "destructive",
              }[clip.status] as any;

              return (
                <Link
                  key={clip.id}
                  href={`/clips/${clip.id}`}
                  className="group flex flex-col rounded-xl overflow-hidden border border-border bg-surface hover:border-accent/60 transition-all hover:shadow-lg hover:shadow-accent/10"
                >
                  {/* 9:16 Video Thumbnail Container */}
                  <div className="relative w-full aspect-[9/16] bg-black overflow-hidden flex items-center justify-center">
                    {clip.thumbnail_path ? (
                      <img
                        src={clip.thumbnail_path}
                        alt={clip.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center p-3 text-center text-muted-foreground">
                        <Film className="h-8 w-8 text-accent mb-2" />
                        <span className="text-[10px] uppercase font-mono tracking-wider">
                          {clip.status}
                        </span>
                      </div>
                    )}

                    {/* Play Hover Overlay */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <div className="h-10 w-10 rounded-full bg-accent text-white flex items-center justify-center shadow-lg">
                        <Play className="h-5 w-5 fill-current ml-0.5" />
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="absolute top-2 left-2">
                      <Badge variant={statusVariant} className="text-[9px] uppercase font-bold py-0 px-1.5">
                        {clip.status}
                      </Badge>
                    </div>

                    {/* Duration Badge */}
                    <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      <span>{formatDuration(clip.duration || 30)}</span>
                    </div>

                    {/* Cost Badge */}
                    {clip.cost_usd > 0 && (
                      <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/40 text-[9px] font-mono text-emerald-400">
                        ${clip.cost_usd.toFixed(3)}
                      </div>
                    )}
                  </div>

                  {/* Card Metadata */}
                  <div className="p-3 flex-1 flex flex-col justify-between">
                    <div>
                      <h4 className="font-bold text-white text-xs line-clamp-2 group-hover:text-accent-light transition-colors">
                        {clip.title || `Clip #${clip.id}`}
                      </h4>
                      <p className="text-[11px] text-muted-foreground mt-1 truncate">
                        {streamerName}
                      </p>
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/50 text-[10px] text-muted-foreground">
                      <span className="font-mono">{formatRelativeTime(clip.created_at)}</span>
                      <span className="font-mono text-accent">9:16</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
