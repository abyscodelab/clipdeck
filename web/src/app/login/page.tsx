"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Flame, Lock, User, KeyRound, ShieldCheck, ArrowRight } from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/components/ui/toast";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();
  const { toast } = useToast();

  const [username, setUsername] = React.useState("admin");
  const [password, setPassword] = React.useState("");
  const [totpCode, setTotpCode] = React.useState("");
  const [showTotpField, setShowTotpField] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const res = await login(
        username.trim(),
        password,
        showTotpField ? totpCode.trim() : undefined
      );

      toast({
        title: "Welcome to ClipDeck",
        message: "Authenticated successfully.",
        type: "success",
      });

      router.push("/dashboard");
    } catch (err: any) {
      const msg = err.message || "Login failed";
      // Check if server rejected because TOTP code is required
      if (
        msg.toLowerCase().includes("totp") ||
        msg.toLowerCase().includes("two-factor") ||
        msg.toLowerCase().includes("2fa")
      ) {
        setShowTotpField(true);
        setError("Two-Factor Authentication is enabled. Please enter your 6-digit TOTP code.");
      } else {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center p-4 bg-[#0D0D0D] relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-white/[0.03] rounded-full blur-3xl pointer-events-none" />

      <Card className="w-full max-w-sm border-border bg-[#161616] shadow-2xl relative z-10 rounded-2xl">
        <CardHeader className="space-y-2 text-center pb-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-white border border-white/10 mb-2">
            <Flame className="h-6 w-6 fill-white" />
          </div>
          <CardTitle className="text-xl font-bold tracking-tight text-white">
            ClipDeck
          </CardTitle>
          <CardDescription className="text-neutral-400 text-xs">
            Personal Live-Stream Moment Detection & DVR Clipping
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                {error}
              </div>
            )}

            {/* Username */}
            <div className="space-y-1.5">
              <Label htmlFor="login-username" className="text-xs text-neutral-300">Username</Label>
              <div className="relative">
                <Input
                  id="login-username"
                  placeholder="admin"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus={!username}
                  className="pl-9 bg-[#121212]"
                />
                <User className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-neutral-500" />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label htmlFor="login-password" className="text-xs text-neutral-300">Password</Label>
              <div className="relative">
                <Input
                  id="login-password"
                  type="password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="pl-9 bg-[#121212]"
                />
                <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-neutral-500" />
              </div>
            </div>

            {/* TOTP 2FA Field if prompted */}
            {showTotpField && (
              <div className="space-y-1.5 animate-in fade-in slide-in-from-top-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-totp" className="text-xs text-neutral-300 flex items-center gap-1">
                    <ShieldCheck className="h-3.5 w-3.5 text-neutral-400" />
                    Two-Factor Authentication Code
                  </Label>
                </div>
                <div className="relative">
                  <Input
                    id="login-totp"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="123456"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    required
                    autoFocus
                    className="pl-9 font-mono tracking-widest text-base bg-[#121212]"
                  />
                  <KeyRound className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-neutral-500" />
                </div>
              </div>
            )}

            <Button
              type="submit"
              size="lg"
              className="w-full h-11 bg-white hover:bg-neutral-200 text-neutral-950 font-semibold gap-2 mt-2 rounded-xl text-sm"
              isLoading={isLoading}
            >
              <span>{showTotpField ? "Verify & Sign In" : "Sign In to Dashboard"}</span>
              <ArrowRight className="h-4 w-4" />
            </Button>

            <div className="text-center pt-2">
              <p className="text-[11px] text-neutral-500">
                First time setup? Use <code className="text-neutral-300 font-mono">admin / changeme</code>
              </p>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
