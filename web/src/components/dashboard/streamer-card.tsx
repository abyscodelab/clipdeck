"use client";

import * as React from "react";
import Link from "next/link";
import { Users, MessageSquare, ExternalLink } from "@/components/icons";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { HypeSparkline } from "./hype-sparkline";
import { ClipNowButton } from "./clip-now-button";
import { formatNumber, getHypeColor } from "@/lib/utils";
import type { Streamer } from "@/lib/types";
import type { SparklinePoint } from "@/hooks/use-live-data";

interface StreamerCardProps {
  streamer: Streamer;
  sparklinePoints?: SparklinePoint[];
  onClip: (streamerId: number, duration: number) => Promise<any>;
}

export function StreamerCard({
  streamer,
  sparklinePoints = [],
  onClip,
}: StreamerCardProps) {
  const currentScore = Number(streamer.current_hype ?? 0) || 0;
  const currentMps = Number(streamer.current_mps ?? 0) || 0;
  const hypeColor = getHypeColor(currentScore);

  const platformKey = (streamer.platform?.toLowerCase() || "youtube") as "twitch" | "kick" | "youtube";
  const platformBadgeVariant = (["twitch", "kick", "youtube"].includes(platformKey)
    ? platformKey
    : "default") as any;

  return (
    <Card className="overflow-hidden border-border bg-surface hover:border-white/20 transition-all flex flex-col justify-between">
      {/* Top Header */}
      <CardContent className="p-4 sm:p-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          {/* Avatar & Names */}
          <Link
            href={`/streamers/${streamer.id}`}
            className="flex items-center gap-3 min-w-0 group"
          >
            <div className="relative shrink-0">
              <Avatar
                fallback={streamer.name}
                size="default"
                className="border border-white/10 group-hover:border-white/20 transition-colors"
              />
              <span className="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-surface">
                <span className="h-2 w-2 rounded-full bg-live animate-live" />
              </span>
            </div>

            <div className="flex flex-col truncate">
              <div className="flex items-center gap-1.5">
                <h4 className="font-semibold text-white text-sm truncate group-hover:text-white transition-colors">
                  {streamer.name}
                </h4>
                <ExternalLink className="h-3 w-3 text-neutral-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant={platformBadgeVariant} className="text-[10px] uppercase font-medium py-0 px-1.5">
                  {streamer.platform}
                </Badge>
                {streamer.niche && (
                  <span className="text-[11px] text-muted-foreground truncate max-w-[100px]">
                    {streamer.niche}
                  </span>
                )}
              </div>
            </div>
          </Link>

          {/* Viewers Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-border text-xs text-neutral-300">
            <Users className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-bold tabular-nums">
              {formatNumber(streamer.viewer_count)}
            </span>
          </div>
        </div>

        {/* Hype Score & Velocity Row */}
        <div className="mt-4 flex items-baseline justify-between">
          <div className="flex items-baseline gap-2">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
              Hype Velocity
            </span>
            <div className="flex items-center gap-1 text-xs text-gray-400">
              <MessageSquare className="h-3 w-3" />
              <span className="tabular-nums font-mono">{currentMps.toFixed(1)}/s</span>
            </div>
          </div>

          {/* Big Hype Score */}
          <div className="flex items-baseline gap-1">
            <span
              className={`text-3xl sm:text-4xl font-black tabular-nums tracking-tight ${hypeColor.text}`}
            >
              {Math.round(currentScore)}
            </span>
            <span className="text-xs text-muted-foreground font-bold">/100</span>
          </div>
        </div>

        {/* Real-time Sparkline */}
        <div className="mt-2 rounded-xl bg-[#0D0D0D] p-2.5 border border-border">
          <HypeSparkline
            points={sparklinePoints}
            height={52}
            currentScore={currentScore}
            threshold={60}
          />
        </div>
      </CardContent>

      {/* Prominent Clip Now Button */}
      <div className="p-4 pt-0 sm:p-5 sm:pt-0">
        <ClipNowButton
          streamerId={streamer.id}
          streamerName={streamer.name}
          onClip={onClip}
          size="default"
        />
      </div>
    </Card>
  );
}
