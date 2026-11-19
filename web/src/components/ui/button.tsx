import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "live";
  size?: "default" | "sm" | "lg" | "icon" | "huge";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", isLoading, children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/20 disabled:pointer-events-none disabled:opacity-40 select-none active:scale-[0.96]";

    const variantStyles = {
      default: "bg-white hover:bg-neutral-200 text-neutral-950 font-semibold shadow-sm",
      secondary: "bg-surface-hover hover:bg-surface-raised text-white border border-border",
      outline: "border border-border bg-transparent hover:bg-surface-hover text-neutral-200",
      ghost: "hover:bg-surface-hover text-muted-foreground hover:text-white",
      destructive: "bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30",
      link: "text-white underline-offset-4 hover:underline p-0 h-auto active:scale-100",
      live: "bg-emerald-500 hover:bg-emerald-600 text-white font-semibold shadow-sm shadow-emerald-950/40",
    };

    const sizeStyles = {
      sm: "h-8 px-3 rounded-lg text-xs gap-1.5",
      default: "h-9 px-3.5 py-1.5 rounded-xl text-xs sm:text-sm gap-2",
      lg: "h-11 px-5 rounded-xl text-sm font-semibold gap-2",
      icon: "h-9 w-9 rounded-xl p-0",
      huge: "h-12 px-6 rounded-xl text-base font-semibold gap-2.5",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5 text-current shrink-0"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
