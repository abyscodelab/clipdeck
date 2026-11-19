"use client";

import * as React from "react";
import { Sliders, Save, Database, HardDrive, Cpu, DollarSign, Bot, Mic } from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import type { Setting } from "@/lib/types";

interface DetectorSettingsProps {
  initialSettings?: Setting[];
  onSaveSettings: (settings: Record<string, any>) => Promise<any>;
}

export function DetectorSettings({
  initialSettings = [],
  onSaveSettings,
}: DetectorSettingsProps) {
  const { toast } = useToast();

  // Convert settings list to dictionary
  const settingsDict = React.useMemo(() => {
    const dict: Record<string, any> = {};
    initialSettings.forEach((s) => {
      dict[s.key] = s.value;
    });
    return dict;
  }, [initialSettings]);

  // Detector state
  const [threshold, setThreshold] = React.useState<number>(
    settingsDict["detector_threshold"] ?? 65
  );
  const [cooldown, setCooldown] = React.useState<number>(
    settingsDict["detector_cooldown_seconds"] ?? 90
  );
  const [windowSize, setWindowSize] = React.useState<number>(
    settingsDict["detector_window_seconds"] ?? 30
  );

  // Weights
  const [weightVelocity, setWeightVelocity] = React.useState<number>(
    settingsDict["weight_velocity"] ?? 40
  );
  const [weightEmotes, setWeightEmotes] = React.useState<number>(
    settingsDict["weight_emotes"] ?? 25
  );
  const [weightCaps, setWeightCaps] = React.useState<number>(
    settingsDict["weight_caps"] ?? 15
  );
  const [weightCopypasta, setWeightCopypasta] = React.useState<number>(
    settingsDict["weight_copypasta"] ?? 20
  );

  // General state
  const [mediaPath, setMediaPath] = React.useState<string>(
    settingsDict["media_path"] ?? "/data/media"
  );
  const [maxStreams, setMaxStreams] = React.useState<number>(
    settingsDict["max_concurrent_streams"] ?? 4
  );
  const [ringBufferMinutes, setRingBufferMinutes] = React.useState<number>(
    settingsDict["ring_buffer_max_minutes"] ?? 15
  );

  // Phase 2 AI Model and Budget settings
  const [scoringModel, setScoringModel] = React.useState<string>(
    settingsDict["scoring_model"] ?? "claude-3-5-sonnet-20241022"
  );
  const [edlModel, setEdlModel] = React.useState<string>(
    settingsDict["edl_model"] ?? "claude-3-5-sonnet-20241022"
  );
  const [titleModel, setTitleModel] = React.useState<string>(
    settingsDict["title_model"] ?? "gpt-4o"
  );
  const [transcriptionProvider, setTranscriptionProvider] = React.useState<string>(
    settingsDict["transcription_provider"] ?? "deepgram"
  );
  const [dailyBudgetCap, setDailyBudgetCap] = React.useState<number>(
    settingsDict["daily_budget_cap_usd"] ?? 10.0
  );

  const [isSaving, setIsSaving] = React.useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        detector_threshold: threshold,
        detector_cooldown_seconds: cooldown,
        detector_window_seconds: windowSize,
        weight_velocity: weightVelocity,
        weight_emotes: weightEmotes,
        weight_caps: weightCaps,
        weight_copypasta: weightCopypasta,
        media_path: mediaPath,
        max_concurrent_streams: maxStreams,
        ring_buffer_max_minutes: ringBufferMinutes,
        scoring_model: scoringModel,
        edl_model: edlModel,
        title_model: titleModel,
        transcription_provider: transcriptionProvider,
        daily_budget_cap_usd: dailyBudgetCap,
      };

      await onSaveSettings(payload);
      toast({
        title: "Settings Saved",
        message: "Algorithm thresholds, AI models, and budget caps updated.",
        type: "success",
      });
    } catch (err: any) {
      toast({
        title: "Save Failed",
        message: err.message || "Could not save settings",
        type: "error",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {/* AI Models & Budget Settings (Phase 2) */}
      <Card className="border-border bg-surface">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="h-4 w-4 text-accent" />
            AI Models & Cost Budget Protection
          </CardTitle>
          <CardDescription>
            Select preferred LLM backends per task, speech-to-text engine, and maximum daily spend.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="scoring-model">Moment Scoring Model</Label>
              <Select
                id="scoring-model"
                value={scoringModel}
                onChange={(e) => setScoringModel(e.target.value)}
              >
                <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                <option value="gpt-4o">GPT-4o (OpenAI)</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                <option value="meta-llama/llama-3.3-70b-instruct">Llama 3.3 70B</option>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edl-model">EDL Generator Model</Label>
              <Select
                id="edl-model"
                value={edlModel}
                onChange={(e) => setEdlModel(e.target.value)}
              >
                <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                <option value="gpt-4o">GPT-4o (OpenAI)</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="title-model">Title & Hashtags Model</Label>
              <Select
                id="title-model"
                value={titleModel}
                onChange={(e) => setTitleModel(e.target.value)}
              >
                <option value="gpt-4o">GPT-4o (OpenAI)</option>
                <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-border/50">
            <div className="space-y-1.5">
              <Label htmlFor="transcribe-prov" className="flex items-center gap-1.5">
                <Mic className="h-3.5 w-3.5 text-accent" />
                Transcription Provider (Speech-to-Text)
              </Label>
              <Select
                id="transcribe-prov"
                value={transcriptionProvider}
                onChange={(e) => setTranscriptionProvider(e.target.value)}
              >
                <option value="deepgram">Deepgram Nova-2 (Fast & Accurate)</option>
                <option value="whisper_api">OpenAI Whisper API</option>
                <option value="whisper_local">Local Faster-Whisper (GPU/CPU)</option>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="daily-cap" className="flex items-center gap-1.5">
                <DollarSign className="h-3.5 w-3.5 text-emerald-400" />
                Daily Budget Cap (USD $)
              </Label>
              <Input
                id="daily-cap"
                type="number"
                step="0.5"
                min="1"
                max="500"
                value={dailyBudgetCap}
                onChange={(e) => setDailyBudgetCap(parseFloat(e.target.value) || 10)}
                className="font-mono"
              />
              <span className="text-[11px] text-muted-foreground">
                Automatic safeguard: halts LLM clipping when daily limit is reached.
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Algorithm Tuning */}
      <Card className="border-border bg-surface">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Sliders className="h-4 w-4 text-accent" />
            Hype Detection Algorithm
          </CardTitle>
          <CardDescription>
            Configure EWMA sensitivity, spike threshold triggers, and cooldown timers.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Threshold Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-sm">
              <Label className="font-semibold text-white">Detection Threshold Score</Label>
              <span className="font-mono font-bold text-accent tabular-nums">{threshold} / 100</span>
            </div>
            <Slider
              value={threshold}
              min={20}
              max={95}
              step={1}
              onValueChange={setThreshold}
            />
            <p className="text-xs text-muted-foreground">
              Hype scores exceeding this trigger automatic moment creation. Lower = more clips; Higher = only huge moments.
            </p>
          </div>

          {/* Cooldown Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-sm">
              <Label className="font-semibold text-white">Spike Cooldown (Seconds)</Label>
              <span className="font-mono font-bold text-accent tabular-nums">{cooldown}s</span>
            </div>
            <Slider
              value={cooldown}
              min={15}
              max={300}
              step={5}
              onValueChange={setCooldown}
            />
            <p className="text-xs text-muted-foreground">
              Minimum duration to wait before triggering another clip on the same stream.
            </p>
          </div>

          {/* Window Size */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-sm">
              <Label className="font-semibold text-white">Analysis Window (Seconds)</Label>
              <span className="font-mono font-bold text-accent tabular-nums">{windowSize}s</span>
            </div>
            <Slider
              value={windowSize}
              min={10}
              max={120}
              step={5}
              onValueChange={setWindowSize}
            />
          </div>

          {/* Signal Weights Breakdown */}
          <div className="pt-4 border-t border-border space-y-4">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Signal Weight Distribution (Relative Impact)
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-medium">
                  <span>Chat Message Velocity</span>
                  <span className="font-mono text-accent">{weightVelocity}%</span>
                </div>
                <Slider
                  value={weightVelocity}
                  min={0}
                  max={100}
                  onValueChange={setWeightVelocity}
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-medium">
                  <span>Emote Density</span>
                  <span className="font-mono text-accent">{weightEmotes}%</span>
                </div>
                <Slider
                  value={weightEmotes}
                  min={0}
                  max={100}
                  onValueChange={setWeightEmotes}
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-medium">
                  <span>Capital Letters Ratio</span>
                  <span className="font-mono text-accent">{weightCaps}%</span>
                </div>
                <Slider
                  value={weightCaps}
                  min={0}
                  max={100}
                  onValueChange={setWeightCaps}
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-medium">
                  <span>Copypasta / Spam Burst</span>
                  <span className="font-mono text-accent">{weightCopypasta}%</span>
                </div>
                <Slider
                  value={weightCopypasta}
                  min={0}
                  max={100}
                  onValueChange={setWeightCopypasta}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* General System & Storage Settings */}
      <Card className="border-border bg-surface">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-accent" />
            Storage & Worker Limits
          </CardTitle>
          <CardDescription>
            Configure DVR ring buffer capacity and concurrent stream limits.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="media-path">Media Storage Path</Label>
              <Input
                id="media-path"
                value={mediaPath}
                onChange={(e) => setMediaPath(e.target.value)}
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="max-streams">Max Concurrent Streams</Label>
              <Input
                id="max-streams"
                type="number"
                min={1}
                max={16}
                value={maxStreams}
                onChange={(e) => setMaxStreams(parseInt(e.target.value) || 1)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ring-mins">Ring Buffer Retention (Mins)</Label>
              <Input
                id="ring-mins"
                type="number"
                min={5}
                max={60}
                value={ringBufferMinutes}
                onChange={(e) => setRingBufferMinutes(parseInt(e.target.value) || 15)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button type="submit" size="lg" isLoading={isSaving} className="gap-2 font-bold px-8">
          <Save className="h-4 w-4" />
          Save All Settings
        </Button>
      </div>
    </form>
  );
}
