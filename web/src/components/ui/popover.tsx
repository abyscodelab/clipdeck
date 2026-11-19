"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface PopoverContextValue {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

const PopoverContext = React.createContext<PopoverContextValue | null>(null);

export function Popover({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  return (
    <PopoverContext.Provider value={{ open, setOpen }}>
      <div ref={containerRef} className="relative inline-block">
        {children}
      </div>
    </PopoverContext.Provider>
  );
}

export function PopoverTrigger({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(PopoverContext);
  return (
    <button
      type="button"
      onClick={() => ctx?.setOpen((prev) => !prev)}
      className={className}
      {...props}
    >
      {children}
    </button>
  );
}

export function PopoverContent({
  className,
  align = "center",
  children,
  ...props
}: {
  align?: "left" | "right" | "center";
} & React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(PopoverContext);
  if (!ctx?.open) return null;

  const alignStyles = {
    left: "left-0",
    right: "right-0",
    center: "left-1/2 -translate-x-1/2",
  };

  return (
    <div
      className={cn(
        "absolute z-50 mt-2 w-72 rounded-xl border border-border bg-surface p-4 shadow-xl outline-none animate-in fade-in-50 zoom-in-95",
        alignStyles[align],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
