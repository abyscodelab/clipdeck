"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Film,
  ArrowLeft,
  Download,
  Share2,
  Copy,
  Check,
  RefreshCw,
  Scissors,
  Layers,
  Sparkles,
  DollarSign,
  Type,
  Maximize2,
  FileText,
  Image as ImageIcon,
} from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDuration, formatDate, getMediaUrl } from "@/lib/utils";
import type { Clip, Streamer, EditDecisionList } from "@/lib/types";

export default function ClipDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const clipId = Number(params?.id);

  const [isRerendering, setIsRerendering] = React.useState(false);
  const [isGeneratingThumb, setIsGeneratingThumb] = React.useState(false);

  const handleAutoThumbnail = async (thumbMode: "cinematic" | "split" = "cinematic") => {
    setIsGeneratingThumb(true);
    try {
      await api.thumbnails.autoGenerateForClip(clipId, thumbMode);
      toast({
        title: "Vertical Thumbnail Ready",
        message: `Generated 1080×1920 ${thumbMode} thumbnail for this video.`,
        type: "success",
      });
      mutateClip();
    } catch (err: any) {
      toast({
        title: "Thumbnail Failed",
        message: err.message || "Failed to generate thumbnail",
        type: "error",
      });
    } finally {
      setIsGeneratingThumb(false);
    }
  };
  const [copiedKey, setCopiedKey] = React.useState<string | null>(null);

  // Fetch Clip Details
  const {
    data: clip,
    isLoading: isClipLoading,
    mutate: mutateClip,
  } = useApi<Clip>(() => api.clips.get(clipId), [clipId]);

  // Fetch Streamer Details
  const { data: streamer } = useApi<Streamer>(
    () => api.streamers.get(clip!.streamer_id),
    [clip?.streamer_id],
    { enabled: !!clip?.streamer_id }
  );

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
    toast({
      title: "Copied to Clipboard",
      message: `${key} copied.`,
      type: "info",
    });
  };

  const handleRerender = async () => {
    setIsRerendering(true);
    try {
      const res = await api.clips.rerender(clipId, clip?.latest_edl || undefined);
      toast({
        title: "Re-render Queued",
        message: `Worker Job #${res.job_id} scheduled for 9:16 rendering.`,
        type: "success",
      });
      mutateClip();
    } catch (err: any) {
      toast({
        title: "Re-render Failed",
        message: err.message || "Failed to trigger re-render",
        type: "error",
      });
    } finally {
      setIsRerendering(false);
    }
  };

  if (isClipLoading) {
    return (
      <AppShell>
        <div className="space-y-4 max-w-5xl mx-auto">
          <Skeleton className="h-8 w-40" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="w-full aspect-[9/16] rounded-2xl" />
            <Skeleton className="h-96 w-full rounded-2xl" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!clip) {
    return (
      <AppShell>
        <div className="p-8 text-center text-muted-foreground">Clip not found.</div>
      </AppShell>
    );
  }

  const edl: EditDecisionList | null = clip.latest_edl || (clip.edit_versions?.[0]?.edl_data ?? null);

  return (
    <AppShell>
      <div className="space-y-6 max-w-6xl mx-auto">
        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Link href="/clips">
            <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-white">
              <ArrowLeft className="h-4 w-4" />
              All Vertical Clips
            </Button>
          </Link>

          <div className="flex items-center gap-2">
            <Badge
              variant={clip.status === "rendered" ? "success" : "warning"}
              className="uppercase font-bold text-xs"
            >
              {clip.status}
            </Badge>
          </div>
        </div>

        {/* Main Grid: 9:16 Video Player on Left, Controls & EDL on Right */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* 9:16 Vertical Player Column (5 cols) */}
          <div className="md:col-span-5 flex flex-col items-center">
            <div className="w-full max-w-[340px] aspect-[9/16] rounded-2xl overflow-hidden bg-black border border-border shadow-2xl relative">
              {clip.file_path ? (
                <video
                  controls
                  autoPlay
                  playsInline
                  className="w-full h-full object-cover"
                  poster={getMediaUrl(clip.thumbnail_path) || undefined}
                >
                  <source src={getMediaUrl(clip.file_path)} type="video/mp4" />
                  Your browser does not support HTML5 video.
                </video>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center text-muted-foreground">
                  <Film className="h-12 w-12 text-accent mb-3 animate-pulse" />
                  <h4 className="text-base font-bold text-white">Clip Rendering</h4>
                  <p className="text-xs text-muted-foreground mt-1">
                    Worker is stitching 1080x1920 video with blurred background and ASS subtitles.
                  </p>
                </div>
              )}
            </div>

            {/* Quick Actions Under Player */}
            <div className="w-full max-w-[340px] mt-4 flex items-center justify-between gap-2">
              {clip.file_path && (
                <a
                  href={clip.file_path}
                  download={`clipdeck_${clip.id}.mp4`}
                  className="flex-1"
                >
                  <Button variant="default" className="w-full gap-2 text-xs font-bold">
                    <Download className="h-4 w-4" />
                    Download MP4
                  </Button>
                </a>
              )}

              <Button
                variant="outline"
                disabled={isRerendering}
                onClick={handleRerender}
                className="gap-1.5 text-xs text-neutral-300"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isRerendering ? "animate-spin" : ""}`} />
                Re-render
              </Button>
            </div>

            {/* Vertical Thumbnail Card (GTA VI Style) */}
            <div className="w-full max-w-[340px] mt-4 p-4 rounded-2xl bg-[#161616] border border-border space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <ImageIcon className="h-4 w-4 text-neutral-400" />
                  Vertical Cover (1080×1920)
                </span>
                <Link href="/thumbnails" className="text-[11px] text-neutral-400 hover:text-white transition-colors">
                  Studio →
                </Link>
              </div>

              {clip.thumbnail_path ? (
                <div className="relative aspect-[9/16] w-full rounded-xl overflow-hidden bg-black border border-border">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={getMediaUrl(clip.thumbnail_path)}
                    alt="Vertical Cover"
                    className="w-full h-full object-cover outline outline-1 -outline-offset-1 outline-white/10"
                  />
                  <div className="absolute bottom-2 right-2 flex gap-1">
                    <a
                      href={getMediaUrl(clip.thumbnail_path)}
                      download={`thumb_clip_${clip.id}.jpg`}
                    >
                      <Button size="sm" variant="default" className="h-7 px-2.5 text-[11px] gap-1 font-semibold rounded-lg">
                        <Download className="h-3 w-3" />
                        Save 1080×1920
                      </Button>
                    </a>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center border border-dashed border-border rounded-xl bg-white/[0.02]">
                  <p className="text-xs text-neutral-400">No vertical cover generated yet.</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isGeneratingThumb}
                  onClick={() => handleAutoThumbnail("cinematic")}
                  className="text-[11px] gap-1 font-medium"
                >
                  <Sparkles className="h-3 w-3 text-rose-400" />
                  Cinematic Rim
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isGeneratingThumb}
                  onClick={() => handleAutoThumbnail("split")}
                  className="text-[11px] gap-1 font-medium"
                >
                  <Sparkles className="h-3 w-3 text-cyan-400" />
                  Split Wireframe
                </Button>
              </div>
            </div>
          </div>

          {/* Metadata & EDL Column (7 cols) */}
          <div className="md:col-span-7 space-y-5">
            {/* Title & Metadata Card */}
            <Card className="border-border bg-surface">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground font-semibold">
                    {streamer?.name || `Streamer #${clip.streamer_id}`}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-emerald-400 font-bold">
                      ${clip.cost_usd.toFixed(3)} USD
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      ({clip.cost_tokens.toLocaleString()} tokens)
                    </span>
                  </div>
                </div>
                <CardTitle className="text-xl font-bold mt-1 text-white">
                  {clip.title}
                </CardTitle>
                {clip.description && (
                  <CardDescription className="text-gray-300 mt-1">
                    {clip.description}
                  </CardDescription>
                )}
              </CardHeader>

              {/* Hashtag pills */}
              {clip.hashtags && clip.hashtags.length > 0 && (
                <CardContent className="pt-0 pb-4">
                  <div className="flex flex-wrap gap-1.5">
                    {clip.hashtags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-accent/15 text-accent-light border border-accent/30"
                      >
                        #{tag.replace(/^#/, "")}
                      </span>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>

            {/* Social Platform Previews */}
            <Tabs defaultValue="tiktok">
              <TabsList className="grid grid-cols-3 w-full">
                <TabsTrigger value="tiktok" className="text-xs font-semibold">
                  TikTok
                </TabsTrigger>
                <TabsTrigger value="shorts" className="text-xs font-semibold">
                  YouTube Shorts
                </TabsTrigger>
                <TabsTrigger value="reels" className="text-xs font-semibold">
                  Instagram Reels
                </TabsTrigger>
              </TabsList>

              <TabsContent value="tiktok" className="pt-2">
                <Card className="border-border bg-surface p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-200">TikTok Caption</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleCopy(
                          `${clip.title} ${clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}`,
                          "TikTok Caption"
                        )
                      }
                      className="h-7 text-xs gap-1"
                    >
                      {copiedKey === "TikTok Caption" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      Copy
                    </Button>
                  </div>
                  <p className="text-xs text-gray-300 bg-background/80 p-3 rounded-lg font-mono">
                    {clip.title} {clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}
                  </p>
                </Card>
              </TabsContent>

              <TabsContent value="shorts" className="pt-2">
                <Card className="border-border bg-surface p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-200">YouTube Shorts Title & Tags</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleCopy(
                          `${clip.title} #shorts\n\n${clip.description || ""}\n\n${clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}`,
                          "Shorts Metadata"
                        )
                      }
                      className="h-7 text-xs gap-1"
                    >
                      {copiedKey === "Shorts Metadata" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      Copy
                    </Button>
                  </div>
                  <p className="text-xs text-gray-300 bg-background/80 p-3 rounded-lg font-mono whitespace-pre-wrap">
                    {clip.title} #shorts{"\n\n"}
                    {clip.description}{"\n\n"}
                    {clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}
                  </p>
                </Card>
              </TabsContent>

              <TabsContent value="reels" className="pt-2">
                <Card className="border-border bg-surface p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-200">Reels Caption</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleCopy(
                          `${clip.title}\n.\n.\n${clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}`,
                          "Reels Caption"
                        )
                      }
                      className="h-7 text-xs gap-1"
                    >
                      {copiedKey === "Reels Caption" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      Copy
                    </Button>
                  </div>
                  <p className="text-xs text-gray-300 bg-background/80 p-3 rounded-lg font-mono whitespace-pre-wrap">
                    {clip.title}{"\n.\n.\n"}{clip.hashtags?.map((t) => `#${t.replace(/^#/, "")}`).join(" ")}
                  </p>
                </Card>
              </TabsContent>
            </Tabs>

            {/* EDL Inspector Card */}
            {edl && (
              <Card className="border-border bg-surface">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Scissors className="h-4 w-4 text-accent" />
                    Edit Decision List (EDL)
                  </CardTitle>
                  <CardDescription>
                    Pacing cuts, hook overlay, and 9:16 layout parameters generated by AI.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="p-2.5 rounded-lg bg-background border border-border">
                      <span className="text-[10px] text-muted-foreground uppercase">Trim In</span>
                      <div className="font-mono font-bold text-white mt-0.5">{edl.trim_in}s</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-background border border-border">
                      <span className="text-[10px] text-muted-foreground uppercase">Trim Out</span>
                      <div className="font-mono font-bold text-white mt-0.5">{edl.trim_out}s</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-background border border-border">
                      <span className="text-[10px] text-muted-foreground uppercase">Layout</span>
                      <div className="font-mono font-bold text-accent mt-0.5 capitalize">{edl.layout}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-background border border-border">
                      <span className="text-[10px] text-muted-foreground uppercase">Dead Air Cuts</span>
                      <div className="font-mono font-bold text-white mt-0.5">{edl.cuts?.length || 0} cuts</div>
                    </div>
                  </div>

                  {edl.hook_text && (
                    <div className="p-3 rounded-lg bg-accent/10 border border-accent/30 text-accent-light">
                      <span className="font-bold text-[11px] uppercase tracking-wider block mb-0.5">
                        Hook Text (0.0s - 2.5s):
                      </span>
                      &quot;{edl.hook_text}&quot;
                    </div>
                  )}

                  {edl.zoom_punches && edl.zoom_punches.length > 0 && (
                    <div className="space-y-1">
                      <span className="font-semibold text-muted-foreground text-[11px]">
                        Zoom Punches:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {edl.zoom_punches.map((zp, i) => (
                          <Badge key={i} variant="outline" className="text-[10px] font-mono">
                            @{zp.timestamp}s ({zp.scale}x for {zp.duration}s)
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
