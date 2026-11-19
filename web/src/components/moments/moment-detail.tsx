"use client";

import * as React from "react";
import Link from "next/link";
import {
  Flame,
  Clock,
  Radio,
  CheckCircle2,
  XCircle,
  Download,
  Share2,
  ArrowLeft,
  MessageSquare,
  BarChart3,
  Sparkles,
  Scissors,
  AlertTriangle,
  Film,
  Zap,
} from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDuration, formatDate, getHypeColor } from "@/lib/utils";
import type { Moment, Streamer, MomentStatus, MomentScoreResult, EditDecisionList } from "@/lib/types";

interface MomentDetailProps {
  moment: Moment;
  streamer?: Streamer;
  onUpdateStatus: (status: MomentStatus) => Promise<void>;
  onRunAiEdit?: () => Promise<any>;
  isUpdating?: boolean;
}

export function MomentDetail({
  moment,
  streamer,
  onUpdateStatus,
  onRunAiEdit,
  isUpdating = false,
}: MomentDetailProps) {
  const hype = getHypeColor(moment.hype_score);
  const [isRunningEdit, setIsRunningEdit] = React.useState(false);

  const aiScore: MomentScoreResult | null = moment.ai_score || null;
  const edl: EditDecisionList | null = moment.latest_edl || null;

  const handleRunAiEdit = async () => {
    if (!onRunAiEdit) return;
    setIsRunningEdit(true);
    try {
      await onRunAiEdit();
    } finally {
      setIsRunningEdit(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Bar Navigation */}
      <div className="flex items-center justify-between">
        <Link href="/moments">
          <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-white">
            <ArrowLeft className="h-4 w-4" />
            Back to Moments
          </Button>
        </Link>

        {/* Status Badge & AI Edit Trigger */}
        <div className="flex items-center gap-2">
          {onRunAiEdit && (
            <Button
              size="sm"
              disabled={isRunningEdit}
              isLoading={isRunningEdit}
              onClick={handleRunAiEdit}
              className="gap-1.5 font-bold bg-gradient-to-r from-accent to-purple-700 hover:from-accent-hover hover:to-purple-800 text-white shadow-md shadow-accent/20"
            >
              <Zap className="h-3.5 w-3.5 fill-current" />
              Run AI Edit (9:16)
            </Button>
          )}

          <Badge
            variant={
              moment.status === "approved"
                ? "success"
                : moment.status === "rejected"
                ? "destructive"
                : "warning"
            }
            className="uppercase font-bold tracking-wider px-2.5 py-1 text-xs"
          >
            {moment.status}
          </Badge>
        </div>
      </div>

      {/* Main Grid: Video Player + Metadata */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video Player Column */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="overflow-hidden border-border bg-black aspect-video flex items-center justify-center relative rounded-2xl">
            {moment.file_path ? (
              <video
                controls
                autoPlay
                className="w-full h-full object-contain"
                poster={moment.thumbnail_path || undefined}
              >
                <source src={moment.file_path} type="video/mp4" />
                Your browser does not support HTML video.
              </video>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                <Flame className={`h-12 w-12 ${hype.text} mb-3`} />
                <h4 className="text-base font-semibold text-white">Clip Rendering / Buffer Ingest</h4>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                  {moment.status === "clipping"
                    ? "Video rendering job is currently processing this moment from the DVR buffer."
                    : "No video file available yet."}
                </p>
              </div>
            )}
          </Card>

          {/* Quick Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl border border-border bg-surface">
            <div className="flex items-center gap-2">
              <Button
                variant={moment.status === "approved" ? "live" : "outline"}
                disabled={isUpdating}
                onClick={() => onUpdateStatus("approved")}
                className="gap-1.5 font-semibold text-xs h-9"
              >
                <CheckCircle2 className="h-4 w-4" />
                Approve Clip
              </Button>

              <Button
                variant={moment.status === "rejected" ? "destructive" : "ghost"}
                disabled={isUpdating}
                onClick={() => onUpdateStatus("rejected")}
                className="gap-1.5 text-xs h-9 hover:bg-rose-500/15 hover:text-rose-400"
              >
                <XCircle className="h-4 w-4" />
                Reject
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {moment.clips && moment.clips.length > 0 && (
                <Link href={`/clips/${moment.clips[0].id}`}>
                  <Button variant="secondary" size="sm" className="gap-1.5 text-xs h-9 text-accent-light">
                    <Film className="h-3.5 w-3.5" />
                    View 9:16 Render
                  </Button>
                </Link>
              )}

              {moment.file_path && (
                <a href={moment.file_path} download={`moment_${moment.id}.mp4`}>
                  <Button variant="outline" size="sm" className="gap-1.5 text-xs h-9">
                    <Download className="h-3.5 w-3.5" />
                    Download MP4
                  </Button>
                </a>
              )}
            </div>
          </div>

          {/* AI Scoring & Playbook Virality Analysis Card */}
          {aiScore && (
            <Card className="border-border bg-surface">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-accent" />
                    AI Virality Score & Playbook Evaluation
                  </CardTitle>
                  <Badge variant={aiScore.keep ? "success" : "destructive"}>
                    {aiScore.keep ? "KEEP (Recommended)" : "DISCARD"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3.5 text-xs">
                <div className="flex items-center justify-between p-3 rounded-xl bg-background border border-border">
                  <span className="font-semibold text-gray-300">Virality Potential</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-black text-accent-light font-mono">
                      {aiScore.virality_score}
                    </span>
                    <span className="text-muted-foreground font-bold">/100</span>
                  </div>
                </div>

                {aiScore.category && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Category:</span>
                    <Badge variant="outline" className="capitalize text-xs font-semibold">
                      {aiScore.category}
                    </Badge>
                  </div>
                )}

                {aiScore.reason && (
                  <div className="space-y-1">
                    <span className="text-muted-foreground font-semibold">AI Reasoning:</span>
                    <p className="text-gray-200 bg-background/60 p-2.5 rounded-lg leading-relaxed">
                      {aiScore.reason}
                    </p>
                  </div>
                )}

                {/* Rules Applied */}
                {aiScore.playbook_rules_applied && aiScore.playbook_rules_applied.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Playbook Rules Applied:
                    </span>
                    <ul className="list-disc list-inside text-gray-300 pl-1 space-y-0.5">
                      {aiScore.playbook_rules_applied.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Rule Violations */}
                {aiScore.rule_violations && aiScore.rule_violations.length > 0 && (
                  <div className="space-y-1 pt-1 border-t border-border/50">
                    <span className="text-rose-400 font-semibold flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Brand-Safety Violations:
                    </span>
                    <ul className="list-disc list-inside text-rose-300 pl-1 space-y-0.5">
                      {aiScore.rule_violations.map((v, idx) => (
                        <li key={idx}>{v}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Generated EDL Preview */}
          {edl && (
            <Card className="border-border bg-surface">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Scissors className="h-4 w-4 text-accent" />
                  Generated Edit Decision List (EDL)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2 rounded-lg bg-background border border-border">
                    <span className="text-[10px] text-muted-foreground uppercase">Trim Range</span>
                    <div className="font-mono font-bold text-white mt-0.5">
                      {edl.trim_in}s &rarr; {edl.trim_out}s
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-background border border-border">
                    <span className="text-[10px] text-muted-foreground uppercase">Layout Mode</span>
                    <div className="font-mono font-bold text-accent capitalize mt-0.5">
                      {edl.layout}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-background border border-border">
                    <span className="text-[10px] text-muted-foreground uppercase">Dead Air Cuts</span>
                    <div className="font-mono font-bold text-white mt-0.5">
                      {edl.cuts?.length || 0} cuts
                    </div>
                  </div>
                </div>

                {edl.hook_text && (
                  <div className="p-2.5 rounded-lg bg-accent/10 border border-accent/30 text-accent-light">
                    <span className="font-bold text-[10px] uppercase block mb-0.5">Hook Text:</span>
                    &quot;{edl.hook_text}&quot;
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar Metadata Column */}
        <div className="space-y-4">
          <Card className="border-border bg-surface">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Moment Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3.5 text-xs">
              {/* Streamer */}
              <div className="flex justify-between items-center py-1.5 border-b border-border/50">
                <span className="text-muted-foreground">Streamer</span>
                <span className="font-bold text-white text-sm">
                  {streamer?.name || `Streamer #${moment.streamer_id}`}
                </span>
              </div>

              {/* Hype Score */}
              <div className="flex justify-between items-center py-1.5 border-b border-border/50">
                <span className="text-muted-foreground">Hype Score</span>
                <span className={`font-black text-lg ${hype.text}`}>
                  {Math.round(moment.hype_score)} / 100
                </span>
              </div>

              {/* Detected At */}
              <div className="flex justify-between items-center py-1.5 border-b border-border/50">
                <span className="text-muted-foreground">Detected At</span>
                <span className="font-mono text-gray-200">
                  {formatDate(moment.detected_at)}
                </span>
              </div>

              {/* Duration */}
              <div className="flex justify-between items-center py-1.5 border-b border-border/50">
                <span className="text-muted-foreground">Clip Duration</span>
                <span className="font-mono text-gray-200">
                  {formatDuration(moment.clip_duration || 60)}
                </span>
              </div>

              {/* Trigger */}
              <div className="flex justify-between items-center py-1.5">
                <span className="text-muted-foreground">Trigger Mode</span>
                <Badge variant="secondary" className="capitalize">
                  {moment.trigger_type}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Chat Signal Breakdown Card */}
          <Card className="border-border bg-surface">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-accent" />
                Chat Signals
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              {moment.chat_data ? (
                <div className="space-y-2">
                  {Object.entries(moment.chat_data).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex justify-between items-center py-1 border-b border-border/40">
                      <span className="capitalize text-muted-foreground">
                        {key.replace(/_/g, " ")}
                      </span>
                      <span className="font-mono font-semibold text-white">
                        {typeof val === "number" ? val.toFixed(2) : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-xs">
                  Raw chat velocity and emote burst snapshot captured at trigger timestamp.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
