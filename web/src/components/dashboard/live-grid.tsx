"use client";

import * as React from "react";
import Link from "next/link";
import { Radio, ChevronDown, ChevronUp, Plus, Clock } from "@/components/icons";
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
  const [isOfflineOpen, setIsOfflineOpen] = React.useState(false);

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

  return (
    <div className="space-y-6">
      {/* Live Streamers Section */}
      <div>
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-live animate-live" />
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Live Channels
            </h2>
            <Badge variant="live" className="text-xs">
              {liveStreamers.length} Active
            </Badge>
          </div>

          <Link href="/streamers">
            <Button variant="ghost" size="sm" className="text-xs gap-1 text-accent">
              <Plus className="h-3.5 w-3.5" />
              Add Streamer
            </Button>
          </Link>
        </div>

        {liveStreamers.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface/40 p-8 text-center flex flex-col items-center justify-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-full bg-surface-hover text-muted-foreground mb-3">
              <Radio className="h-6 w-6" />
            </div>
            <h3 className="text-base font-semibold text-white">No Monitored Streamers Live</h3>
            <p className="text-xs text-muted-foreground max-w-sm mt-1 mb-4">
              None of your configured channels are currently broadcasting. Add more channels or wait for auto-detection.
            </p>
            <Link href="/streamers">
              <Button size="sm" className="gap-1.5">
                <Plus className="h-4 w-4" />
                Configure Streamers
              </Button>
            </Link>
          </div>
        ) : (
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
        )}
      </div>

      {/* Offline Streamers Collapsible Section */}
      {offlineStreamers.length > 0 && (
        <div className="rounded-xl border border-border bg-surface/60 overflow-hidden">
          <button
            type="button"
            onClick={() => setIsOfflineOpen(!isOfflineOpen)}
            className="flex items-center justify-between w-full p-4 text-left hover:bg-surface-hover/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-gray-500" />
              <span className="text-sm font-semibold text-gray-300">
                Offline Channels ({offlineStreamers.length})
              </span>
            </div>
            {isOfflineOpen ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>

          {isOfflineOpen && (
            <div className="p-4 pt-0 border-t border-border/50 divide-y divide-border/40">
              {offlineStreamers.map((st) => (
                <div
                  key={st.id}
                  className="flex items-center justify-between py-2.5 first:pt-3 last:pb-1"
                >
                  <Link
                    href={`/streamers/${st.id}`}
                    className="flex items-center gap-3 group min-w-0"
                  >
                    <Avatar fallback={st.name} size="sm" className="opacity-75" />
                    <div className="flex flex-col truncate">
                      <span className="text-sm font-medium text-gray-300 group-hover:text-white truncate">
                        {st.name}
                      </span>
                      <span className="text-[10px] text-muted-foreground uppercase">
                        {st.platform}
                      </span>
                    </div>
                  </Link>

                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>
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
