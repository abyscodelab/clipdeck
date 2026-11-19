"use client";

import * as React from "react";
import { LiveGrid } from "@/components/dashboard/live-grid";
import { MomentFeed } from "@/components/dashboard/moment-feed";
import { useLiveData } from "@/hooks/use-live-data";
import { Sparkles, Radio } from "@/components/icons";

export default function DashboardPage() {
  const {
    streamers,
    liveStreamers,
    offlineStreamers,
    moments,
    sparklines,
    isLoading,
    clipNow,
    updateMomentStatus,
  } = useLiveData();

  // Mobile tab state: "live" or "feed"
  const [mobileTab, setMobileTab] = React.useState<"live" | "moments">("live");

  return (
    <div className="space-y-8">
      {/* Mobile Tab Switcher (Visible only on small screens) */}
      <div className="flex md:hidden rounded-full bg-white/[0.04] border border-border p-1 gap-1">
        <button
          type="button"
          onClick={() => setMobileTab("live")}
          className={`flex-1 py-1.5 text-xs rounded-full flex items-center justify-center gap-1.5 transition-all active:scale-[0.96] ${
            mobileTab === "live"
              ? "bg-white text-neutral-950 font-semibold shadow-sm"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Radio className="h-3.5 w-3.5" />
          <span>Live ({liveStreamers.length})</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("moments")}
          className={`flex-1 py-1.5 text-xs rounded-full flex items-center justify-center gap-1.5 transition-all active:scale-[0.96] ${
            mobileTab === "moments"
              ? "bg-white text-neutral-950 font-semibold shadow-sm"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Moments ({moments.length})</span>
        </button>
      </div>

      {/* Main Grid View */}
      {/* On desktop: Live Streamers on top, Moment feed below */}
      {/* On mobile: Tabbed view for thumb ergonomics */}
      <div className="space-y-8">
        <div className={`md:block ${mobileTab === "live" ? "block" : "hidden"}`}>
          <LiveGrid
            liveStreamers={liveStreamers}
            offlineStreamers={offlineStreamers}
            sparklines={sparklines}
            isLoading={isLoading}
            onClip={clipNow}
          />
        </div>

        <div className={`md:block pt-4 md:border-t md:border-border/60 ${mobileTab === "moments" ? "block" : "hidden"}`}>
          <MomentFeed
            moments={moments}
            streamers={streamers}
            isLoading={isLoading}
            onUpdateStatus={updateMomentStatus}
          />
        </div>
      </div>
    </div>
  );
}
