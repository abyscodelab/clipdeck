"use client";

import * as React from "react";
import {
  ListTodo,
  RefreshCw,
  XCircle,
  ChevronDown,
  ChevronUp,
  Terminal,
  AlertCircle,
  CheckCircle2,
} from "@/components/icons";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { formatRelativeTime, formatDuration } from "@/lib/utils";
import type { Job } from "@/lib/types";

interface JobListProps {
  jobs: Job[];
  onRetry: (id: number) => Promise<any>;
  onCancel: (id: number) => Promise<any>;
}

export function JobList({ jobs, onRetry, onCancel }: JobListProps) {
  const [expandedId, setExpandedId] = React.useState<number | null>(null);
  const [actionLoadingId, setActionLoadingId] = React.useState<number | null>(null);

  const toggleExpand = (id: number) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const handleAction = async (id: number, action: "retry" | "cancel") => {
    setActionLoadingId(id);
    try {
      if (action === "retry") {
        await onRetry(id);
      } else {
        await onCancel(id);
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Queue / Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Progress</TableHead>
            <TableHead>Target</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                No active or recent jobs found in the queue.
              </TableCell>
            </TableRow>
          ) : (
            jobs.map((job) => {
              const isExpanded = expandedId === job.id;
              const isActionLoading = actionLoadingId === job.id;

              const statusVariant = {
                pending: "secondary",
                running: "warning",
                completed: "success",
                failed: "destructive",
                cancelled: "secondary",
              }[job.status] as any;

              return (
                <React.Fragment key={job.id}>
                  <TableRow
                    className="cursor-pointer hover:bg-surface-hover/60"
                    onClick={() => toggleExpand(job.id)}
                  >
                    {/* Queue & Type */}
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-semibold text-white capitalize text-sm">
                          {job.job_type.replace(/_/g, " ")}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono uppercase">
                          Queue: {job.queue}
                        </span>
                      </div>
                    </TableCell>

                    {/* Status */}
                    <TableCell>
                      <Badge variant={statusVariant} className="text-[10px] uppercase font-bold py-0.5">
                        {job.status}
                      </Badge>
                    </TableCell>

                    {/* Progress Bar */}
                    <TableCell className="w-40">
                      <div className="space-y-1">
                        <div className="flex justify-between text-[11px] font-mono text-muted-foreground">
                          <span>{Math.round(job.progress)}%</span>
                          {job.retries > 0 && <span>Retry #{job.retries}</span>}
                        </div>
                        <Progress
                          value={job.progress}
                          indicatorClassName={
                            job.status === "failed"
                              ? "bg-rose-500"
                              : job.status === "completed"
                              ? "bg-emerald-500"
                              : "bg-accent"
                          }
                        />
                      </div>
                    </TableCell>

                    {/* Target Streamer / Moment */}
                    <TableCell>
                      <div className="text-xs font-mono text-gray-300">
                        {job.streamer_id && <div>Streamer #{job.streamer_id}</div>}
                        {job.moment_id && <div>Moment #{job.moment_id}</div>}
                        {!job.streamer_id && !job.moment_id && <div>System</div>}
                      </div>
                    </TableCell>

                    {/* Timestamp */}
                    <TableCell className="text-xs text-muted-foreground">
                      {formatRelativeTime(job.created_at)}
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        {job.status === "failed" && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isActionLoading}
                            onClick={() => handleAction(job.id, "retry")}
                            className="h-8 text-xs gap-1 border-accent/40 text-accent hover:bg-accent/10"
                          >
                            <RefreshCw className={`h-3 w-3 ${isActionLoading ? "animate-spin" : ""}`} />
                            Retry
                          </Button>
                        )}

                        {job.status === "running" && (
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={isActionLoading}
                            onClick={() => handleAction(job.id, "cancel")}
                            className="h-8 text-xs gap-1"
                          >
                            <XCircle className="h-3 w-3" />
                            Cancel
                          </Button>
                        )}

                        <button
                          type="button"
                          onClick={() => toggleExpand(job.id)}
                          className="p-1.5 text-muted-foreground hover:text-white rounded-lg hover:bg-surface-hover transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>

                  {/* Expanded Row for Logs / Details */}
                  {isExpanded && (
                    <TableRow className="bg-background/80 hover:bg-background/80">
                      <TableCell colSpan={6} className="p-4">
                        <div className="space-y-3">
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span className="flex items-center gap-1.5 font-semibold text-gray-200">
                              <Terminal className="h-4 w-4 text-accent" />
                              Job Execution Log (Job ID #{job.id})
                            </span>
                            {job.error && (
                              <span className="text-rose-400 font-medium flex items-center gap-1">
                                <AlertCircle className="h-3.5 w-3.5" />
                                Error: {job.error}
                              </span>
                            )}
                          </div>

                          {/* Raw Log Output Terminal */}
                          <pre className="p-3 rounded-lg bg-black/90 border border-border font-mono text-[11px] text-gray-300 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                            {job.log || (job.error ? job.error : "No output logs captured for this job.")}
                          </pre>

                          {/* Params and Result payload if available */}
                          {job.params && (
                            <div className="text-[11px] font-mono text-muted-foreground">
                              <span className="text-gray-400">Params: </span>
                              {JSON.stringify(job.params)}
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
