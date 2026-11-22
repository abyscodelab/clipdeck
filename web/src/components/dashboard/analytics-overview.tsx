"use client";

import * as React from "react";
import { Radio, Users, Sparkles, Flame, TrendingUp } from "@/components/icons";
import { formatNumber, getHypeColor } from "@/lib/utils";
import type { Streamer, Moment } from "@/lib/types";

interface AnalyticsOverviewProps {
  streamers: Streamer[];
  liveStreamers: Streamer[];
  moments: Moment[];
  isLoading?: boolean;
}

export function AnalyticsOverview({
  streamers,
  liveStreamers,
  moments,
  isLoading = false,
}: AnalyticsOverviewProps) {
  const totalViewers = React.useMemo(() => {
    return (liveStreamers || []).reduce((acc, s) => acc + (Number(s.viewer_count) || 0), 0);
  }, [liveStreamers]);

  const peakHype = React.useMemo(() => {
    if (!liveStreamers || liveStreamers.length === 0) return 0;
    return Math.max(...liveStreamers.map((s) => Number(s.current_hype) || 0), 0);
  }, [liveStreamers]);

  const approvedMoments = React.useMemo(() => {
    return (moments || []).filter((m) => m.status === "approved").length;
  }, [moments]);

  const peakHypeColor = getHypeColor(peakHype);

  const metrics = [
    {
      title: "Active Live Feeds",
      value: `${liveStreamers.length} / ${streamers.length}`,
      subtext: `${streamers.length - liveStreamers.length} channels in standby`,
      icon: Radio,
      iconColor: "text-emerald-400",
      iconBg: "bg-emerald-500/10 border-emerald-500/20",
      badge: liveStreamers.length > 0 ? "LIVE MONITORING" : "STANDBY",
      badgeClass:
        liveStreamers.length > 0
          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
          : "bg-white/[0.05] text-neutral-400 border-border",
      pulse: liveStreamers.length > 0,
    },
    {
      title: "Concurrent Audience",
      value: formatNumber(totalViewers),
      subtext: liveStreamers.length > 0 ? "Live viewer aggregate" : "Waiting for broadcasts",
      icon: Users,
      iconColor: "text-sky-400",
      iconBg: "bg-sky-500/10 border-sky-500/20",
      badge: "REAL-TIME",
      badgeClass: "bg-sky-500/10 text-sky-400 border-sky-500/30",
      pulse: false,
    },
    {
      title: "Moments Captured",
      value: `${moments.length}`,
      subtext: `${approvedMoments} approved viral clips`,
      icon: Sparkles,
      iconColor: "text-amber-400",
      iconBg: "bg-amber-500/10 border-amber-500/20",
      badge: `${moments.filter((m) => m.status === "detected").length} NEW`,
      badgeClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
      pulse: false,
    },
    {
      title: "Peak Hype Surge",
      value: `${Math.round(peakHype)}/100`,
      subtext: peakHype >= 65 ? "Chat velocity spike" : "Chat baseline velocity",
      icon: Flame,
      iconColor: peakHypeColor.text,
      iconBg: `${peakHypeColor.bg} ${peakHypeColor.border}`,
      badge: peakHype >= 65 ? "SURGE ACTIVE" : "NORMAL",
      badgeClass: `${peakHypeColor.bg} ${peakHypeColor.text} ${peakHypeColor.border}`,
      pulse: peakHype >= 65,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
      {metrics.map((metric, idx) => {
        const Icon = metric.icon;
        return (
          <div
            key={idx}
            className="relative rounded-2xl border border-border bg-[#141414] p-4 sm:p-5 flex flex-col justify-between overflow-hidden shadow-sm hover:border-white/20 transition-all group"
          >
            {/* Top row: Icon + Badge */}
            <div className="flex items-center justify-between mb-3">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-xl border ${metric.iconBg} ${metric.iconColor}`}
              >
                <Icon className="h-4 w-4" />
              </div>

              <div
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-bold tracking-wider uppercase font-mono ${metric.badgeClass}`}
              >
                {metric.pulse && (
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
                  </span>
                )}
                <span>{metric.badge}</span>
              </div>
            </div>

            {/* Value & Title */}
            <div>
              <div className="text-2xl sm:text-3xl font-black text-white tracking-tight tabular-nums">
                {metric.value}
              </div>
              <div className="text-xs font-semibold text-neutral-300 mt-0.5">
                {metric.title}
              </div>
              <div className="text-[11px] text-neutral-500 mt-1 truncate">
                {metric.subtext}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
