/**
 * API client with automatic token injection, refresh token retry on 401,
 * and strongly-typed endpoints for ClipDeck backend (Phase 1 & Phase 2).
 */

import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  isBrowser,
} from "./auth";
import type {
  Streamer,
  StreamerCreate,
  StreamSession,
  ChatStatsBucket,
  Moment,
  MomentStatus,
  Job,
  Setting,
  ProviderKey,
  HealthInfo,
  User,
  LoginResponse,
  TOTPSetupResponse,
  Clip,
  Playbook,
  PlaybookCreate,
  PromptTemplate,
  LayoutPreset,
  CostMetrics,
  EditDecisionList,
  ThumbnailResponse,
  ThumbnailListItem,
  GenerateThumbnailRequest,
} from "./types";

export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || "";
  if (isBrowser()) {
    const isRemote =
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1";
    // If running in browser on a remote domain (e.g. *.netlify.app), do not attempt to contact localhost
    if (isRemote && (envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))) {
      return "";
    }
  }
  return envUrl;
}

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: any) => void;
  reject: (reason?: any) => void;
}> = [];

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export async function apiFetch<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${getApiBaseUrl()}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    const signal = options.signal || (typeof AbortSignal !== "undefined" && "timeout" in AbortSignal ? AbortSignal.timeout(15000) : undefined);
    response = await fetch(url, {
      ...options,
      signal,
      headers,
    });
  } catch (err: any) {
    if (err.name === "TimeoutError") {
      throw new ApiError(0, "Request timed out. Please check that the backend server is reachable.");
    }
    throw new ApiError(0, err.message || "Network error. Please check your connection.");
  }

  // Handle 401 Unauthorized with token refresh (except for /api/auth/login and /api/auth/refresh)
  if (
    response.status === 401 &&
    !endpoint.includes("/api/auth/login") &&
    !endpoint.includes("/api/auth/refresh")
  ) {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      clearTokens();
      if (isBrowser() && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired. Please log in again.");
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((newToken) => {
          headers.set("Authorization", `Bearer ${newToken}`);
          return apiFetch<T>(endpoint, { ...options, headers });
        })
        .catch((err) => {
          return Promise.reject(err);
        });
    }

    isRefreshing = true;

    try {
      const refreshRes = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!refreshRes.ok) {
        throw new Error("Refresh token expired");
      }

      const refreshData = await refreshRes.json();
      setTokens(refreshData.access_token, refreshData.refresh_token);
      processQueue(null, refreshData.access_token);

      headers.set("Authorization", `Bearer ${refreshData.access_token}`);
      return apiFetch<T>(endpoint, { ...options, headers });
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      clearTokens();
      if (isBrowser() && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired. Please log in again.");
    } finally {
      isRefreshing = false;
    }
  }

  if (!response.ok) {
    let errorDetail = "Request failed";
    let data: any = null;
    try {
      data = await response.json();
      errorDetail = data.detail || data.message || JSON.stringify(data);
    } catch {
      errorDetail = response.statusText || `HTTP Error ${response.status}`;
    }
    throw new ApiError(response.status, errorDetail, data);
  }

  if (response.status === 204) {
    return {} as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    return {} as T;
  }
}

// ---------------------------------------------------------------------------
// Typed API Endpoints
// ---------------------------------------------------------------------------

