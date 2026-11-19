"use client";

import * as React from "react";
import Link from "next/link";
import {
  BookOpen,
  Plus,
  Upload,
  CheckCircle2,
  Sliders,
  Radio,
  Globe,
  Tag,
  Crosshair,
  FileText,
  Trash2,
} from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";
import type { Playbook, PlaybookCreate, PlaybookScope } from "@/lib/types";

export default function PlaybooksPage() {
  const { toast } = useToast();
  const [scopeFilter, setScopeFilter] = React.useState<string>("");
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // New Playbook Form State
  const [newName, setNewName] = React.useState("");
  const [newDescription, setNewDescription] = React.useState("");
  const [newScope, setNewScope] = React.useState<PlaybookScope>("global");
  const [newTargetId, setNewTargetId] = React.useState("");
  const [newPriority, setNewPriority] = React.useState(50);
  const [newContent, setNewContent] = React.useState(`# Playbook Rules

## What TO Clip (High Priority)
- Big gameplay plays and clutches
- High chat spike reaction moments
- Funny streamer banter or unexpected failures

## What NOT to Clip (Hard Safety Rules)
- NO copyrighted music as main audio
- NO gambling or sponsor reads
- NO toxic slurs or personal info
- NO dead air over 0.7 seconds

## Pacing & Editing Guidelines
- 15 to 60 seconds duration
- Punchy hook within first 2.5 seconds
- Animated ASS subtitles enabled
`);

  // Fetch Playbooks
  const {
    data: playbooks = [],
    isLoading,
    mutate,
  } = useApi<Playbook[]>(
    () => api.playbooks.list(scopeFilter || undefined),
    [scopeFilter]
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    setIsSubmitting(true);
    try {
      const payload: PlaybookCreate = {
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        scope: newScope,
        target_id: newTargetId.trim() || undefined,
        priority: Number(newPriority) || 50,
        enabled: true,
        content: newContent,
      };

      await api.playbooks.create(payload);
      toast({
        title: "Playbook Created",
        message: `${payload.name} added to hierarchy.`,
        type: "success",
      });
      setIsCreateOpen(false);
      mutate();
    } catch (err: any) {
      toast({
        title: "Creation Failed",
        message: err.message || "Failed to create playbook",
        type: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleEnable = async (playbook: Playbook) => {
    try {
      await api.playbooks.update(playbook.id, {
        enabled: !playbook.enabled,
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Update Failed",
        message: err.message || "Failed to toggle playbook",
        type: "error",
      });
    }
  };

  const getScopeIcon = (scope: PlaybookScope) => {
    switch (scope) {
      case "global":
        return <Globe className="h-3.5 w-3.5 text-accent" />;
      case "category":
        return <Tag className="h-3.5 w-3.5 text-neutral-300" />;
      case "streamer":
        return <Radio className="h-3.5 w-3.5 text-emerald-400" />;
      case "target":
        return <Crosshair className="h-3.5 w-3.5 text-amber-400" />;
      default:
        return <BookOpen className="h-3.5 w-3.5 text-gray-400" />;
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <BookOpen className="h-6 w-6 text-accent" />
              AI Playbooks
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Hierarchical rulesets guiding virality scoring, brand-safety compliance, hook styles, and pacing.
            </p>
          </div>

          <Button
            onClick={() => setIsCreateOpen(true)}
            className="gap-2 font-bold shadow-md shadow-accent/20"
          >
            <Plus className="h-4 w-4" />
            Create Playbook
          </Button>
        </div>

        {/* Scope Hierarchy Explainer Banner */}
        <div className="p-4 rounded-xl border border-border bg-surface/60 text-xs text-muted-foreground flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap font-medium">
            <span className="text-gray-300 font-bold">Merge Order:</span>
            <span className="px-2 py-0.5 rounded bg-surface border border-border text-accent-light">
              1. Global Rules
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded bg-surface border border-border text-neutral-300">
              2. Category (Gaming / IRL)
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded bg-surface border border-border text-emerald-400">
              3. Streamer
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-0.5 rounded bg-surface border border-border text-amber-400">
              4. Target Platform
            </span>
          </div>
          <span className="text-[11px] text-muted-foreground italic">
            Hard safety rules (&quot;NO&quot;) are enforced across all tiers.
          </span>
        </div>

        {/* Scope Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {["", "global", "category", "streamer", "target"].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setScopeFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                scopeFilter === s
                  ? "bg-accent text-white shadow-sm"
                  : "bg-surface border border-border text-muted-foreground hover:text-white"
              }`}
            >
              {s ? `${s} Scope` : "All Scopes"}
            </button>
          ))}
        </div>

        {/* Playbooks List Grid */}
        {isLoading && playbooks.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-48 w-full rounded-xl" />
            ))}
          </div>
        ) : playbooks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/30 p-12 text-center flex flex-col items-center">
            <BookOpen className="h-10 w-10 text-muted-foreground mb-2" />
            <h3 className="text-base font-semibold text-white">No playbooks found</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm mb-4">
              Add your first playbook or configure category-specific rulesets for stream moments.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {playbooks.map((pb) => (
              <Card
                key={pb.id}
                className="border-border bg-surface hover:border-accent/40 transition-all flex flex-col justify-between"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      {getScopeIcon(pb.scope)}
                      <Badge variant="outline" className="text-[10px] uppercase font-mono">
                        {pb.scope}
                      </Badge>
                      {pb.target_id && (
                        <span className="text-[10px] text-muted-foreground truncate max-w-[100px]">
                          ({pb.target_id})
                        </span>
                      )}
                    </div>
                    <Switch
                      checked={pb.enabled}
                      onCheckedChange={() => handleToggleEnable(pb)}
                    />
                  </div>

                  <Link href={`/playbooks/${pb.id}`}>
                    <CardTitle className="text-base font-bold text-white hover:text-accent-light transition-colors mt-2">
                      {pb.name}
                    </CardTitle>
                  </Link>

                  {pb.description && (
                    <CardDescription className="text-xs text-gray-300 line-clamp-2 mt-1">
                      {pb.description}
                    </CardDescription>
                  )}
                </CardHeader>

                <CardContent className="pt-0">
                  <div className="flex items-center justify-between pt-3 border-t border-border/50 text-[11px] text-muted-foreground">
                    <span>Priority: {pb.priority}</span>
                    <Link href={`/playbooks/${pb.id}`}>
                      <Button variant="ghost" size="sm" className="h-7 text-xs text-accent hover:text-white">
                        Edit & Test Bench &rarr;
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create Playbook Modal */}
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create New AI Playbook</DialogTitle>
              <DialogDescription>
                Define editing rules, brand-safety negative constraints, and hook styles.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="pb-name" required>Playbook Name</Label>
                <Input
                  id="pb-name"
                  placeholder="e.g. Fast-Paced Gaming Viral Clips"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="pb-scope">Scope</Label>
                  <Select
                    id="pb-scope"
                    value={newScope}
                    onChange={(e) => setNewScope(e.target.value as PlaybookScope)}
                  >
                    <option value="global">Global (All Streams)</option>
                    <option value="category">Category (Gaming / IRL)</option>
                    <option value="streamer">Streamer-Specific</option>
                    <option value="target">Target Platform (TikTok/Shorts)</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="pb-priority">Priority (1 - 100)</Label>
                  <Input
                    id="pb-priority"
                    type="number"
                    min={1}
                    max={100}
                    value={newPriority}
                    onChange={(e) => setNewPriority(parseInt(e.target.value) || 50)}
                  />
                </div>
              </div>

              {newScope !== "global" && (
                <div className="space-y-1.5">
                  <Label htmlFor="pb-target-id">Target Identifier</Label>
                  <Input
                    id="pb-target-id"
                    placeholder="e.g. 'gaming', 'irl', streamer ID, or 'tiktok'"
                    value={newTargetId}
                    onChange={(e) => setNewTargetId(e.target.value)}
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="pb-desc">Description</Label>
                <Input
                  id="pb-desc"
                  placeholder="Short summary of ruleset goals..."
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="pb-content" required>Playbook Content (Markdown)</Label>
                <Textarea
                  id="pb-content"
                  rows={8}
                  className="font-mono text-xs"
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  required
                />
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCreateOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" isLoading={isSubmitting}>
                  Save Playbook
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
