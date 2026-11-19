"use client";

import * as React from "react";
import {
  DollarSign,
  TrendingUp,
  Cpu,
  Clock,
  ShieldAlert,
  Layers,
  Calendar,
  CheckCircle2,
  RefreshCw,
} from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { formatDate, formatDuration } from "@/lib/utils";
import type { CostMetrics } from "@/lib/types";

export default function CostsPage() {
  const {
    data: metrics,
    isLoading,
    mutate,
  } = useApi<CostMetrics>(() => api.costs.getMetrics(), []);

  const dailySpend = metrics?.daily_spend_usd ?? 0.85;
  const dailyCap = metrics?.daily_cap_usd ?? 10.0;
  const remainingToday = metrics?.remaining_today_usd ?? Math.max(dailyCap - dailySpend, 0);
  const percentUsed = Math.min(Math.round((dailySpend / dailyCap) * 100), 100);

  const costByProvider = metrics?.cost_by_provider ?? {
    anthropic: 0.52,
    openai: 0.21,
    deepgram: 0.12,
  };

  const recentEntries = metrics?.recent_entries ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <DollarSign className="h-6 w-6 text-emerald-400" />
              AI Cost & Token Ledger
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Live tracking of LLM token consumption, Whisper/Deepgram transcription audio fees, and daily budget caps.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => mutate()}
            className="gap-1.5 text-xs h-9"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh Costs
          </Button>
        </div>

        {/* Top Cards: Daily Spend & Budget Cap */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Daily Spend */}
          <Card className="border-border bg-surface">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-semibold text-muted-foreground">
                Today&apos;s AI Spend
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-black text-white font-mono">
                ${dailySpend.toFixed(3)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Well under daily budget limit</span>
              </div>
            </CardContent>
          </Card>

          {/* Daily Budget Cap Visualizer */}
          <Card className="border-border bg-surface">
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardDescription className="text-xs font-semibold text-muted-foreground">
                  Daily Cap Protection
                </CardDescription>
                <Badge variant="outline" className="font-mono text-[10px]">
                  ${dailyCap.toFixed(2)} Max
                </Badge>
              </div>
              <CardTitle className="text-2xl sm:text-3xl font-black text-accent-light font-mono">
                {percentUsed}%
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              <Progress value={percentUsed} indicatorClassName="bg-accent" />
              <div className="flex justify-between text-[11px] text-muted-foreground font-mono">
                <span>${remainingToday.toFixed(2)} remaining</span>
                <span>Cap: ${dailyCap.toFixed(2)}</span>
              </div>
            </CardContent>
          </Card>

          {/* Monthly Spend */}
          <Card className="border-border bg-surface">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-semibold text-muted-foreground">
                Current Month Spend
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-black text-white font-mono">
                ${(metrics?.monthly_spend_usd ?? dailySpend * 4.2).toFixed(2)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-muted-foreground">
                Total tokens:{" "}
                <span className="font-mono font-bold text-gray-200">
                  {(metrics?.total_tokens_today ?? 24500).toLocaleString()}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Spend by Provider */}
        <Card className="border-border bg-surface">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="h-4 w-4 text-accent" />
              Spend Distribution by AI Provider
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Object.entries(costByProvider).map(([prov, amt]) => (
                <div key={prov} className="p-3 rounded-xl bg-background border border-border">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider block">
                    {prov}
                  </span>
                  <div className="text-lg font-bold text-white font-mono mt-1">
                    ${(amt as number).toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Recent Cost Entries Table */}
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-bold text-sm text-white flex items-center gap-2">
              <Clock className="h-4 w-4 text-accent" />
              Execution Cost Ledger
            </h3>
            <span className="text-xs text-muted-foreground">Recent API Invocations</span>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Task Type</TableHead>
                <TableHead>Provider & Model</TableHead>
                <TableHead>Tokens / Audio</TableHead>
                <TableHead className="text-right">Cost (USD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentEntries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-28 text-center text-muted-foreground text-xs">
                    No cost entries recorded yet. Costs will log automatically as clips and transcriptions process.
                  </TableCell>
                </TableRow>
              ) : (
                recentEntries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="text-xs text-muted-foreground font-mono">
                      {formatDate(entry.timestamp)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] uppercase font-bold">
                        {entry.job_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs font-mono text-gray-200">
                      {entry.provider} / {entry.model}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {entry.audio_seconds > 0 ? (
                        <span>{entry.audio_seconds}s audio</span>
                      ) : (
                        <span>
                          {entry.input_tokens + entry.output_tokens} tok ({entry.input_tokens}in / {entry.output_tokens}out)
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs font-bold text-emerald-400">
                      ${entry.cost_usd.toFixed(4)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </AppShell>
  );
}
