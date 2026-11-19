"use client";

import * as React from "react";
import Link from "next/link";
import { Flame, Activity, Radio } from "@/components/icons";
import { useSSE } from "@/hooks/use-sse";
import { Badge } from "@/components/ui/badge";

export function Header({ liveCount = 0 }: { liveCount?: number }) {
  const { connectionState } = useSSE();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-14 px-4 sm:px-6 bg-[#0D0D0D]/80 backdrop-blur-md border-b border-border">
      {/* Mobile brand (hidden on desktop) */}
      <div className="flex items-center gap-2 md:hidden">
        <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-white/10 text-white border border-white/10">
          <Flame className="h-4 w-4 fill-white" />
        </div>
        <span className="font-semibold text-white text-sm tracking-tight">ClipDeck</span>
      </div>

      {/* Desktop breadcrumb / status indicator */}
      <div className="hidden md:flex items-center gap-3 text-xs">
        <span className="font-medium text-neutral-400">Live Monitor</span>
        {liveCount > 0 ? (
          <Badge variant="live" className="gap-1.5 px-2.5 py-0.5 text-xs font-medium">
            <Radio className="h-3 w-3 animate-pulse text-emerald-400" />
            {liveCount} STREAM{liveCount > 1 ? "S" : ""} LIVE
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-xs text-neutral-400">
            No Active Streams
          </Badge>
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2 sm:gap-2.5">
        {/* Connection Indicator pill */}
        <div
          title={`SSE Stream: ${connectionState}`}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-border text-[11px]"
        >
          {connectionState === "connected" ? (
            <>
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              <span className="text-[11px] font-medium text-emerald-400 hidden sm:inline">
                Live SSE
              </span>
            </>
          ) : (
            <>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-rose-500" />
              <span className="text-[11px] font-medium text-rose-400 hidden sm:inline">
                {connectionState}
              </span>
            </>
          )}
        </div>

        {/* Health status link */}
        <Link
          href="/health"
          title="System Health"
          className="flex items-center justify-center h-8 w-8 rounded-lg border border-border bg-white/[0.03] text-neutral-400 hover:text-white hover:bg-white/[0.08] transition-colors active:scale-[0.96]"
        >
          <Activity className="h-3.5 w-3.5" />
        </Link>
      </div>
    </header>
  );
}
