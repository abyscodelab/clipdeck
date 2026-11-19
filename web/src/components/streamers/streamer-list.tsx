"use client";

import * as React from "react";
import Link from "next/link";
import { Radio, Edit2, Trash2, Scissors, ExternalLink, ShieldCheck } from "@/components/icons";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Avatar } from "@/components/ui/avatar";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Streamer } from "@/lib/types";

interface StreamerListProps {
  streamers: Streamer[];
  onToggleMonitor: (streamer: Streamer) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onClipNow: (streamerId: number, duration: number) => Promise<any>;
}

export function StreamerList({
  streamers,
  onToggleMonitor,
  onDelete,
  onClipNow,
}: StreamerListProps) {
  const [deleteId, setDeleteId] = React.useState<number | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const confirmDelete = async () => {
    if (!deleteId) return;
    setIsDeleting(true);
    try {
      await onDelete(deleteId);
      setDeleteId(null);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Streamer</TableHead>
            <TableHead>Platform</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Auto-Monitor</TableHead>
            <TableHead>Relationship</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {streamers.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                No streamers configured yet. Click &quot;Add Streamer&quot; to get started.
              </TableCell>
            </TableRow>
          ) : (
            streamers.map((st) => {
              const platformVariant = {
                twitch: "twitch",
                kick: "kick",
                youtube: "youtube",
              }[st.platform] as "twitch" | "kick" | "youtube";

              return (
                <TableRow key={st.id}>
                  {/* Streamer Avatar & Name */}
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar fallback={st.name} size="sm" />
                      <div className="flex flex-col">
                        <Link
                          href={`/streamers/${st.id}`}
                          className="font-bold text-white hover:text-accent-light transition-colors flex items-center gap-1.5"
                        >
                          {st.name}
                        </Link>
                        {st.niche && (
                          <span className="text-xs text-muted-foreground">{st.niche}</span>
                        )}
                      </div>
                    </div>
                  </TableCell>

                  {/* Platform */}
                  <TableCell>
                    <Badge variant={platformVariant} className="text-[10px] uppercase font-bold py-0.5">
                      {st.platform}
                    </Badge>
                  </TableCell>

                  {/* Status */}
                  <TableCell>
                    {st.is_live ? (
                      <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold">
                        <span className="h-2 w-2 rounded-full bg-live animate-live" />
                        LIVE
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Offline</span>
                    )}
                  </TableCell>

                  {/* Auto-Monitor Toggle */}
                  <TableCell>
                    <Switch
                      checked={st.auto_monitor}
                      onCheckedChange={() => onToggleMonitor(st)}
                    />
                  </TableCell>

                  {/* Relationship */}
                  <TableCell>
                    <Badge variant="outline" className="text-xs capitalize">
                      {st.relationship_type.replace("_", " ")}
                    </Badge>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {st.is_live && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onClipNow(st.id, 60)}
                          title="Instant Clip (60s)"
                          className="h-8 w-8 text-accent hover:text-accent-light hover:bg-accent/15"
                        >
                          <Scissors className="h-4 w-4" />
                        </Button>
                      )}
                      <Link href={`/streamers/${st.id}`}>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Edit Streamer"
                          className="h-8 w-8 text-muted-foreground hover:text-white"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteId(st.id)}
                        title="Delete Streamer"
                        className="h-8 w-8 text-muted-foreground hover:text-rose-400"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteId !== null} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove Streamer?</DialogTitle>
            <DialogDescription>
              Are you sure you want to stop monitoring this streamer? Their historical moments will remain preserved.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setDeleteId(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              isLoading={isDeleting}
              onClick={confirmDelete}
            >
              Delete Streamer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
