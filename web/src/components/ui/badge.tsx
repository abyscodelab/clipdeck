import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "live" | "warning" | "success" | "accent" | "twitch" | "kick" | "youtube";
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: "bg-white/[0.08] text-neutral-200 border-white/10",
    secondary: "bg-surface-hover text-muted-foreground border-border",
    destructive: "bg-rose-500/10 text-rose-300 border-rose-500/20",
    live: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/10 text-amber-300 border-amber-500/20",
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    accent: "bg-white text-neutral-950 font-semibold border-white",
    outline: "text-neutral-300 border-border bg-transparent",
    twitch: "bg-[#9146FF]/10 text-[#C4A7FF] border-[#9146FF]/20",
    kick: "bg-[#53FC18]/10 text-[#53FC18] border-[#53FC18]/20",
    youtube: "bg-[#FF0000]/10 text-[#FF6B6B] border-[#FF0000]/20",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors select-none",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}
