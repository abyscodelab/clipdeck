"use client";

import * as React from "react";
import { Filter, RotateCcw } from "@/components/icons";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { Streamer } from "@/lib/types";

export interface MomentFilterValues {
  streamerId?: number;
  status?: string;
  triggerType?: string;
  sortBy?: "date" | "hype";
}

interface MomentFiltersProps {
  streamers: Streamer[];
  values: MomentFilterValues;
  onChange: (vals: MomentFilterValues) => void;
  onReset: () => void;
}

export function MomentFilters({
  streamers,
  values,
  onChange,
  onReset,
}: MomentFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 p-4 rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider shrink-0">
        <Filter className="h-3.5 w-3.5 text-accent" />
        <span>Filters</span>
      </div>

      <div className="grid grid-cols-2 sm:flex sm:flex-1 gap-2.5">
        {/* Streamer Filter */}
        <div className="w-full sm:w-44">
          <Select
            value={values.streamerId ? String(values.streamerId) : ""}
            onChange={(e) =>
              onChange({
                ...values,
                streamerId: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          >
            <option value="">All Streamers</option>
            {streamers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>

        {/* Status Filter */}
        <div className="w-full sm:w-36">
          <Select
            value={values.status || ""}
            onChange={(e) =>
              onChange({
                ...values,
                status: e.target.value || undefined,
              })
            }
          >
            <option value="">All Statuses</option>
            <option value="detected">Detected</option>
            <option value="clipping">Clipping</option>
            <option value="clipped">Clipped</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>

        {/* Trigger Type Filter */}
        <div className="w-full sm:w-32">
          <Select
            value={values.triggerType || ""}
            onChange={(e) =>
              onChange({
                ...values,
                triggerType: e.target.value || undefined,
              })
            }
          >
            <option value="">All Triggers</option>
            <option value="auto">Auto Spike</option>
            <option value="manual">Manual Clip</option>
          </Select>
        </div>

        {/* Sort */}
        <div className="w-full sm:w-36">
          <Select
            value={values.sortBy || "date"}
            onChange={(e) =>
              onChange({
                ...values,
                sortBy: e.target.value as "date" | "hype",
              })
            }
          >
            <option value="date">Sort: Newest</option>
            <option value="hype">Sort: Hype Score</option>
          </Select>
        </div>
      </div>

      {/* Reset */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onReset}
        title="Reset Filters"
        className="h-10 px-3 text-xs text-muted-foreground hover:text-white shrink-0 self-end sm:self-center"
      >
        <RotateCcw className="h-3.5 w-3.5 mr-1" />
        Reset
      </Button>
    </div>
  );
}
