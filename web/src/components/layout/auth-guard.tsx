"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { Lock, ShieldAlert } from "@/components/icons";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, mustChangePassword, changePassword } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { toast } = useToast();

  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [isChanging, setIsChanging] = React.useState(false);
  const [changeError, setChangeError] = React.useState("");
  const [dismissModal, setDismissModal] = React.useState(false);

  React.useEffect(() => {
    if (!isLoading && !isAuthenticated && pathname !== "/login") {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangeError("");

    if (newPassword.length < 8) {
      setChangeError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setChangeError("Passwords do not match");
      return;
    }

    setIsChanging(true);
    try {
      await changePassword(currentPassword, newPassword);
      toast({
        title: "Password Updated",
        message: "Your default password has been updated successfully.",
        type: "success",
      });
    } catch (err: any) {
      setChangeError(err.message || "Failed to change password");
    } finally {
      setIsChanging(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background p-6">
        <div className="w-full max-w-md space-y-4">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
          <div className="flex gap-3">
            <Skeleton className="h-10 w-1/2 rounded-lg" />
            <Skeleton className="h-10 w-1/2 rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated && pathname !== "/login") {
    return null;
  }

  return (
    <>
      {children}

      {/* Force Change Password Modal */}
      {mustChangePassword && !dismissModal && pathname !== "/login" && (
        <Dialog open={true}>
          <DialogContent className="sm:max-w-md border-amber-500/30">
            <DialogHeader>
              <div className="flex items-center gap-2 text-amber-400 mb-1">
                <ShieldAlert className="h-5 w-5" />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Security Reminder
                </span>
              </div>
              <DialogTitle>Update Default Password</DialogTitle>
              <DialogDescription>
                You are currently using the default administrator credentials. Set a new password or continue with your current password.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              {changeError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                  {changeError}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="curr-pwd" required>Current Password</Label>
                <Input
                  id="curr-pwd"
                  type="password"
                  placeholder="changeme"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="new-pwd" required>New Password (min 8 chars)</Label>
                <Input
                  id="new-pwd"
                  type="password"
                  placeholder="••••••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirm-pwd" required>Confirm New Password</Label>
                <Input
                  id="confirm-pwd"
                  type="password"
                  placeholder="••••••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>

              <DialogFooter className="flex-col sm:flex-row gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full sm:w-auto"
                  onClick={() => setDismissModal(true)}
                >
                  Keep Current Password & Enter
                </Button>
                <Button type="submit" className="w-full sm:w-auto flex-1" isLoading={isChanging}>
                  Update Password & Enter
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