export const api = {
  // Auth
  auth: {
    login: (username: string, password: string, totp_code?: string) =>
      apiFetch<LoginResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password, totp_code }),
      }),
    me: () => apiFetch<User>("/api/auth/me"),
    changePassword: (current_password: string, new_password: string) =>
      apiFetch<{ message: string }>("/api/auth/password", {
        method: "PUT",
        body: JSON.stringify({ current_password, new_password }),
      }),
    setupTotp: () => apiFetch<TOTPSetupResponse>("/api/auth/totp/setup", { method: "POST" }),
    verifyTotp: (code: string) =>
      apiFetch<{ message: string }>("/api/auth/totp/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
  },

  // Streamers
  streamers: {
    list: () => apiFetch<Streamer[]>("/api/streamers"),
    get: (id: number) => apiFetch<Streamer>(`/api/streamers/${id}`),
    create: (data: StreamerCreate) =>
      apiFetch<Streamer>("/api/streamers", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<StreamerCreate>) =>
      apiFetch<Streamer>(`/api/streamers/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      apiFetch<{ message: string }>(`/api/streamers/${id}`, {
        method: "DELETE",
      }),
    clipNow: (id: number, duration: number = 60) =>
      apiFetch<{ message: string; job_id?: number }>(`/api/streamers/${id}/clip-now`, {
        method: "POST",
        body: JSON.stringify({ duration }),
      }),
  },

  // Moments
  moments: {
    list: (params?: {
      streamer_id?: number;
      status?: string;
      limit?: number;
      offset?: number;
    }) => {
      const query = new URLSearchParams();
      if (params?.streamer_id) query.set("streamer_id", String(params.streamer_id));
      if (params?.status) query.set("status", params.status);
      if (params?.limit) query.set("limit", String(params.limit));
      if (params?.offset) query.set("offset", String(params.offset));
      const qs = query.toString();
      return apiFetch<Moment[]>(`/api/moments${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => apiFetch<Moment>(`/api/moments/${id}`),
    updateStatus: (id: number, status: MomentStatus) =>
      apiFetch<Moment>(`/api/moments/${id}/status`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      }),
    runAiEdit: (id: number) =>
      apiFetch<{ message: string; job_id?: number; clip_id?: number }>(`/api/moments/${id}/ai-edit`, {
        method: "POST",
      }),
  },

  // Clips (Phase 2)
  clips: {
    list: (params?: { streamer_id?: number; status?: string; limit?: number }) => {
      const query = new URLSearchParams();
      if (params?.streamer_id) query.set("streamer_id", String(params.streamer_id));
      if (params?.status) query.set("status", params.status);
      if (params?.limit) query.set("limit", String(params.limit));
      const qs = query.toString();
      return apiFetch<Clip[]>(`/api/clips${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => apiFetch<Clip>(`/api/clips/${id}`),
    create: (data: { moment_id: number; edl?: EditDecisionList }) =>
      apiFetch<Clip>("/api/clips", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    rerender: (id: number, edl?: EditDecisionList) =>
      apiFetch<{ message: string; job_id: number }>(`/api/clips/${id}/rerender`, {
        method: "POST",
        body: JSON.stringify({ edl }),
      }),
  },

  // Playbooks (Phase 2)
  playbooks: {
    list: (scope?: string) => {
      const qs = scope ? `?scope=${scope}` : "";
      return apiFetch<Playbook[]>(`/api/playbooks${qs}`);
    },
    get: (id: number) => apiFetch<Playbook>(`/api/playbooks/${id}`),
    create: (data: PlaybookCreate) =>
      apiFetch<Playbook>("/api/playbooks", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<PlaybookCreate>) =>
      apiFetch<Playbook>(`/api/playbooks/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      apiFetch<{ message: string }>(`/api/playbooks/${id}`, {
        method: "DELETE",
      }),
    rollback: (id: number, versionNumber: number) =>
      apiFetch<Playbook>(`/api/playbooks/${id}/rollback`, {
        method: "POST",
        body: JSON.stringify({ version_number: versionNumber }),
      }),
    uploadFile: (id: number, formData: FormData) =>
      apiFetch<{ message: string; filename: string }>(`/api/playbooks/${id}/files`, {
        method: "POST",
        body: formData,
      }),
    testBench: (id: number, sampleText: string) =>
      apiFetch<{ rules_applied: string[]; rule_violations: string[]; analysis: string }>(
        `/api/playbooks/${id}/test`,
        {
          method: "POST",
          body: JSON.stringify({ sample_text: sampleText }),
        }
      ),
  },

  // Templates (Phase 2)
  templates: {
    list: () => apiFetch<PromptTemplate[]>("/api/templates"),
    get: (id: number) => apiFetch<PromptTemplate>(`/api/templates/${id}`),
    update: (id: number, data: Partial<PromptTemplate>) =>
      apiFetch<PromptTemplate>(`/api/templates/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
  },

  // Presets (Phase 2)
  presets: {
    list: (streamerId?: number) => {
      const qs = streamerId ? `?streamer_id=${streamerId}` : "";
      return apiFetch<LayoutPreset[]>(`/api/presets${qs}`);
    },
    create: (data: Partial<LayoutPreset>) =>
      apiFetch<LayoutPreset>("/api/presets", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<LayoutPreset>) =>
      apiFetch<LayoutPreset>(`/api/presets/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      apiFetch<{ message: string }>(`/api/presets/${id}`, {
        method: "DELETE",
      }),
  },

  // Costs (Phase 2)
  costs: {
    getMetrics: () => apiFetch<CostMetrics>("/api/costs"),
  },

  // Sessions
  sessions: {
    list: (streamerId?: number) => {
      const qs = streamerId ? `?streamer_id=${streamerId}` : "";
      return apiFetch<StreamSession[]>(`/api/sessions${qs}`);
    },
    get: (id: number) => apiFetch<StreamSession>(`/api/sessions/${id}`),
    getStats: (sessionId: number, limit: number = 60) =>
      apiFetch<ChatStatsBucket[]>(`/api/sessions/${sessionId}/stats?limit=${limit}`),
  },

  // Jobs
  jobs: {
    list: (params?: { status?: string; queue?: string; limit?: number }) => {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      if (params?.queue) query.set("queue", params.queue);
      if (params?.limit) query.set("limit", String(params.limit));
      const qs = query.toString();
      return apiFetch<Job[]>(`/api/jobs${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => apiFetch<Job>(`/api/jobs/${id}`),
    retry: (id: number) =>
      apiFetch<{ message: string }>(`/api/jobs/${id}/retry`, { method: "POST" }),
    cancel: (id: number) =>
      apiFetch<{ message: string }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  },

  // Settings
  settings: {
    get: () => apiFetch<Setting[]>("/api/settings"),
    update: (settings: Record<string, any>) =>
      apiFetch<Setting[]>("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ settings }),
      }),
    getKeys: () => apiFetch<ProviderKey[]>("/api/settings/keys"),
    createKey: (provider: string, key_name: string, value: string) =>
      apiFetch<ProviderKey>("/api/settings/keys", {
        method: "POST",
        body: JSON.stringify({ provider, key_name, value }),
      }),
    updateKey: (keyId: number, value: string) =>
      apiFetch<ProviderKey>(`/api/settings/keys/${keyId}`, {
        method: "PUT",
        body: JSON.stringify({ value }),
      }),
    deleteKey: (keyId: number) =>
      apiFetch<{ message: string }>(`/api/settings/keys/${keyId}`, {
        method: "DELETE",
      }),
    testKey: (keyId: number) =>
      apiFetch<{ success: boolean; message?: string; error?: string }>(
        `/api/settings/keys/${keyId}/test`,
        { method: "POST" }
      ),
  },

  // Health
  health: {
    get: () => apiFetch<HealthInfo>("/api/health"),
  },

  // Vertical Thumbnails (GTA VI Style)
  thumbnails: {
    list: (limit: number = 50) =>
      apiFetch<ThumbnailListItem[]>(`/api/thumbnails?limit=${limit}`),
    generate: (params: GenerateThumbnailRequest) =>
      apiFetch<ThumbnailResponse>("/api/thumbnails/generate", {
        method: "POST",
        body: JSON.stringify(params),
      }),
    autoGenerateForClip: (clipId: number, mode: "cinematic" | "split" = "cinematic") =>
      apiFetch<ThumbnailResponse>(
        `/api/thumbnails/clips/${clipId}/auto-thumbnail?mode=${mode}`,
        { method: "POST" }
      ),
  },
};
