"use client";

import * as React from "react";
import { ListTodo, RefreshCw } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { JobList } from "@/components/jobs/job-list";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useSSE } from "@/hooks/use-sse";
import { useToast } from "@/components/ui/toast";
import type { Job, JobUpdateEvent } from "@/lib/types";

export default function JobsPage() {
  const { toast } = useToast();
  const { subscribe } = useSSE();

  const [queueFilter, setQueueFilter] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<string>("");

  const {
    data: jobs = [],
    isLoading,
    mutate,
    setData: setJobsData,
  } = useApi<Job[]>(
    () =>
      api.jobs.list({
        queue: queueFilter || undefined,
        status: statusFilter || undefined,
        limit: 50,
      }),
    [queueFilter, statusFilter],
    { refreshInterval: 5000 } // Auto-poll every 5s as fallback
  );

  // Subscribe to real-time job updates via SSE
  React.useEffect(() => {
    const unsub = subscribe("job_update", (data: JobUpdateEvent) => {
      setJobsData((prev = []) => {
        const index = prev.findIndex((j) => j.id === data.job.id);
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = data.job;
          return updated;
        } else {
          return [data.job, ...prev];
        }
      });
    });

    return () => {
      unsub();
    };
  }, [subscribe, setJobsData]);

  const handleRetryJob = async (id: number) => {
    try {
      await api.jobs.retry(id);
      toast({
        title: "Job Scheduled for Retry",
        message: `Job #${id} added back to queue.`,
        type: "success",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Retry Failed",
        message: err.message || "Could not retry job",
        type: "error",
      });
    }
  };

  const handleCancelJob = async (id: number) => {
    try {
      await api.jobs.cancel(id);
      toast({
        title: "Job Cancelled",
        message: `Job #${id} was cancelled.`,
        type: "info",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Cancel Failed",
        message: err.message || "Could not cancel job",
        type: "error",
      });
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <ListTodo className="h-6 w-6 text-accent" />
              Worker Job Queue
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Monitor FFmpeg render jobs, streamlink ingest workers, and background clipping tasks.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => mutate()}
            className="gap-1.5 text-xs h-9"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh Queue
          </Button>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl border border-border bg-surface">
          <div className="w-full sm:w-44">
            <Select
              value={queueFilter}
              onChange={(e) => setQueueFilter(e.target.value)}
            >
              <option value="">All Queues</option>
              <option value="ingest">Ingest Queue</option>
              <option value="detect">Detect Queue</option>
              <option value="render">Render Queue</option>
              <option value="publish">Publish Queue</option>
            </Select>
          </div>

          <div className="w-full sm:w-44">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </Select>
          </div>
        </div>

        {/* Job List Table */}
        {isLoading && jobs.length === 0 ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        ) : (
          <JobList
            jobs={jobs}
            onRetry={handleRetryJob}
            onCancel={handleCancelJob}
          />
        )}
      </div>
    </AppShell>
  );
}
