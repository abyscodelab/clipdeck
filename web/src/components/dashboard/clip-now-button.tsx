"use client";

import * as React from "react";
import { Scissors, Zap, Clock } from "@/components/icons";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

interface ClipNowButtonProps {
  streamerId: number;
  streamerName: string;
  onClip: (streamerId: number, duration: number) => Promise<any>;
  className?: string;
  size?: "default" | "huge";
}

export function ClipNowButton({
  streamerId,
  streamerName,
  onClip,
  className,
  size = "default",
}: ClipNowButtonProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [selectedDuration, setSelectedDuration] = React.useState<number>(60);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const durations = [
    { label: "30s", value: 30, desc: "Quick reaction or punchline" },
    { label: "60s", value: 60, desc: "Standard highlight / round end", recommended: true },
    { label: "90s", value: 90, desc: "Extended play or conversation" },
  ];

  const handleTriggerClip = async () => {
    setIsSubmitting(true);
    try {
      await onClip(streamerId, selectedDuration);
      setIsOpen(false);
    } catch {
      // toast is handled in parent hook
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="default"
        size={size === "huge" ? "huge" : "default"}
        onClick={() => setIsOpen(true)}
        className={`w-full gap-2 font-semibold bg-white hover:bg-neutral-200 text-neutral-950 shadow-sm rounded-xl touch-manipulation active:scale-[0.96] ${className}`}
      >
        <Scissors className={size === "huge" ? "h-5 w-5" : "h-3.5 w-3.5"} />
        <span>Clip Buffer</span>
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md bg-[#161616] border-border rounded-2xl">
          <DialogHeader>
            <div className="flex items-center gap-2 text-neutral-400 mb-1">
              <Zap className="h-4 w-4 fill-white text-white" />
              <span className="text-xs font-medium uppercase tracking-wider">
                Instant Clip Buffer
              </span>
            </div>
            <DialogTitle className="text-white">Clip {streamerName}</DialogTitle>
            <DialogDescription className="text-neutral-400 text-xs">
              Extract the last N seconds from the active DVR ring buffer immediately.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 my-2">
            <label className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
              Select Capture Window
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              {durations.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => setSelectedDuration(d.value)}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all text-center active:scale-[0.96] ${
                    selectedDuration === d.value
                      ? "border-white/30 bg-white/10 text-white font-semibold ring-1 ring-white/20"
                      : "border-border bg-white/[0.02] hover:bg-white/[0.04] text-neutral-300"
                  }`}
                >
                  <Clock className="h-3.5 w-3.5 mb-1 text-neutral-400" />
                  <span className="text-sm font-bold">{d.label}</span>
                  {d.recommended && (
                    <span className="text-[10px] text-neutral-400 font-medium mt-0.5">
                      Rec
                    </span>
                  )}
                </button>
              ))}
            </div>

            <p className="text-xs text-neutral-500 mt-2 text-center">
              Target: Last {selectedDuration} seconds up to current moment
            </p>
          </div>

          <DialogFooter className="mt-4 sm:space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsOpen(false)}
              disabled={isSubmitting}
              className="rounded-xl"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              isLoading={isSubmitting}
              onClick={handleTriggerClip}
              className="bg-white hover:bg-neutral-200 text-neutral-950 font-semibold rounded-xl"
            >
              Confirm Clip ({selectedDuration}s)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
