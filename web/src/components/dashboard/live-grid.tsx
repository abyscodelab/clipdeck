"use client";

import * as React from "react";
import Link from "next/link";
import { Radio, ChevronDown, ChevronUp, Plus, Clock, ExternalLink } from "@/components/icons";
import { StreamerCard } from "./streamer-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { formatRelativeTime } from "@/lib/utils";
import type { Streamer } from "@/lib/types";
import type { SparklinePoint } from "@/hooks/use-live-data";

interface LiveGridProps {
  liveStreamers: Streamer[];
  offlineStreamers: Streamer[];
  sparklines: Record<number, SparklinePoint[]>;
  isLoading: boolean;
  onClip: (streamerId: number, duration: number) => Promise<any>;
}

export function LiveGrid({
  liveStreamers,
  offlineStreamers,
  sparklines,
  isLoading,
  onClip,
}: LiveGridProps) {
  const [isOfflineOpen, setIsOfflineOpen] = React.useState(true);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl border border-border bg-surface p-5 space-y-4">
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="space-y-1.5 flex-1">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-3 w-16" />
              </div>
            </div>
            <Skeleton className="h-14 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ))}
      </div>
    );
  }

  const totalConfigured = (liveStreamers?.length || 0) + (offlineStreamers?.length || 0);

  return (
    <div className="space-y-6">
      {/* Live Streamers Section */}
      <div>
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <span
              className={`flex h-2.5 w-2.5 rounded-full ${
                liveStreamers.length > 0 ? "bg-live animate-live" : "bg-neutral-500"
              }`}
            />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Live Channels
            </h2>
            <Badge
              variant={liveStreamers.length > 0 ? "live" : "secondary"}
              className="text-xs"
            >
              {liveStreamers.length} Active
            </Badge>
          </div>

          <Link href="/streamers">
            <Button variant="ghost" size="sm" className="text-xs gap-1 text-accent">
              <Plus className="h-3.5 w-3.5" />
              Manage Channels
            </Button>
          </Link>
        </div>

        {liveStreamers.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {liveStreamers.map((streamer) => (
              <StreamerCard
                key={streamer.id}
                streamer={streamer}
                sparklinePoints={sparklines[streamer.id] || []}
                onClip={onClip}
              />
            ))}
          </div>
        ) : totalConfigured > 0 ? (
          /* When streamers are configured, but currently none are live */
          <div className="rounded-2xl border border-border/80 bg-surface/40 p-6 sm:p-7 text-center flex flex-col items-center justify-center">
            <div className="flex items-center justify-center h-11 w-11 rounded-2xl bg-white/[0.04] border border-white/10 text-neutral-400 mb-3">
              <Radio className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">
              Channels Monitored & Ready
            </h3>
            <p className="text-xs text-neutral-400 max-w-md mt-1 mb-4 leading-relaxed">
              Your configured channels are actively monitored in standby. The moment a streamer goes live, real-time hype velocity tracking and DVR recording will engage.
            </p>
            <div className="flex items-center gap-2.5">
              <Link href="/streamers">
                <Button size="sm" variant="outline" className="text-xs gap-1.5 border-border">
                  <Plus className="h-3.5 w-3.5" />
                  Add More Channels
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          /* Truly zero streamers configured */
          <div className="rounded-2xl border border-dashed border-border bg-surface/40 p-8 text-center flex flex-col items-center justify-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-full bg-surface-hover text-muted-foreground mb-3">
              <Radio className="h-6 w-6" />
            </div>
            <h3 className="text-base font-semibold text-white">No Monitored Channels Added</h3>
            <p className="text-xs text-muted-foreground max-w-sm mt-1 mb-4">
              Add YouTube, Kick, or Twitch channels to start automated 24/7 stream recording and AI moment clipping.
            </p>
            <Link href="/streamers">
              <Button size="sm" className="gap-1.5">
                <Plus className="h-4 w-4" />
                Add First Streamer
              </Button>
            </Link>
          </div>
        )}
      </div>

      {/* Standby / Offline Channels Section */}
      {offlineStreamers.length > 0 && (
        <div className="rounded-2xl border border-border bg-surface/60 overflow-hidden">
          <button
            type="button"
            onClick={() => setIsOfflineOpen(!isOfflineOpen)}
            className="flex items-center justify-between w-full p-4 text-left hover:bg-surface-hover/50 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="h-2 w-2 rounded-full bg-neutral-500" />
              <span className="text-sm font-bold text-neutral-200">
                Monitored Channels in Standby ({offlineStreamers.length})
              </span>
              <span className="text-[11px] text-neutral-500 hidden sm:inline">
                Waiting for broadcast
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-neutral-400">
              <span>{isOfflineOpen ? "Hide" : "Show"}</span>
              {isOfflineOpen ? (
                <ChevronUp className="h-4 w-4 text-neutral-400" />
              ) : (
                <ChevronDown className="h-4 w-4 text-neutral-400" />
              )}
            </div>
          </button>

          {isOfflineOpen && (
            <div className="p-4 pt-0 border-t border-border/50 divide-y divide-border/40">
              {offlineStreamers.map((st) => (
                <div
                  key={st.id}
                  className="flex items-center justify-between py-3 first:pt-3.5 last:pb-1 gap-3"
                >
                  <Link
                    href={`/streamers/${st.id}`}
                    className="flex items-center gap-3 group min-w-0 flex-1"
                  >
                    <Avatar fallback={st.name} size="sm" className="opacity-80" />
                    <div className="flex flex-col truncate">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-semibold text-neutral-200 group-hover:text-white truncate">
                          {st.name}
                        </span>
                        <ExternalLink className="h-3 w-3 text-neutral-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] font-mono text-neutral-400 uppercase">
                          {st.platform}
                        </span>
                        {st.niche && (
                          <span className="text-[10px] text-neutral-500 truncate max-w-[150px]">
                            • {st.niche}
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>

                  <div className="flex items-center gap-2 text-xs text-neutral-400 shrink-0">
                    <span className="px-2 py-0.5 rounded-full bg-white/[0.04] border border-border text-[10px] font-mono text-neutral-400">
                      Auto-Monitor Active
                    </span>
                    <Clock className="h-3 w-3 ml-1 text-neutral-500" />
                    <span className="text-[11px] text-neutral-500">
                      {st.last_live
                        ? `Last live ${formatRelativeTime(st.last_live)}`
                        : "Offline"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
