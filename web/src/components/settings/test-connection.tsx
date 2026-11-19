"use client";

import * as React from "react";
import { CheckCircle2, XCircle, RefreshCw } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface TestConnectionProps {
  keyId?: number;
  onTest?: () => Promise<any>;
}

export function TestConnection({ keyId, onTest }: TestConnectionProps) {
  const [testing, setTesting] = React.useState(false);
  const [result, setResult] = React.useState<{
    success?: boolean;
    message?: string;
  } | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      if (onTest) {
        const res = await onTest();
        setResult({ success: true, message: res?.message || "Connected" });
      } else if (keyId) {
        const res = await api.settings.testKey(keyId);
        setResult({ success: res.success, message: res.message || "Connected" });
      }
    } catch (err: any) {
      setResult({
        success: false,
        message: err.message || "Connection test failed",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={testing}
        onClick={handleTest}
        className="h-8 text-xs gap-1.5"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${testing ? "animate-spin text-accent" : ""}`} />
        <span>Test Connection</span>
      </Button>

      {result && (
        <div
          className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md ${
            result.success
              ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/30"
              : "text-rose-400 bg-rose-500/10 border border-rose-500/30"
          }`}
        >
          {result.success ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <XCircle className="h-3.5 w-3.5 shrink-0" />
          )}
          <span className="truncate max-w-[140px]">{result.message}</span>
        </div>
      )}
    </div>
  );
}
