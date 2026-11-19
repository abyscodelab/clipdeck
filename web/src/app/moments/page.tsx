"use client";

import * as React from "react";
import { Sparkles, ArrowUpDown } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { MomentCard } from "@/components/dashboard/moment-card";
import { MomentFilters, type MomentFilterValues } from "@/components/moments/moment-filters";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import type { Moment, Streamer } from "@/lib/types";

export default function MomentsPage() {
  const { toast } = useToast();

  const [filters, setFilters] = React.useState<MomentFilterValues>({
    sortBy: "date",
  });

  // Fetch Streamers for filter dropdown
  const { data: streamers = [] } = useApi<Streamer[]>(
    () => api.streamers.list(),
    []
  );

  // Fetch Moments
  const {
    data: moments = [],
    isLoading,
    mutate,
  } = useApi<Moment[]>(
    () =>
      api.moments.list({
        streamer_id: filters.streamerId,
        status: filters.status,
        limit: 100,
      }),
    [filters.streamerId, filters.status]
  );

  // Map streamers
  const streamerMap = React.useMemo(() => {
    const map = new Map<number, string>();
    streamers.forEach((s) => map.set(s.id, s.name));
    return map;
  }, [streamers]);

  // Client-side filter & sort
  const processedMoments = React.useMemo(() => {
    let result = [...moments];

    if (filters.triggerType) {
      result = result.filter((m) => m.trigger_type === filters.triggerType);
    }

    if (filters.sortBy === "hype") {
      result.sort((a, b) => b.hype_score - a.hype_score);
    } else {
      result.sort(
        (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
      );
    }

    return result;
  }, [moments, filters.triggerType, filters.sortBy]);

  const handleUpdateStatus = async (
    momentId: number,
    status: "approved" | "rejected"
  ) => {
    try {
      await api.moments.updateStatus(momentId, status);
      toast({
        title: "Moment Updated",
        message: `Marked as ${status}`,
        type: "success",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Failed to update status",
        type: "error",
      });
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Title */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-accent" />
              Detected Moments & Clips
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Browse, filter, review, and approve automated hype spikes and manual clips.
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <MomentFilters
          streamers={streamers}
          values={filters}
          onChange={setFilters}
          onReset={() => setFilters({ sortBy: "date" })}
        />

        {/* Moments List */}
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex gap-4 p-4 rounded-xl border border-border bg-surface">
                <Skeleton className="h-20 w-36 rounded-lg shrink-0" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-36" />
                </div>
              </div>
            ))}
          </div>
        ) : processedMoments.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/30 p-12 text-center flex flex-col items-center">
            <Sparkles className="h-8 w-8 text-muted-foreground mb-2" />
            <h3 className="text-sm font-semibold text-white">No moments found</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Try adjusting your filter criteria or wait for live stream spikes.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {processedMoments.map((moment) => (
              <MomentCard
                key={moment.id}
                moment={moment}
                streamerName={streamerMap.get(moment.streamer_id) || "Streamer"}
                onApprove={(id) => handleUpdateStatus(id, "approved")}
                onReject={(id) => handleUpdateStatus(id, "rejected")}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
