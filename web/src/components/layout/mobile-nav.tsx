"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Film,
  Image as ImageIcon,
  Sparkles,
  BookOpen,
  MoreHorizontal,
  DollarSign,
  Radio,
  Sliders,
  ListTodo,
  Settings,
  Activity,
} from "@/components/icons";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

const primaryMobileNav = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Clips", href: "/clips", icon: Film },
  { label: "Moments", href: "/moments", icon: Sparkles },
  { label: "Playbooks", href: "/playbooks", icon: BookOpen },
];

export function MobileNav() {
  const pathname = usePathname();

  const isMoreActive =
    pathname.startsWith("/thumbnails") ||
    pathname.startsWith("/costs") ||
    pathname.startsWith("/streamers") ||
    pathname.startsWith("/templates") ||
    pathname.startsWith("/jobs") ||
    pathname.startsWith("/settings") ||
    pathname.startsWith("/health");

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#111111]/95 backdrop-blur-lg border-t border-border px-1 py-1 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
      <div className="flex items-center justify-around h-13">
        {primaryMobileNav.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center flex-1 h-full py-1 text-xs transition-colors relative touch-manipulation",
                isActive
                  ? "text-white font-semibold"
                  : "text-neutral-400 hover:text-white"
              )}
            >
              {isActive && (
                <span className="absolute top-0 w-6 h-0.5 bg-white rounded-full -translate-y-1" />
              )}
              <Icon
                className={cn(
                  "h-4 w-4 mb-0.5 transition-transform",
                  isActive ? "text-white scale-105" : "text-neutral-400"
                )}
              />
              <span className="text-[10px] leading-tight">{item.label}</span>
            </Link>
          );
        })}

        {/* More Menu Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger
            className={cn(
              "flex flex-col items-center justify-center flex-1 h-full py-1 text-xs transition-colors relative touch-manipulation",
              isMoreActive ? "text-white font-semibold" : "text-neutral-400 hover:text-white"
            )}
          >
            {isMoreActive && (
              <span className="absolute top-0 w-6 h-0.5 bg-white rounded-full -translate-y-1" />
            )}
            <MoreHorizontal className="h-4 w-4 mb-0.5 text-neutral-400" />
            <span className="text-[10px] leading-tight">More</span>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="right" className="w-48 mb-2 bg-[#161616] border-border">
            <Link href="/thumbnails">
              <DropdownMenuItem className="gap-2 text-xs">
                <ImageIcon className="h-4 w-4 text-neutral-300" />
                <span>Thumbnails (GTA)</span>
              </DropdownMenuItem>
            </Link>
            <Link href="/costs">
              <DropdownMenuItem className="gap-2 text-xs">
                <DollarSign className="h-4 w-4 text-emerald-400" />
                <span>Cost Ledger</span>
              </DropdownMenuItem>
            </Link>
            <Link href="/streamers">
              <DropdownMenuItem className="gap-2 text-xs">
                <Radio className="h-4 w-4 text-neutral-300" />
                <span>Streamers</span>
              </DropdownMenuItem>
            </Link>
            <Link href="/templates">
              <DropdownMenuItem className="gap-2 text-xs">
                <Sliders className="h-4 w-4 text-neutral-300" />
                <span>AI Templates</span>
              </DropdownMenuItem>
            </Link>
            <Link href="/jobs">
              <DropdownMenuItem className="gap-2 text-xs">
                <ListTodo className="h-4 w-4 text-neutral-300" />
                <span>Worker Jobs</span>
              </DropdownMenuItem>
            </Link>
            <DropdownMenuSeparator className="bg-border" />
            <Link href="/settings">
              <DropdownMenuItem className="gap-2 text-xs">
                <Settings className="h-4 w-4 text-neutral-400" />
                <span>Settings</span>
              </DropdownMenuItem>
            </Link>
            <Link href="/health">
              <DropdownMenuItem className="gap-2 text-xs">
                <Activity className="h-4 w-4 text-neutral-400" />
                <span>Health</span>
              </DropdownMenuItem>
            </Link>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  );
}
