"use client";

import * as React from "react";
import { Sliders, Save, Sparkles, Code, Cpu, Plus } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import type { PromptTemplate } from "@/lib/types";

const AVAILABLE_PLACEHOLDERS = [
  { tag: "{{transcript}}", desc: "Whisper/Deepgram word timestamps & full text" },
  { tag: "{{chat_messages}}", desc: "Top chat messages during the hype spike" },
  { tag: "{{hype_metrics}}", desc: "Chat velocity, caps ratio & copypasta score" },
  { tag: "{{streamer_name}}", desc: "Broadcaster handle and channel niche" },
  { tag: "{{playbook_rules}}", desc: "Merged hierarchical editing & safety playbook" },
];

export default function TemplatesPage() {
  const { toast } = useToast();

  const [activeTask, setActiveTask] = React.useState<"scoring" | "edl" | "title">("scoring");
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [templateText, setTemplateText] = React.useState("");
  const [defaultModel, setDefaultModel] = React.useState("claude-3-5-sonnet-20241022");
  const [isSaving, setIsSaving] = React.useState(false);

  // Fetch Templates
  const {
    data: templates = [],
    isLoading,
    mutate,
  } = useApi<PromptTemplate[]>(() => api.templates.list(), [], {
    onSuccess: (data) => {
      const match = data.find((t) => t.task_type === activeTask);
      if (match) {
        setSystemPrompt(match.system_prompt);
        setTemplateText(match.template_text);
        setDefaultModel(match.default_model);
      }
    },
  });

  // When tab changes, populate form with that template
  React.useEffect(() => {
    const match = templates.find((t) => t.task_type === activeTask);
    if (match) {
      setSystemPrompt(match.system_prompt);
      setTemplateText(match.template_text);
      setDefaultModel(match.default_model);
    } else {
      // Defaults if DB not populated yet
      if (activeTask === "scoring") {
        setSystemPrompt("You are an expert stream clipping evaluator. Evaluate whether this moment has high viral potential.");
        setTemplateText("Analyze the moment transcript:\n{{transcript}}\n\nChat reaction:\n{{chat_messages}}\n\nPlaybook:\n{{playbook_rules}}\n\nOutput JSON matching MomentScoreResult.");
      } else if (activeTask === "edl") {
        setSystemPrompt("You are an elite short-form video editor for TikTok and Shorts. Produce a precise EditDecisionList JSON.");
        setTemplateText("Moment dialogue:\n{{transcript}}\n\nRules:\n{{playbook_rules}}\n\nGenerate trim in/out, cut dead air >0.7s, add hook text.");
      } else {
        setSystemPrompt("You are a viral social media manager. Generate high-CTR titles and engaging captions.");
        setTemplateText("Streamer: {{streamer_name}}\nMoment: {{transcript}}\n\nGenerate title, description, and hashtags.");
      }
    }
  }, [activeTask, templates]);

  const handleInsertTag = (tag: string) => {
    setTemplateText((prev) => `${prev} ${tag}`);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const current = templates.find((t) => t.task_type === activeTask);
      if (current) {
        await api.templates.update(current.id, {
          system_prompt: systemPrompt,
          template_text: templateText,
          default_model: defaultModel,
        });
      }
      toast({
        title: "Prompt Template Saved",
        message: `${activeTask.toUpperCase()} prompt configuration updated.`,
        type: "success",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Save Failed",
        message: err.message || "Could not save prompt template",
        type: "error",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-4xl mx-auto">
        {/* Header */}
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <Sliders className="h-6 w-6 text-accent" />
            AI Prompt Templates
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Customize system instructions, few-shot structures, and variable bindings for LLM pipelines.
          </p>
        </div>

        {/* Task Tabs */}
        <div className="flex rounded-xl bg-surface border border-border p-1 w-full sm:w-96">
          <button
            type="button"
            onClick={() => setActiveTask("scoring")}
            className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
              activeTask === "scoring" ? "bg-accent text-white shadow-sm" : "text-muted-foreground hover:text-white"
            }`}
          >
            1. Moment Scoring
          </button>
          <button
            type="button"
            onClick={() => setActiveTask("edl")}
            className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
              activeTask === "edl" ? "bg-accent text-white shadow-sm" : "text-muted-foreground hover:text-white"
            }`}
          >
            2. EDL Generator
          </button>
          <button
            type="button"
            onClick={() => setActiveTask("title")}
            className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
              activeTask === "title" ? "bg-accent text-white shadow-sm" : "text-muted-foreground hover:text-white"
            }`}
          >
            3. Title & Captions
          </button>
        </div>

        {/* Template Form */}
        <form onSubmit={handleSave} className="space-y-4">
          <Card className="border-border bg-surface">
            <CardHeader className="pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-accent" />
                  Task Model & System Instruction
                </CardTitle>

                <div className="w-full sm:w-64">
                  <Select
                    value={defaultModel}
                    onChange={(e) => setDefaultModel(e.target.value)}
                  >
                    <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (Recommended)</option>
                    <option value="gpt-4o">GPT-4o (OpenAI)</option>
                    <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                    <option value="meta-llama/llama-3.3-70b-instruct">Llama 3.3 70B (OpenRouter)</option>
                  </Select>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="sys-prompt">System Prompt</Label>
                <Textarea
                  id="sys-prompt"
                  rows={3}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>

              {/* Variable Placeholders Toolbar */}
              <div className="space-y-1.5 pt-2 border-t border-border/50">
                <Label className="text-xs text-muted-foreground">
                  Click to Insert Variable Tag:
                </Label>
                <div className="flex flex-wrap gap-1.5">
                  {AVAILABLE_PLACEHOLDERS.map((ph) => (
                    <button
                      key={ph.tag}
                      type="button"
                      onClick={() => handleInsertTag(ph.tag)}
                      title={ph.desc}
                      className="px-2 py-1 rounded-md bg-accent/15 border border-accent/30 text-accent-light text-[11px] font-mono hover:bg-accent/25 transition-colors flex items-center gap-1"
                    >
                      <Plus className="h-3 w-3" />
                      {ph.tag}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="user-template">User Prompt Template</Label>
                <Textarea
                  id="user-template"
                  rows={8}
                  value={templateText}
                  onChange={(e) => setTemplateText(e.target.value)}
                  className="font-mono text-xs leading-relaxed"
                />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button type="submit" size="lg" isLoading={isSaving} className="gap-2 font-bold px-6">
              <Save className="h-4 w-4" />
              Save Template
            </Button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
