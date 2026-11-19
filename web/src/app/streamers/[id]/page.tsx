"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Radio, Sparkles, Clock, Calendar, Edit3, History } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { StreamerForm } from "@/components/streamers/streamer-form";
import { MomentCard } from "@/components/dashboard/moment-card";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate, formatDuration } from "@/lib/utils";
import type { Streamer, StreamerCreate, Moment, StreamSession } from "@/lib/types";

export default function StreamerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const streamerId = Number(params?.id);

  const [isUpdating, setIsUpdating] = React.useState(false);

  // Fetch Streamer Details
  const {
    data: streamer,
    isLoading: isStreamerLoading,
    mutate: mutateStreamer,
  } = useApi<Streamer>(() => api.streamers.get(streamerId), [streamerId]);

  // Fetch Moments for this streamer
  const {
    data: moments = [],
    isLoading: isMomentsLoading,
    mutate: mutateMoments,
  } = useApi<Moment[]>(
    () => api.moments.list({ streamer_id: streamerId, limit: 50 }),
    [streamerId]
  );

  // Fetch Past Stream Sessions
  const {
    data: sessions = [],
    isLoading: isSessionsLoading,
  } = useApi<StreamSession[]>(
    () => api.sessions.list(streamerId),
    [streamerId]
  );

  const handleUpdate = async (formData: StreamerCreate) => {
    setIsUpdating(true);
    try {
      await api.streamers.update(streamerId, formData);
      toast({
        title: "Streamer Updated",
        message: "Channel configuration saved successfully.",
        type: "success",
      });
      mutateStreamer();
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Failed to save streamer changes",
        type: "error",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateMomentStatus = async (
    momentId: number,
    status: "approved" | "rejected"
  ) => {
    try {
      await api.moments.updateStatus(momentId, status);
      toast({
        title: "Moment Updated",
        message: `Marked as ${status}`,
        type: "success",
      });
      mutateMoments();
    } catch (err: any) {
      toast({
        title: "Action Failed",
        message: err.message || "Could not update moment status",
        type: "error",
      });
    }
  };

  if (isStreamerLoading) {
    return (
      <AppShell>
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (!streamer) {
    return (
      <AppShell>
        <div className="p-8 text-center text-muted-foreground">
          Streamer not found.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <Link href="/streamers">
            <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-white">
              <ArrowLeft className="h-4 w-4" />
              All Streamers
            </Button>
          </Link>

          <div className="flex items-center gap-2">
            <Badge
              variant={streamer.is_live ? "live" : "secondary"}
              className="font-bold uppercase text-[10px]"
            >
              {streamer.is_live ? "Live Now" : "Offline"}
            </Badge>
          </div>
        </div>

        {/* Streamer Header Banner */}
        <div className="p-6 rounded-2xl border border-border bg-surface flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                {streamer.name}
              </h1>
              <Badge variant="outline" className="text-xs uppercase font-mono">
                {streamer.platform}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {streamer.url || `Platform ID: ${streamer.platform_id || "Auto-detected"}`}
              {streamer.niche && ` • ${streamer.niche}`}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-muted-foreground">Recorded Moments</div>
              <div className="text-xl font-bold text-white font-mono">{moments.length}</div>
            </div>
            <div className="text-right pl-3 border-l border-border">
              <div className="text-xs text-muted-foreground">Sessions</div>
              <div className="text-xl font-bold text-white font-mono">{sessions.length}</div>
            </div>
          </div>
        </div>

        {/* Tabbed Sections: Edit Form, Moments, Sessions */}
        <Tabs defaultValue="moments">
          <TabsList className="grid grid-cols-3 w-full sm:w-96">
            <TabsTrigger value="moments" className="gap-1.5 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-accent" />
              Moments ({moments.length})
            </TabsTrigger>
            <TabsTrigger value="edit" className="gap-1.5 text-xs">
              <Edit3 className="h-3.5 w-3.5" />
              Configuration
            </TabsTrigger>
            <TabsTrigger value="sessions" className="gap-1.5 text-xs">
              <History className="h-3.5 w-3.5" />
              Sessions ({sessions.length})
            </TabsTrigger>
          </TabsList>

          {/* Moments Tab */}
          <TabsContent value="moments" className="space-y-4 pt-2">
            {isMomentsLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : moments.length === 0 ? (
              <Card className="border-dashed p-8 text-center text-muted-foreground">
                No moments recorded for {streamer.name} yet.
              </Card>
            ) : (
              <div className="space-y-3">
                {moments.map((m) => (
                  <MomentCard
                    key={m.id}
                    moment={m}
                    streamerName={streamer.name}
                    onApprove={(id) => handleUpdateMomentStatus(id, "approved")}
                    onReject={(id) => handleUpdateMomentStatus(id, "rejected")}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          {/* Edit Configuration Tab */}
          <TabsContent value="edit" className="pt-2">
            <Card className="border-border bg-surface p-6">
              <StreamerForm
                initialData={streamer}
                onSubmit={handleUpdate}
                isLoading={isUpdating}
              />
            </Card>
          </TabsContent>

          {/* Sessions Tab */}
          <TabsContent value="sessions" className="pt-2">
            <Card className="border-border bg-surface">
              <CardHeader>
                <CardTitle className="text-base">Stream Sessions History</CardTitle>
                <CardDescription>
                  Live stream broadcast events and chat velocity statistics recorded by worker engine.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {sessions.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted-foreground">
                    No stream sessions recorded yet.
                  </div>
                ) : (
                  <div className="divide-y divide-border/50">
                    {sessions.map((s) => (
                      <div key={s.id} className="py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Radio className="h-4 w-4 text-accent" />
                          <div>
                            <div className="font-semibold text-white text-sm">
                              Session #{s.id}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Started: {formatDate(s.started_at)}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <Badge variant={s.status === "live" ? "live" : "secondary"} className="uppercase text-[10px]">
                            {s.status}
                          </Badge>
                          {s.viewer_count && (
                            <span className="text-xs font-mono text-muted-foreground">
                              {s.viewer_count} viewers
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
