"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { MomentDetail } from "@/components/moments/moment-detail";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import type { Moment, Streamer, MomentStatus } from "@/lib/types";

export default function MomentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const momentId = Number(params?.id);

  const [isUpdating, setIsUpdating] = React.useState(false);

  // Fetch Moment details
  const {
    data: moment,
    isLoading: isMomentLoading,
    mutate: mutateMoment,
  } = useApi<Moment>(() => api.moments.get(momentId), [momentId]);

  // Fetch associated streamer if moment is loaded
  const { data: streamer } = useApi<Streamer>(
    () => api.streamers.get(moment!.streamer_id),
    [moment?.streamer_id],
    { enabled: !!moment?.streamer_id }
  );

  const handleUpdateStatus = async (status: MomentStatus) => {
    setIsUpdating(true);
    try {
      await api.moments.updateStatus(momentId, status);
      toast({
        title: "Moment Updated",
        message: `Status changed to ${status}.`,
        type: status === "approved" ? "success" : "info",
      });
      mutateMoment();
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Could not update status",
        type: "error",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleRunAiEdit = async () => {
    try {
      const res = await api.moments.runAiEdit(momentId);
      toast({
        title: "AI Editing Queued",
        message: `Job #${res.job_id || "running"} dispatched. Scoring & 9:16 EDL generation underway.`,
        type: "success",
      });
      mutateMoment();
      if (res.clip_id) {
        router.push(`/clips/${res.clip_id}`);
      }
    } catch (err: any) {
      toast({
        title: "AI Edit Failed",
        message: err.message || "Could not queue AI edit pipeline",
        type: "error",
      });
      throw err;
    }
  };

  if (isMomentLoading) {
    return (
      <AppShell>
        <div className="space-y-4 max-w-5xl mx-auto">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="aspect-video w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (!moment) {
    return (
      <AppShell>
        <div className="p-8 text-center text-muted-foreground">
          Moment not found.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <MomentDetail
        moment={moment}
        streamer={streamer}
        onUpdateStatus={handleUpdateStatus}
        onRunAiEdit={handleRunAiEdit}
        isUpdating={isUpdating}
      />
    </AppShell>
  );
}
