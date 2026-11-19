"use client";

import * as React from "react";
import { ApiError } from "@/lib/api";

interface UseApiOptions<T> {
  initialData?: T;
  enabled?: boolean;
  refreshInterval?: number;
  onSuccess?: (data: T) => void;
  onError?: (err: any) => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: any[] = [],
  options: UseApiOptions<T> = {}
) {
  const {
    initialData,
    enabled = true,
    refreshInterval,
    onSuccess,
    onError,
  } = options;

  const [data, setData] = React.useState<T | undefined>(initialData);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState<boolean>(enabled && initialData === undefined);
  const [isValidating, setIsValidating] = React.useState<boolean>(false);

  const fetcherRef = React.useRef(fetcher);
  fetcherRef.current = fetcher;

  const execute = React.useCallback(async (isBackground = false) => {
    if (!enabled) return;
    if (isBackground) {
      setIsValidating(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const result = await fetcherRef.current();
      setData(result);
      onSuccess?.(result);
      return result;
    } catch (err: any) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err?.message || "An unexpected error occurred";
      setError(msg);
      onError?.(err);
    } finally {
      setIsLoading(false);
      setIsValidating(false);
    }
  }, [enabled, onSuccess, onError]);

  React.useEffect(() => {
    execute();
  }, [execute, ...deps]);

  React.useEffect(() => {
    if (!refreshInterval || !enabled) return;
    const interval = setInterval(() => {
      execute(true);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, enabled, execute]);

  return {
    data,
    error,
    isLoading,
    isValidating,
    mutate: execute,
    setData,
  };
}
