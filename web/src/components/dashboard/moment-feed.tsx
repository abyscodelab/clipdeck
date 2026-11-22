"use client";

import * as React from "react";
import Link from "next/link";
import { Sparkles, ArrowRight, Filter } from "@/components/icons";
import { MomentCard } from "./moment-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import type { Moment, Streamer } from "@/lib/types";

interface MomentFeedProps {
  moments: Moment[];
  streamers: Streamer[];
  isLoading: boolean;
  onUpdateStatus: (momentId: number, status: "approved" | "rejected" | "reviewed") => void;
}

export function MomentFeed({
  moments,
  streamers,
  isLoading,
  onUpdateStatus,
}: MomentFeedProps) {
  const [filter, setFilter] = React.useState<"all" | "detected" | "approved">("all");

  const safeStreamers = Array.isArray(streamers) ? streamers : [];
  const safeMoments = Array.isArray(moments) ? moments : [];

  const streamerMap = React.useMemo(() => {
    const map = new Map<number, string>();
    safeStreamers.forEach((s) => {
      if (s && s.id) map.set(s.id, s.name);
    });
    return map;
  }, [safeStreamers]);

  const filteredMoments = React.useMemo(() => {
    if (filter === "all") return safeMoments;
    return safeMoments.filter((m) => m && m.status === filter);
  }, [safeMoments, filter]);

  return (
    <div className="space-y-4">
      {/* Feed Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
            Live Moment Feed
          </h2>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Filter tabs */}
          <div className="flex items-center rounded-lg bg-surface border border-border p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                filter === "all" ? "bg-accent text-white font-bold" : "text-muted-foreground hover:text-white"
              }`}
            >
              All ({moments.length})
            </button>
            <button
              type="button"
              onClick={() => setFilter("detected")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                filter === "detected" ? "bg-accent text-white font-bold" : "text-muted-foreground hover:text-white"
              }`}
            >
              New
            </button>
            <button
              type="button"
              onClick={() => setFilter("approved")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                filter === "approved" ? "bg-accent text-white font-bold" : "text-muted-foreground hover:text-white"
              }`}
            >
              Approved
            </button>
          </div>

          <Link href="/moments">
            <Button variant="ghost" size="sm" className="text-xs gap-1 hidden sm:flex">
              View All
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex gap-4 p-4 rounded-xl border border-border bg-surface">
              <Skeleton className="h-20 w-32 rounded-lg shrink-0" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-32" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredMoments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface/30 p-8 text-center flex flex-col items-center">
          <Sparkles className="h-8 w-8 text-muted-foreground/60 mb-2" />
          <h4 className="text-sm font-semibold text-gray-300">No moments recorded yet</h4>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm">
            Moments trigger automatically when chat velocity spikes beyond the threshold, or when you click &quot;Clip Now&quot;.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredMoments.slice(0, 15).map((moment) => (
            <MomentCard
              key={moment.id}
              moment={moment}
              streamerName={streamerMap.get(moment.streamer_id) || "Live Streamer"}
              onApprove={(id) => onUpdateStatus(id, "approved")}
              onReject={(id) => onUpdateStatus(id, "rejected")}
            />
          ))}
        </div>
      )}
    </div>
  );
}
