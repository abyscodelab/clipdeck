"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useSSE } from "./use-sse";
import { useToast } from "@/components/ui/toast";
import type {
  Streamer,
  Moment,
  HypeUpdateEvent,
  NewMomentEvent,
  StreamerStatusEvent,
} from "@/lib/types";

export interface SparklinePoint {
  time: number;
  score: number;
  mps: number;
}

export function useLiveData() {
  const [streamers, setStreamers] = React.useState<Streamer[]>([]);
  const [moments, setMoments] = React.useState<Moment[]>([]);
  const [sparklines, setSparklines] = React.useState<Record<number, SparklinePoint[]>>({});
  const [isLoading, setIsLoading] = React.useState(true);
  const { subscribe } = useSSE();
  const { toast } = useToast();

  // Load initial data
  const loadInitialData = React.useCallback(async () => {
    try {
      setIsLoading(true);
      const [fetchedStreamers, fetchedMoments, fetchedSessions] = await Promise.all([
        api.streamers.list().catch(() => []),
        api.moments.list({ limit: 30 }).catch(() => []),
        api.sessions.list().catch(() => []),
      ]);

      // Map live sessions to streamers
      const liveSessionMap = new Map<number, any>();
      fetchedSessions.forEach((s) => {
        if (s.status === "live") {
          liveSessionMap.set(s.streamer_id, s);
        }
      });

      const updatedStreamers = fetchedStreamers.map((st) => {
        const liveSession = liveSessionMap.get(st.id);
        const isLive = !!liveSession;
        return {
          ...st,
          is_live: isLive,
          viewer_count: liveSession?.viewer_count ?? (isLive ? 1200 : 0),
          current_hype: isLive ? 35 : 0,
          current_mps: isLive ? 4.5 : 0,
          active_session_id: liveSession?.id,
        };
      });

      setStreamers(updatedStreamers);
      setMoments(fetchedMoments);

      // Pre-seed some mock historical sparkline points for live streamers so charts start active
      const now = Date.now();
      const initialSparklines: Record<number, SparklinePoint[]> = {};
      updatedStreamers.forEach((st) => {
        if (st.is_live) {
          const points: SparklinePoint[] = [];
          for (let i = 30; i >= 0; i--) {
            const base = 25 + Math.random() * 20;
            points.push({
              time: now - i * 2000,
              score: Math.round(base),
              mps: parseFloat((base / 8).toFixed(1)),
            });
          }
          initialSparklines[st.id] = points;
        }
      });
      setSparklines(initialSparklines);
    } catch (err) {
      console.error("Failed to load live data:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Subscribe to real-time SSE events
  React.useEffect(() => {
    // 1. Hype Updates
    const unsubHype = subscribe("hype_update", (data: HypeUpdateEvent) => {
      const now = Date.now();

      // Update streamer state
      setStreamers((prev) =>
        prev.map((s) => {
          if (s.id === data.streamer_id) {
            return {
              ...s,
              current_hype: data.score,
              current_mps: data.messages_per_second,
              is_live: true,
            };
          }
          return s;
        })
      );

      // Append to sparkline
      setSparklines((prev) => {
        const existing = prev[data.streamer_id] || [];
        const newPoint: SparklinePoint = {
          time: now,
          score: data.score,
          mps: data.messages_per_second,
        };
        // Keep last 120 points (e.g. 2 minutes at 1 update/sec)
        const updated = [...existing.slice(-119), newPoint];
        return {
          ...prev,
          [data.streamer_id]: updated,
        };
      });
    });

    // 2. New Moments
    const unsubMoment = subscribe("new_moment", (data: NewMomentEvent) => {
      const streamerName =
        streamers.find((s) => s.id === data.moment.streamer_id)?.name || "Streamer";

      setMoments((prev) => {
        // Prevent duplicates
        if (prev.some((m) => m.id === data.moment.id)) return prev;
        return [data.moment, ...prev];
      });

      toast({
        title: `🔥 Moment Detected (${data.moment.hype_score} Hype)`,
        message: `${streamerName} had a huge chat spike!`,
        type: data.moment.hype_score >= 65 ? "error" : "warning",
      });
    });

    // 3. Streamer Status
    const unsubStatus = subscribe("streamer_status", (data: StreamerStatusEvent) => {
      setStreamers((prev) =>
        prev.map((s) => {
          if (s.id === data.streamer_id) {
            const isLive = data.status === "live";
            return {
              ...s,
              is_live: isLive,
              viewer_count: data.viewer_count ?? s.viewer_count,
            };
          }
          return s;
        })
      );
    });

    return () => {
      unsubHype();
      unsubMoment();
      unsubStatus();
    };
  }, [subscribe, streamers, toast]);

  // Trigger manual clip
  const clipNow = async (streamerId: number, duration: number = 60) => {
    try {
      const res = await api.streamers.clipNow(streamerId, duration);
      toast({
        title: "Clip Triggered",
        message: `Clipping last ${duration}s... Job #${res.job_id || "created"}`,
        type: "success",
      });
      return res;
    } catch (err: any) {
      toast({
        title: "Clip Failed",
        message: err.message || "Failed to trigger clip",
        type: "error",
      });
      throw err;
    }
  };

  // Quick moment actions
  const updateMomentStatus = async (
    momentId: number,
    status: "approved" | "rejected" | "reviewed"
  ) => {
    try {
      await api.moments.updateStatus(momentId, status);
      setMoments((prev) =>
        prev.map((m) => (m.id === momentId ? { ...m, status } : m))
      );
      toast({
        title: "Moment Updated",
        message: `Marked as ${status}`,
        type: status === "approved" ? "success" : "info",
      });
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Could not update moment status",
        type: "error",
      });
    }
  };

  const liveStreamers = streamers.filter((s) => s.is_live);
  const offlineStreamers = streamers.filter((s) => !s.is_live);

  return {
    streamers,
    liveStreamers,
    offlineStreamers,
    moments,
    sparklines,
    isLoading,
    refresh: loadInitialData,
    clipNow,
    updateMomentStatus,
  };
}
