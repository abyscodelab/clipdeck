"use client";

import * as React from "react";
import Image from "next/image";
import {
  Sparkles,
  Download,
  Flame,
  Palette,
  Sliders,
  CheckCircle2,
  RefreshCw,
  Eye,
  Film,
  UploadCloud,
  ChevronRight,
  Split,
  Layers,
  Check,
  Smartphone,
  ChevronDown,
} from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getMediaUrl } from "@/lib/utils";
import type { Clip, ThumbnailListItem, ThumbnailResponse } from "@/lib/types";

export default function ThumbnailsPage() {
  const { toast } = useToast();

  const [thumbnails, setThumbnails] = React.useState<ThumbnailListItem[]>([]);
  const [clips, setClips] = React.useState<Clip[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [galleryFilter, setGalleryFilter] = React.useState<"all" | "cinematic" | "split">("all");

  // Studio Generator State
  const [selectedClipId, setSelectedClipId] = React.useState<string>("none");
  const [mode, setMode] = React.useState<"cinematic" | "split">("cinematic");
  const [word1, setWord1] = React.useState("INSANE");
  const [word2, setWord2] = React.useState("CLUTCH");
  const [badgeTitle, setBadgeTitle] = React.useState("GTA VI");
  const [badgeSub, setBadgeSub] = React.useState("CLIPPED");
  const [faceX, setFaceX] = React.useState(0.5);
  const [heroBase64, setHeroBase64] = React.useState<string | null>(null);
  const [heroFileName, setHeroFileName] = React.useState<string | null>(null);

  // Live preview & result
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [currentThumbnail, setCurrentThumbnail] = React.useState<ThumbnailResponse | null>(null);

  // Lightbox view
  const [previewThumb, setPreviewThumb] = React.useState<ThumbnailListItem | null>(null);

  const loadData = React.useCallback(async () => {
    try {
      setIsLoading(true);
      const [thumbList, clipList] = await Promise.all([
        api.thumbnails.list(50),
        api.clips.list(),
      ]);
      setThumbnails(thumbList);
      setClips(clipList);

      // Pre-select first clip if available
      if (clipList.length > 0 && selectedClipId === "none") {
        setSelectedClipId(clipList[0].id.toString());
        const words = (clipList[0].title || "INSANE CLUTCH")
          .replace(/[^\w\s]/g, "")
          .trim()
          .split(/\s+/);
        if (words.length >= 2) {
          setWord1(words[0].toUpperCase());
          setWord2(words[1].toUpperCase());
        }
      }
    } catch (err: any) {
      console.error("Failed to load thumbnail data:", err);
      toast({
        title: "Load Error",
        message: err.message || "Could not fetch thumbnails",
        type: "error",
      });
    } finally {
      setIsLoading(false);
    }
  }, [selectedClipId, toast]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // When clip selection changes, update words suggestion
  const handleClipSelect = (clipIdStr: string) => {
    setSelectedClipId(clipIdStr);
    if (clipIdStr !== "none") {
      const found = clips.find((c) => c.id.toString() === clipIdStr);
      if (found && found.title) {
        const tokens = found.title
          .replace(/[^\w\s]/g, "")
          .trim()
          .split(/\s+/)
          .filter((w) => w.length >= 2);
        if (tokens.length >= 2) {
          setWord1(tokens[0].toUpperCase());
          setWord2(tokens[1].toUpperCase());
        } else if (tokens.length === 1) {
          setWord1(tokens[0].toUpperCase());
          setWord2("LIVE");
        }
      }
    }
  };

  // Handle custom hero cutout upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setHeroFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      setHeroBase64(reader.result as string);
      toast({
        title: "Character Cutout Loaded",
        message: `Loaded ${file.name} for compositing.`,
        type: "success",
      });
    };
    reader.readAsDataURL(file);
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const clipIdNum = selectedClipId !== "none" ? parseInt(selectedClipId, 10) : undefined;
      const res = await api.thumbnails.generate({
        clip_id: clipIdNum,
        word1: word1.trim().toUpperCase(),
        word2: word2.trim().toUpperCase(),
        mode,
        face_x: faceX,
        badge_title: badgeTitle,
        badge_sub: badgeSub,
        hero_base64: heroBase64 || undefined,
      });

      setCurrentThumbnail(res);
      toast({
        title: "Vertical Thumbnail Created",
        message: `1080×1920 ${mode} cover generated successfully!`,
        type: "success",
      });

      // Reload gallery
      const updated = await api.thumbnails.list(50);
      setThumbnails(updated);
    } catch (err: any) {
      toast({
        title: "Generation Failed",
        message: err.message || "Failed to generate thumbnail",
        type: "error",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const filteredThumbnails = thumbnails.filter((t) => {
    if (galleryFilter === "all") return true;
    return t.mode.toLowerCase() === galleryFilter;
  });

  return (
    <AppShell>
      <div className="space-y-8 animate-in fade-in duration-200 max-w-6xl mx-auto">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Vertical Thumbnail Studio
              </h1>
              <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/[0.08] text-neutral-300 border border-white/10">
                1080 × 1920
              </span>
            </div>
            <p className="text-xs sm:text-sm text-neutral-400 max-w-2xl text-pretty">
              High-impact 9:16 vertical cover generator inspired by the GTA VI cinematic aesthetic. Miami night skyline, 2-word Anton typography layered behind the hero, and dual-rim lighting.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              isLoading={isLoading}
              className="gap-1.5 text-xs text-neutral-300"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Refresh</span>
            </Button>
          </div>
        </div>

        {/* Studio Workspace: Controls (Left) & Mobile Mockup Preview (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Controls Column (7 Cols) */}
          <div className="lg:col-span-7">
            <Card className="border-border bg-[#161616]">
              <CardHeader className="pb-4 border-b border-border/60">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-7 w-7 rounded-lg bg-white/10 flex items-center justify-center text-white border border-white/10">
                      <Sliders className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <CardTitle className="text-base text-white">Cover Composition</CardTitle>
                      <CardDescription className="text-xs text-neutral-400">
                        Configure layout mode, punchy words, and subject cutout
                      </CardDescription>
                    </div>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-6 pt-5">
                {/* 1. Aesthetic Mode Selection */}
                <div className="space-y-2.5">
                  <Label className="text-xs font-medium text-neutral-300">
                    Aesthetic Style Mode
                  </Label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setMode("cinematic")}
                      className={`p-3.5 rounded-xl border text-left transition-all duration-150 flex flex-col justify-between ${
                        mode === "cinematic"
                          ? "border-white/30 bg-white/[0.08] shadow-sm ring-1 ring-white/20"
                          : "border-border bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-semibold text-xs sm:text-sm text-white flex items-center gap-1.5">
                            <Flame className="h-4 w-4 text-rose-500 shrink-0" />
                            Cinematic Dual-Rim
                          </span>
                          <span
                            className={`h-4 w-4 rounded-full flex items-center justify-center border text-[10px] ${
                              mode === "cinematic"
                                ? "bg-white text-neutral-950 border-white font-bold"
                                : "border-white/20 text-transparent"
                            }`}
                          >
                            ✓
                          </span>
                        </div>
                        <p className="text-[11px] text-neutral-400 leading-relaxed text-pretty">
                          Police cruiser rim lighting: Crimson light on left silhouette, Ice Blue on right. Full-color subject.
                        </p>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setMode("split")}
                      className={`p-3.5 rounded-xl border text-left transition-all duration-150 flex flex-col justify-between ${
                        mode === "split"
                          ? "border-white/30 bg-white/[0.08] shadow-sm ring-1 ring-white/20"
                          : "border-border bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-semibold text-xs sm:text-sm text-white flex items-center gap-1.5">
                            <Split className="h-4 w-4 text-cyan-400 shrink-0" />
                            Split AI Wireframe
                          </span>
                          <span
                            className={`h-4 w-4 rounded-full flex items-center justify-center border text-[10px] ${
                              mode === "split"
                                ? "bg-white text-neutral-950 border-white font-bold"
                                : "border-white/20 text-transparent"
                            }`}
                          >
                            ✓
                          </span>
                        </div>
                        <p className="text-[11px] text-neutral-400 leading-relaxed text-pretty">
                          3D wireframe mesh on left half with monochrome B&W grade and vertical divider.
                        </p>
                      </div>
                    </button>
                  </div>
                </div>

                {/* 2. Source Video Clip Select */}
                <div className="space-y-1.5">
                  <Label htmlFor="clip-select" className="text-xs font-medium text-neutral-300">
                    Source Video Clip
                  </Label>
                  <div className="relative">
                    <select
                      id="clip-select"
                      value={selectedClipId}
                      onChange={(e) => handleClipSelect(e.target.value)}
                      className="w-full h-10 pl-3.5 pr-8 bg-[#121212] border border-border rounded-xl text-xs sm:text-sm text-neutral-200 focus:outline-none focus:border-white/20 focus:ring-1 focus:ring-white/20 appearance-none cursor-pointer"
                    >
                      <option value="none">Standalone Studio Cover (No Clip Attached)</option>
                      {clips.map((c) => (
                        <option key={c.id} value={c.id.toString()}>
                          Clip #{c.id} — {c.title || "Untitled Short"} ({c.duration?.toFixed(1)}s)
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-3 h-4 w-4 text-neutral-500 pointer-events-none" />
                  </div>
                  <p className="text-[11px] text-neutral-500">
                    Auto-extracts character frame and derives hook words from the clip title.
                  </p>
                </div>

                {/* 3. 2-Word Typography */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-medium text-neutral-300">
                      Impact Typography (1-2 Words)
                    </Label>
                    <span className="text-[10px] font-mono text-neutral-500">
                      Layered Behind Hero Character
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-neutral-400">Word 1</span>
                        <span className="text-neutral-300 font-mono text-[10px]">Pure White (#FFF)</span>
                      </div>
                      <Input
                        id="word1"
                        value={word1}
                        onChange={(e) => setWord1(e.target.value)}
                        placeholder="INSANE"
                        className="font-mono uppercase tracking-wider text-sm font-bold bg-[#121212]"
                      />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-neutral-400">Word 2</span>
                        <span className="text-rose-400 font-mono text-[10px]">Hook Red (#EB1923)</span>
                      </div>
                      <Input
                        id="word2"
                        value={word2}
                        onChange={(e) => setWord2(e.target.value)}
                        placeholder="CLUTCH"
                        className="font-mono uppercase tracking-wider text-sm font-bold text-rose-500 border-rose-500/30 bg-[#121212]"
                      />
                    </div>
                  </div>
                </div>

                {/* 4. Nose Split Slider (Only visible in Split mode) */}
                {mode === "split" && (
                  <div className="space-y-2 p-3.5 rounded-xl bg-white/[0.02] border border-border">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-neutral-300">Nose Split Position</span>
                      <span className="font-mono text-neutral-200 text-xs px-2 py-0.5 rounded-full bg-white/10">
                        {(faceX * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0.2"
                      max="0.8"
                      step="0.01"
                      value={faceX}
                      onChange={(e) => setFaceX(parseFloat(e.target.value))}
                      className="w-full accent-white h-1.5 bg-neutral-800 rounded-lg cursor-pointer"
                    />
                    <p className="text-[11px] text-neutral-500">
                      Align the B&W scan line directly with the character&apos;s nose bridge.
                    </p>
                  </div>
                )}

                {/* 5. Custom Hero Character Upload */}
                <div className="space-y-1.5">
                  <Label htmlFor="hero-upload" className="text-xs font-medium text-neutral-300">
                    Subject Character (Optional Cutout)
                  </Label>
                  <div className="relative border border-dashed border-white/10 hover:border-white/20 rounded-xl p-4 text-center transition-colors bg-[#121212]/60 cursor-pointer group">
                    <input
                      id="hero-upload"
                      type="file"
                      accept="image/png,image/webp,image/jpeg"
                      onChange={handleFileUpload}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                    />
                    <div className="flex flex-col items-center justify-center gap-1.5 pointer-events-none">
                      <UploadCloud className="h-5 w-5 text-neutral-400 group-hover:text-white transition-colors" />
                      <span className="text-xs font-medium text-neutral-200">
                        {heroFileName ? heroFileName : "Upload transparent PNG cutout"}
                      </span>
                      <span className="text-[10px] text-neutral-500 max-w-sm">
                        Leave blank to auto-extract the optimal keyframe from the source video.
                      </span>
                    </div>
                  </div>
                </div>

                {/* 6. Branding Badge Labels */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="badge-title" className="text-xs text-neutral-400">
                      Badge Title
                    </Label>
                    <Input
                      id="badge-title"
                      value={badgeTitle}
                      onChange={(e) => setBadgeTitle(e.target.value)}
                      placeholder="GTA VI"
                      className="h-9 text-xs font-mono bg-[#121212]"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="badge-sub" className="text-xs text-neutral-400">
                      Badge Subtitle
                    </Label>
                    <Input
                      id="badge-sub"
                      value={badgeSub}
                      onChange={(e) => setBadgeSub(e.target.value)}
                      placeholder="CLIPPED"
                      className="h-9 text-xs font-mono bg-[#121212]"
                    />
                  </div>
                </div>

                {/* Generate Trigger */}
                <div className="pt-2">
                  <Button
                    onClick={handleGenerate}
                    size="lg"
                    isLoading={isGenerating}
                    className="w-full h-11 bg-white hover:bg-neutral-200 text-neutral-950 font-semibold rounded-xl text-sm gap-2 shadow-sm"
                  >
                    <Sparkles className="h-4 w-4" />
                    <span>Generate 1080×1920 Vertical Thumbnail</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Phone Preview Column (5 Cols) */}
          <div className="lg:col-span-5 flex flex-col items-center">
            <Card className="w-full max-w-[340px] border-border bg-[#161616] p-4 flex flex-col items-center">
              <div className="flex items-center justify-between w-full pb-3 mb-3 border-b border-border/70 text-xs">
                <span className="font-semibold text-neutral-300 flex items-center gap-1.5">
                  <Smartphone className="h-4 w-4 text-neutral-400" />
                  Live 9:16 Canvas
                </span>
                <span className="text-[10px] font-mono text-neutral-400 px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/10">
                  1080 × 1920
                </span>
              </div>

              {/* Realistic Phone Bezel Frame */}
              <div className="w-full aspect-[9/16] rounded-[24px] p-2 bg-[#0D0D0D] border border-white/10 shadow-[0_16px_40px_rgba(0,0,0,0.7)] flex flex-col relative group">
                {/* Speaker Ear Notch */}
                <div className="w-16 h-3 bg-black rounded-full mx-auto mb-1.5 shrink-0" />

                {/* Inner Canvas Display */}
                <div className="w-full flex-1 rounded-[16px] overflow-hidden bg-black relative flex items-center justify-center">
                  {currentThumbnail ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={getMediaUrl(currentThumbnail.thumbnail_url)}
                      alt="Generated Vertical Thumbnail"
                      className="w-full h-full object-cover outline outline-1 -outline-offset-1 outline-white/10 transition-transform duration-300 group-hover:scale-[1.02]"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center bg-[#0F0F0F]">
                      <div className="h-10 w-10 rounded-full bg-white/[0.05] border border-white/10 flex items-center justify-center mb-3 text-neutral-400">
                        <Layers className="h-5 w-5" />
                      </div>
                      <span className="font-medium text-xs text-white mb-1">
                        Awaiting Generation
                      </span>
                      <p className="text-[11px] text-neutral-500 leading-relaxed text-pretty">
                        Click &ldquo;Generate&rdquo; to composite your 1080×1920 short-form cover image.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Download / Export Action */}
              {currentThumbnail && (
                <div className="w-full pt-4 space-y-2 animate-in fade-in">
                  <a
                    href={getMediaUrl(currentThumbnail.thumbnail_url)}
                    download={`thumb_${word1}_${word2}_1080x1920.jpg`}
                    className="w-full block"
                  >
                    <Button variant="secondary" size="sm" className="w-full h-9 rounded-xl text-xs gap-2">
                      <Download className="h-3.5 w-3.5" />
                      <span>Download High-Res 1080×1920</span>
                    </Button>
                  </a>
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Gallery Section */}
        <div className="space-y-4 pt-6 border-t border-border">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                <Film className="h-4 w-4 text-neutral-400" />
                Thumbnail Library
              </h2>
              <p className="text-xs text-neutral-400">
                All generated 1080×1920 vertical cover assets for Shorts, Reels, and TikTok.
              </p>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 p-1 rounded-full bg-white/[0.04] border border-border">
              {(["all", "cinematic", "split"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setGalleryFilter(tab)}
                  className={`px-3 py-1 text-xs rounded-full capitalize transition-colors ${
                    galleryFilter === tab
                      ? "bg-white/10 text-white font-medium border border-white/10"
                      : "text-neutral-400 hover:text-white"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {filteredThumbnails.length === 0 ? (
            <div className="p-12 text-center border border-dashed border-border rounded-2xl bg-[#141414]/50">
              <Sparkles className="h-6 w-6 text-neutral-500 mx-auto mb-2" />
              <h3 className="text-xs font-semibold text-white">No thumbnails found</h3>
              <p className="text-[11px] text-neutral-500 mt-1">
                {galleryFilter === "all"
                  ? "Generate your first vertical thumbnail using the studio above."
                  : `No ${galleryFilter} thumbnails generated yet.`}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3.5">
              {filteredThumbnails.map((t) => (
                <div
                  key={t.filename}
                  className="group relative rounded-xl border border-border bg-[#161616] overflow-hidden transition-all duration-150 hover:border-white/20 hover:shadow-lg"
                >
                  <div className="aspect-[9/16] relative bg-black overflow-hidden">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={getMediaUrl(t.thumbnail_url)}
                      alt={t.filename}
                      className="w-full h-full object-cover outline outline-1 -outline-offset-1 outline-white/10 transition-transform duration-200 group-hover:scale-[1.03]"
                    />
                    {/* Hover Overlay */}
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1.5 p-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="w-full h-7 text-[11px] gap-1 rounded-lg"
                        onClick={() => setPreviewThumb(t)}
                      >
                        <Eye className="h-3 w-3" />
                        <span>Preview</span>
                      </Button>
                      <a
                        href={getMediaUrl(t.thumbnail_url)}
                        download={t.filename}
                        className="w-full block"
                      >
                        <Button size="sm" variant="default" className="w-full h-7 text-[11px] gap-1 rounded-lg font-semibold">
                          <Download className="h-3 w-3" />
                          <span>Save</span>
                        </Button>
                      </a>
                    </div>
                  </div>

                  {/* Card Meta Footer */}
                  <div className="p-2.5 text-center border-t border-border/60 bg-[#141414]">
                    <div className="flex items-center justify-between text-[11px] mb-1 font-mono">
                      <span className="text-white font-bold truncate max-w-[50%]">{t.word1}</span>
                      <span className="text-rose-400 font-bold truncate max-w-[50%]">{t.word2}</span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-neutral-400">
                      <span className="uppercase text-[9px] px-1.5 py-0.5 rounded-full bg-white/[0.06] border border-white/10">
                        {t.mode}
                      </span>
                      <span className="tabular-nums">{(t.size_bytes / 1024).toFixed(0)} KB</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Lightbox Preview Modal */}
        {previewThumb && (
          <Dialog open={!!previewThumb} onOpenChange={() => setPreviewThumb(null)}>
            <DialogContent className="max-w-md bg-[#161616] border-border p-5 flex flex-col items-center rounded-2xl">
              <DialogHeader className="w-full text-left pb-2">
                <DialogTitle className="text-sm font-semibold flex items-center justify-between">
                  <span>
                    Vertical Cover: {previewThumb.word1} {previewThumb.word2}
                  </span>
                  <span className="uppercase text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.08] text-neutral-300 border border-white/10">
                    {previewThumb.mode}
                  </span>
                </DialogTitle>
                <DialogDescription className="text-xs text-neutral-400">
                  Native 1080×1920 high-resolution vertical render.
                </DialogDescription>
              </DialogHeader>

              <div className="w-full max-w-[300px] aspect-[9/16] rounded-2xl overflow-hidden border border-white/10 shadow-2xl bg-black my-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getMediaUrl(previewThumb.thumbnail_url)}
                  alt="Full preview"
                  className="w-full h-full object-cover outline outline-1 -outline-offset-1 outline-white/10"
                />
              </div>

              <div className="w-full flex items-center justify-between pt-3 border-t border-border mt-2">
                <span className="text-xs text-neutral-400 font-mono tabular-nums">
                  {(previewThumb.size_bytes / 1024).toFixed(0)} KB • 1080 × 1920
                </span>
                <a
                  href={getMediaUrl(previewThumb.thumbnail_url)}
                  download={previewThumb.filename}
                >
                  <Button size="sm" className="h-8 px-3 rounded-lg text-xs gap-1.5 font-semibold">
                    <Download className="h-3.5 w-3.5" />
                    <span>Download Image</span>
                  </Button>
                </a>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </AppShell>
  );
}
