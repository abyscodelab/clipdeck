"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Film,
  Image as ImageIcon,
  Radio,
  Sparkles,
  BookOpen,
  Sliders,
  DollarSign,
  ListTodo,
  Settings,
  Activity,
  LogOut,
  Flame,
  Wifi,
  WifiOff,
} from "@/components/icons";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useSSE } from "@/hooks/use-sse";

export const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Clips (9:16)", href: "/clips", icon: Film },
  { label: "Thumbnails (GTA)", href: "/thumbnails", icon: ImageIcon },
  { label: "Playbooks", href: "/playbooks", icon: BookOpen },
  { label: "Moments", href: "/moments", icon: Sparkles },
  { label: "Streamers", href: "/streamers", icon: Radio },
  { label: "AI Templates", href: "/templates", icon: Sliders },
  { label: "Cost Ledger", href: "/costs", icon: DollarSign },
  { label: "Jobs", href: "/jobs", icon: ListTodo },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "Health", href: "/health", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { connectionState } = useSSE();

  return (
    <aside className="hidden md:flex flex-col w-60 border-r border-border bg-[#111111] shrink-0 h-screen sticky top-0">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 h-14 border-b border-border">
        <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-white/10 text-white border border-white/10">
          <Flame className="h-4 w-4 fill-white" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white text-sm tracking-tight">
            ClipDeck
          </span>
          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full bg-white/[0.08] text-neutral-400 border border-white/10">
            v2.0
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-[background-color,color,transform] duration-150 group active:scale-[0.98]",
                isActive
                  ? "bg-white text-neutral-950 font-semibold shadow-sm"
                  : "text-neutral-400 hover:text-white hover:bg-white/[0.04]"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  isActive
                    ? "text-neutral-950"
                    : "text-neutral-400 group-hover:text-white"
                )}
              />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer / Status & User */}
      <div className="p-3 border-t border-border flex flex-col gap-2.5 bg-[#0D0D0D]">
        {/* SSE Status */}
        <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-border text-[11px]">
          <div className="flex items-center gap-2">
            {connectionState === "connected" ? (
              <Wifi className="h-3 w-3 text-emerald-400" />
            ) : (
              <WifiOff className="h-3 w-3 text-rose-400" />
            )}
            <span className="text-neutral-400">
              Live Feed:{" "}
              <span
                className={
                  connectionState === "connected"
                    ? "text-emerald-400 font-medium"
                    : "text-rose-400 font-medium"
                }
              >
                {connectionState}
              </span>
            </span>
          </div>
          <span className="relative flex h-1.5 w-1.5">
            {connectionState === "connected" && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            )}
            <span
              className={cn(
                "relative inline-flex rounded-full h-1.5 w-1.5",
                connectionState === "connected" ? "bg-emerald-500" : "bg-rose-500"
              )}
            />
          </span>
        </div>

        {/* User bar */}
        <div className="flex items-center justify-between pt-0.5">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="h-7 w-7 rounded-full bg-white/10 flex items-center justify-center font-semibold text-white text-[11px] border border-white/10">
              {user?.username?.slice(0, 2).toUpperCase() || "AD"}
            </div>
            <div className="flex flex-col truncate">
              <span className="text-xs font-medium text-white truncate">
                {user?.username || "Admin"}
              </span>
              <span className="text-[10px] text-neutral-500">Node Operator</span>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition-colors active:scale-[0.96]"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
