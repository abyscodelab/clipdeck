"use client";

import * as React from "react";
import { Terminal, Copy, Check } from "@/components/icons";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Job } from "@/lib/types";

interface JobDetailProps {
  job: Job | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function JobDetail({ job, open, onOpenChange }: JobDetailProps) {
  const [copied, setCopied] = React.useState(false);

  if (!job) return null;

  const handleCopyLogs = () => {
    if (job.log) {
      navigator.clipboard.writeText(job.log);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs uppercase">
              {job.queue}
            </Badge>
            <Badge
              variant={
                job.status === "completed"
                  ? "success"
                  : job.status === "failed"
                  ? "destructive"
                  : "warning"
              }
              className="text-xs uppercase font-bold"
            >
              {job.status}
            </Badge>
          </div>
          <DialogTitle className="mt-1">
            Job #{job.id}: {job.job_type}
          </DialogTitle>
          <DialogDescription>
            Created {new Date(job.created_at).toLocaleString()}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 my-2">
          {/* Execution Log */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-accent" />
                Raw Execution Log
              </span>
              {job.log && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyLogs}
                  className="h-7 text-xs gap-1 text-muted-foreground hover:text-white"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              )}
            </div>
            <pre className="p-3 rounded-lg bg-black/90 border border-border font-mono text-xs text-gray-300 max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed">
              {job.log || job.error || "No logs recorded for this job."}
            </pre>
          </div>

          {/* Job Params */}
          {job.params && (
            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-muted-foreground">Parameters</span>
              <pre className="p-3 rounded-lg bg-surface-hover/70 border border-border font-mono text-xs text-gray-300 overflow-x-auto">
                {JSON.stringify(job.params, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {job.result && (
            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-muted-foreground">Result Payload</span>
              <pre className="p-3 rounded-lg bg-surface-hover/70 border border-border font-mono text-xs text-gray-300 overflow-x-auto">
                {JSON.stringify(job.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
