"use client";

import * as React from "react";
import { Link2, Sparkles, Check } from "@/components/icons";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { detectPlatformFromUrl } from "@/lib/utils";
import type { Streamer, StreamerCreate, Platform, RelationshipType } from "@/lib/types";

interface StreamerFormProps {
  initialData?: Streamer;
  onSubmit: (data: StreamerCreate) => Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
}

export function StreamerForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: StreamerFormProps) {
  const [url, setUrl] = React.useState(initialData?.url || "");
  const [name, setName] = React.useState(initialData?.name || "");
  const [platform, setPlatform] = React.useState<Platform>(initialData?.platform || "twitch");
  const [relationship, setRelationship] = React.useState<RelationshipType>(
    initialData?.relationship_type || "none"
  );
  const [autoMonitor, setAutoMonitor] = React.useState(initialData?.auto_monitor ?? true);
  const [priority, setPriority] = React.useState(initialData?.priority ?? 10);
  const [niche, setNiche] = React.useState(initialData?.niche || "");
  const [keywords, setKeywords] = React.useState(initialData?.keywords?.join(", ") || "");
  const [emoteList, setEmoteList] = React.useState(initialData?.emote_list?.join(", ") || "");
  const [notes, setNotes] = React.useState(initialData?.notes || "");
  const [error, setError] = React.useState("");

  // Handle URL change with auto-detection
  const handleUrlChange = (val: string) => {
    setUrl(val);
    const detected = detectPlatformFromUrl(val);
    if (detected.platform) {
      setPlatform(detected.platform);
    }
    if (detected.extractedName && !name) {
      setName(detected.extractedName);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Streamer display name is required");
      return;
    }

    const payload: StreamerCreate = {
      name: name.trim(),
      platform,
      url: url.trim() || undefined,
      relationship_type: relationship,
      auto_monitor: autoMonitor,
      priority: Number(priority) || 0,
      niche: niche.trim() || undefined,
      keywords: keywords
        ? keywords.split(",").map((k) => k.trim()).filter(Boolean)
        : [],
      emote_list: emoteList
        ? emoteList.split(",").map((e) => e.trim()).filter(Boolean)
        : [],
      notes: notes.trim() || undefined,
    };

    try {
      await onSubmit(payload);
    } catch (err: any) {
      setError(err.message || "Failed to save streamer");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
          {error}
        </div>
      )}

      {/* URL with Auto-Detect */}
      <div className="space-y-1.5">
        <Label htmlFor="streamer-url">Stream URL (Twitch, Kick, or YouTube)</Label>
        <div className="relative">
          <Input
            id="streamer-url"
            type="url"
            placeholder="https://twitch.tv/streamer or https://kick.com/streamer"
            value={url}
            onChange={(e) => handleUrlChange(e.target.value)}
          />
          <Link2 className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-muted-foreground" />
        </div>
        <p className="text-[11px] text-muted-foreground">
          Pasting the channel URL auto-detects the platform and streamer name.
        </p>
      </div>

      {/* Name and Platform Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="streamer-name" required>Display Name</Label>
          <Input
            id="streamer-name"
            placeholder="e.g. xQc, shroud, Tarik"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="streamer-platform" required>Platform</Label>
          <Select
            id="streamer-platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform)}
          >
            <option value="twitch">Twitch</option>
            <option value="kick">Kick</option>
            <option value="youtube">YouTube</option>
          </Select>
        </div>
      </div>

      {/* Relationship and Priority Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="streamer-rel">Relationship</Label>
          <Select
            id="streamer-rel"
            value={relationship}
            onChange={(e) => setRelationship(e.target.value as RelationshipType)}
          >
            <option value="none">None (Third-party / Clip Channel)</option>
            <option value="editor">Official Editor</option>
            <option value="broadcaster_authorized">Broadcaster Authorized</option>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="streamer-priority">Priority (1 - 100)</Label>
          <Input
            id="streamer-priority"
            type="number"
            min={0}
            max={100}
            value={priority}
            onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
          />
        </div>
      </div>

      {/* Niche / Category */}
      <div className="space-y-1.5">
        <Label htmlFor="streamer-niche">Niche / Content Category</Label>
        <Input
          id="streamer-niche"
          placeholder="e.g. Valorant, Just Chatting, Variety, GTA RP"
          value={niche}
          onChange={(e) => setNiche(e.target.value)}
        />
      </div>

      {/* Keywords & Emotes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="streamer-keywords">Keywords (comma-separated)</Label>
          <Input
            id="streamer-keywords"
            placeholder="ACE, CLUTCH, OMG, W, L"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="streamer-emotes">Custom Emotes (comma-separated)</Label>
          <Input
            id="streamer-emotes"
            placeholder="KEKW, Pog, OMEGALUL, LUL"
            value={emoteList}
            onChange={(e) => setEmoteList(e.target.value)}
          />
        </div>
      </div>

      {/* Auto-Monitor Switch */}
      <div className="flex items-center justify-between p-3 rounded-xl border border-border bg-background">
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-white">Auto-Monitor Stream</span>
          <span className="text-xs text-muted-foreground">
            Automatically ingest chat and detect hype spikes when live.
          </span>
        </div>
        <Switch
          id="auto-monitor"
          checked={autoMonitor}
          onCheckedChange={setAutoMonitor}
        />
      </div>

      {/* Notes */}
      <div className="space-y-1.5">
        <Label htmlFor="streamer-notes">Internal Notes</Label>
        <Textarea
          id="streamer-notes"
          rows={2}
          placeholder="Clip style preferences, preferred audio settings, contact details..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
        )}
        <Button type="submit" isLoading={isLoading} className="gap-1.5 font-semibold">
          <Check className="h-4 w-4" />
          {initialData ? "Save Changes" : "Add Streamer"}
        </Button>
      </div>
    </form>
  );
}
