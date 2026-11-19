"use client";

import * as React from "react";
import Link from "next/link";
import { Check, X, Flame, Play, Clock } from "@/components/icons";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDuration, formatRelativeTime, getHypeColor, getMediaUrl } from "@/lib/utils";
import type { Moment } from "@/lib/types";

interface MomentCardProps {
  moment: Moment;
  streamerName?: string;
  onApprove?: (momentId: number) => void;
  onReject?: (momentId: number) => void;
}

export function MomentCard({
  moment,
  streamerName = "Streamer",
  onApprove,
  onReject,
}: MomentCardProps) {
  const hype = getHypeColor(moment.hype_score);

  const statusVariant = {
    detected: "warning",
    clipping: "warning",
    clipped: "default",
    approved: "success",
    rejected: "destructive",
    reviewed: "default",
    error: "destructive",
  }[moment.status] as any;

  return (
    <Card className="overflow-hidden border-border bg-surface hover:border-white/20 transition-all group flex flex-col sm:flex-row items-stretch sm:items-center justify-between p-3 sm:p-4 gap-3 sm:gap-4">
      {/* Thumbnail / Media Preview */}
      <Link
        href={`/moments/${moment.id}`}
        className="relative shrink-0 w-full sm:w-36 h-28 sm:h-20 rounded-xl overflow-hidden bg-black border border-border flex items-center justify-center group-hover:border-white/20 transition-colors"
      >
        {moment.thumbnail_path ? (
          <img
            src={getMediaUrl(moment.thumbnail_path)}
            alt="Clip thumbnail"
            className="w-full h-full object-cover outline outline-1 -outline-offset-1 outline-white/10"
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-muted-foreground">
            <Flame className={`h-6 w-6 ${hype.text} mb-1`} />
            <span className="text-[10px] font-mono uppercase tracking-wider">
              {moment.status}
            </span>
          </div>
        )}

        {/* Play Overlay */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
          <div className="h-8 w-8 rounded-full bg-white text-neutral-950 flex items-center justify-center shadow-lg">
            <Play className="h-3.5 w-3.5 fill-current ml-0.5" />
          </div>
        </div>

        {/* Duration pill */}
        <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white flex items-center gap-1">
          <Clock className="h-2.5 w-2.5" />
          <span>{formatDuration(moment.clip_duration || 60)}</span>
        </div>
      </Link>

      {/* Info details */}
      <div className="flex-1 min-w-0 flex flex-col justify-center">
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href={`/moments/${moment.id}`}
            className="font-semibold text-white text-sm sm:text-base hover:text-white transition-colors truncate"
          >
            {streamerName}
          </Link>
          <Badge variant={statusVariant} className="text-[10px] uppercase font-bold py-0 px-1.5">
            {moment.status}
          </Badge>
          {moment.trigger_type === "manual" && (
            <Badge variant="secondary" className="text-[10px] py-0 px-1.5">
              Manual
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground flex-wrap">
          <div className="flex items-center gap-1">
            <Flame className={`h-3.5 w-3.5 ${hype.text}`} />
            <span className={`font-bold tabular-nums ${hype.text}`}>
              {Math.round(moment.hype_score)} Hype
            </span>
          </div>
          <span>•</span>
          <span className="tabular-nums">{formatRelativeTime(moment.detected_at)}</span>
        </div>
      </div>

      {/* Quick Action Buttons */}
      <div className="flex items-center gap-2 shrink-0 self-end sm:self-center border-t sm:border-t-0 pt-2 sm:pt-0 w-full sm:w-auto justify-end">
        {moment.status !== "approved" && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onApprove?.(moment.id)}
            title="Approve Clip"
            className="h-8 px-2.5 gap-1 border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
          >
            <Check className="h-3.5 w-3.5" />
            <span className="text-xs font-semibold">Approve</span>
          </Button>
        )}

        {moment.status !== "rejected" && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onReject?.(moment.id)}
            title="Reject Clip"
            className="h-8 px-2.5 gap-1 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-400"
          >
            <X className="h-3.5 w-3.5" />
            <span className="text-xs">Reject</span>
          </Button>
        )}

        <Link href={`/moments/${moment.id}`}>
          <Button type="button" variant="secondary" size="sm" className="h-8 px-3 text-xs">
            Review
          </Button>
        </Link>
      </div>
    </Card>
  );
}
