"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  BookOpen,
  ArrowLeft,
  Save,
  RotateCcw,
  Upload,
  Play,
  History,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  Eye,
  Edit3,
} from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";
import type { Playbook } from "@/lib/types";

export default function PlaybookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const playbookId = Number(params?.id);

  const [content, setContent] = React.useState("");
  const [editorTab, setEditorTab] = React.useState<"write" | "preview">("write");
  const [isSaving, setIsSaving] = React.useState(false);

  // File Upload State
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);

  // Test Bench State
  const [sampleText, setSampleText] = React.useState(
    "Streamer: Check this insane 1v4 clutch on A site! Chat: OMG PogChamp KEKW WTFFFF HE HIT THAT 360 HEADSHOT!"
  );
  const [isTesting, setIsTesting] = React.useState(false);
  const [testResult, setTestResult] = React.useState<{
    rules_applied: string[];
    rule_violations: string[];
    analysis: string;
  } | null>(null);

  // Fetch Playbook details
  const {
    data: playbook,
    isLoading,
    mutate,
  } = useApi<Playbook>(() => api.playbooks.get(playbookId), [playbookId], {
    onSuccess: (data) => {
      setContent(data.content);
    },
  });

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.playbooks.update(playbookId, { content });
      toast({
        title: "Playbook Updated",
        message: "New version recorded in history.",
        type: "success",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Save Failed",
        message: err.message || "Failed to update playbook",
        type: "error",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRollback = async (versionNumber: number) => {
    try {
      await api.playbooks.rollback(playbookId, versionNumber);
      toast({
        title: "Rollback Complete",
        message: `Restored playbook to version #${versionNumber}`,
        type: "info",
      });
      mutate();
    } catch (err: any) {
      toast({
        title: "Rollback Failed",
        message: err.message || "Could not rollback version",
        type: "error",
      });
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      await api.playbooks.uploadFile(playbookId, formData);
      toast({
        title: "File Uploaded",
        message: `${selectedFile.name} added to playbook references.`,
        type: "success",
      });
      setIsUploadOpen(false);
      setSelectedFile(null);
      mutate();
    } catch (err: any) {
      toast({
        title: "Upload Failed",
        message: err.message || "Failed to upload file",
        type: "error",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunTestBench = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await api.playbooks.testBench(playbookId, sampleText);
      setTestResult(res);
      toast({
        title: "Test Complete",
        message: `Evaluated rules against sample transcript.`,
        type: "success",
      });
    } catch (err: any) {
      toast({
        title: "Test Bench Failed",
        message: err.message || "Failed to run test bench",
        type: "error",
      });
    } finally {
      setIsTesting(false);
    }
  };

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-4 max-w-5xl mx-auto">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (!playbook) {
    return (
      <AppShell>
        <div className="p-8 text-center text-muted-foreground">Playbook not found.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-5xl mx-auto">
        {/* Navigation & Actions */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <Link href="/playbooks">
            <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-white">
              <ArrowLeft className="h-4 w-4" />
              All Playbooks
            </Button>
          </Link>

          <div className="flex items-center gap-2 self-end sm:self-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsUploadOpen(true)}
              className="gap-1.5 text-xs"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload Reference (.md/.txt)
            </Button>

            <Button
              size="sm"
              isLoading={isSaving}
              onClick={handleSave}
              className="gap-1.5 text-xs font-bold"
            >
              <Save className="h-3.5 w-3.5" />
              Save Ruleset
            </Button>
          </div>
        </div>

        {/* Playbook Header */}
        <div className="p-5 rounded-2xl border border-border bg-surface flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-black text-white">{playbook.name}</h1>
              <Badge variant="outline" className="text-xs uppercase font-mono">
                {playbook.scope}
              </Badge>
              {playbook.target_id && (
                <Badge variant="secondary" className="text-xs font-mono">
                  {playbook.target_id}
                </Badge>
              )}
            </div>
            {playbook.description && (
              <p className="text-xs text-muted-foreground mt-1">{playbook.description}</p>
            )}
          </div>

          <div className="text-xs text-muted-foreground text-right shrink-0">
            <div>Priority: <span className="font-bold text-white">{playbook.priority}</span></div>
            <div className="text-[11px] mt-0.5">Updated: {formatDate(playbook.updated_at)}</div>
          </div>
        </div>

        {/* Tabbed View: Editor, Version History, Test Bench */}
        <Tabs defaultValue="editor">
          <TabsList className="grid grid-cols-3 w-full sm:w-96">
            <TabsTrigger value="editor" className="text-xs font-semibold gap-1.5">
              <Edit3 className="h-3.5 w-3.5" />
              Editor
            </TabsTrigger>
            <TabsTrigger value="history" className="text-xs font-semibold gap-1.5">
              <History className="h-3.5 w-3.5" />
              Versions ({playbook.versions?.length || 1})
            </TabsTrigger>
            <TabsTrigger value="testbench" className="text-xs font-semibold gap-1.5">
              <Play className="h-3.5 w-3.5 text-emerald-400" />
              Test Bench
            </TabsTrigger>
          </TabsList>

          {/* Editor Tab */}
          <TabsContent value="editor" className="pt-2 space-y-4">
            <Card className="border-border bg-surface">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setEditorTab("write")}
                      className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${
                        editorTab === "write"
                          ? "bg-accent text-white"
                          : "text-muted-foreground hover:text-white"
                      }`}
                    >
                      Markdown Source
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditorTab("preview")}
                      className={`px-3 py-1 text-xs font-bold rounded-md transition-colors ${
                        editorTab === "preview"
                          ? "bg-accent text-white"
                          : "text-muted-foreground hover:text-white"
                      }`}
                    >
                      Formatted Preview
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {editorTab === "write" ? (
                  <Textarea
                    rows={18}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    className="font-mono text-xs leading-relaxed"
                  />
                ) : (
                  <div className="p-4 rounded-xl bg-background border border-border prose prose-invert max-w-none text-xs leading-relaxed whitespace-pre-wrap font-sans">
                    {content}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Attached Reference Files */}
            {playbook.files && playbook.files.length > 0 && (
              <Card className="border-border bg-surface p-4">
                <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <FileText className="h-4 w-4 text-accent" />
                  Attached Reference Files
                </h4>
                <div className="divide-y divide-border/40">
                  {playbook.files.map((file) => (
                    <div key={file.id} className="py-2 flex items-center justify-between text-xs">
                      <span className="font-mono text-white">{file.filename}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {formatDate(file.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </TabsContent>

          {/* Versions Tab */}
          <TabsContent value="history" className="pt-2">
            <Card className="border-border bg-surface">
              <CardHeader>
                <CardTitle className="text-base">Version History & Rollbacks</CardTitle>
                <CardDescription>
                  Every change to this playbook is versioned. Roll back anytime with one click.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {playbook.versions && playbook.versions.length > 0 ? (
                  <div className="divide-y divide-border/50">
                    {playbook.versions.map((ver) => (
                      <div key={ver.id} className="py-3 flex items-center justify-between">
                        <div>
                          <div className="font-bold text-white text-sm">
                            Version #{ver.version_number}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {ver.change_summary || "Playbook content update"} • {formatDate(ver.created_at)}
                          </div>
                        </div>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRollback(ver.version_number)}
                          className="h-8 text-xs gap-1"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Rollback
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center text-xs text-muted-foreground">
                    Initial version #1 is currently active.
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Test Bench Tab */}
          <TabsContent value="testbench" className="pt-2 space-y-4">
            <Card className="border-border bg-surface">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Play className="h-4 w-4 text-emerald-400" />
                  Playbook Test Bench
                </CardTitle>
                <CardDescription>
                  Simulate LLM scoring and rule matching against sample stream dialogue or chat text.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="sample-text">Sample Stream Transcript / Chat Fragment</Label>
                  <Textarea
                    id="sample-text"
                    rows={4}
                    value={sampleText}
                    onChange={(e) => setSampleText(e.target.value)}
                    className="font-mono text-xs"
                  />
                </div>

                <Button
                  onClick={handleRunTestBench}
                  isLoading={isTesting}
                  className="gap-2 font-bold bg-emerald-600 hover:bg-emerald-500 text-white"
                >
                  <Play className="h-4 w-4" />
                  Evaluate Ruleset
                </Button>

                {testResult && (
                  <div className="p-4 rounded-xl bg-background border border-border space-y-3 pt-3">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Evaluation Result:
                    </h4>

                    {/* Applied Rules */}
                    {testResult.rules_applied && testResult.rules_applied.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Rules Applied & Matched:
                        </span>
                        <ul className="list-disc list-inside text-xs text-gray-300 space-y-0.5">
                          {testResult.rules_applied.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Violations */}
                    {testResult.rule_violations && testResult.rule_violations.length > 0 ? (
                      <div className="space-y-1 pt-2">
                        <span className="text-xs font-semibold text-rose-400 flex items-center gap-1">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          Rule Violations Detected:
                        </span>
                        <ul className="list-disc list-inside text-xs text-rose-300 space-y-0.5">
                          {testResult.rule_violations.map((v, i) => (
                            <li key={i}>{v}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="text-xs text-emerald-400 font-medium">
                        ✓ No hard rule violations detected.
                      </div>
                    )}

                    {/* Summary */}
                    {testResult.analysis && (
                      <p className="text-xs text-gray-400 border-t border-border/50 pt-2 italic">
                        {testResult.analysis}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Upload Reference Modal */}
        <Dialog open={isUploadOpen} onOpenChange={setIsUploadOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Upload Playbook Reference</DialogTitle>
              <DialogDescription>
                Upload markdown files, guideline texts, or JSON examples to include in the context.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleFileUpload} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="file-input">Select Document (.md, .txt, .json)</Label>
                <Input
                  id="file-input"
                  type="file"
                  accept=".md,.txt,.json"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  required
                />
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsUploadOpen(false)}
                  disabled={isUploading}
                >
                  Cancel
                </Button>
                <Button type="submit" isLoading={isUploading}>
                  Upload File
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
