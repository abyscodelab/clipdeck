"use client";

import * as React from "react";
import { Plus, Radio } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { StreamerList } from "@/components/streamers/streamer-list";
import { StreamerForm } from "@/components/streamers/streamer-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import type { Streamer, StreamerCreate } from "@/lib/types";

export default function StreamersPage() {
  const { toast } = useToast();
  const [isAddOpen, setIsAddOpen] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const { data: streamers = [], mutate, isLoading } = useApi<Streamer[]>(
    () => api.streamers.list(),
    []
  );

  const handleCreateStreamer = async (formValues: StreamerCreate) => {
    setIsSubmitting(true);
    try {
      await api.streamers.create(formValues);
      toast({
        title: "Streamer Added",
        message: `${formValues.name} (${formValues.platform}) is now being monitored.`,
        type: "success",
      });
      setIsAddOpen(false);
      mutate();
    } catch (err: any) {
      toast({
        title: "Failed to Add Streamer",
        message: err.message || "An error occurred",
        type: "error",
      });
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleMonitor = async (streamer: Streamer) => {
    try {
      const updated = await api.streamers.update(streamer.id, {
        auto_monitor: !streamer.auto_monitor,
      });
      toast({
        title: "Auto-Monitor Updated",
        message: `${streamer.name} auto-monitor is now ${
          updated.auto_monitor ? "enabled" : "paused"
        }`,
        type: "info",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Could not update monitor setting",
        type: "error",
      });
    }
  };

  const handleDeleteStreamer = async (id: number) => {
    try {
      await api.streamers.delete(id);
      toast({
        title: "Streamer Removed",
        message: "Channel removed from monitoring list.",
        type: "success",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Delete Failed",
        message: err.message || "Could not delete streamer",
        type: "error",
      });
    }
  };

  const handleClipNow = async (streamerId: number, duration: number) => {
    return api.streamers.clipNow(streamerId, duration);
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Radio className="h-6 w-6 text-accent" />
              Streamer Management
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Configure Twitch, Kick, and YouTube channels for automated chat ingestion and moment clipping.
            </p>
          </div>

          <Button
            onClick={() => setIsAddOpen(true)}
            className="gap-2 font-bold shadow-md shadow-accent/20"
          >
            <Plus className="h-4 w-4" />
            Add Streamer
          </Button>
        </div>

        {/* Streamers Table List */}
        <StreamerList
          streamers={streamers}
          onToggleMonitor={handleToggleMonitor}
          onDelete={handleDeleteStreamer}
          onClipNow={handleClipNow}
        />

        {/* Add Streamer Modal */}
        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Monitored Channel</DialogTitle>
              <DialogDescription>
                Paste the streamer&apos;s channel link to automatically extract platform and channel ID.
              </DialogDescription>
            </DialogHeader>

            <StreamerForm
              onSubmit={handleCreateStreamer}
              onCancel={() => setIsAddOpen(false)}
              isLoading={isSubmitting}
            />
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
