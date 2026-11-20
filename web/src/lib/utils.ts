import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num?: number | null): string {
  if (num === null || num === undefined) return '0';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return num.toLocaleString();
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return '0:00';
  const sec = Math.round(seconds);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}:${remM.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 5) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.floor(diffHour / 24);
    return `${diffDay}d ago`;
  } catch {
    return dateString;
  }
}

export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

export function getHypeColor(score: number): {
  text: string;
  bg: string;
  border: string;
  hex: string;
} {
  if (score >= 65) {
    return {
      text: 'text-rose-400',
      bg: 'bg-rose-500/15',
      border: 'border-rose-500/40',
      hex: '#EF4444',
    };
  }
  if (score >= 40) {
    return {
      text: 'text-amber-400',
      bg: 'bg-amber-500/15',
      border: 'border-amber-500/40',
      hex: '#F59E0B',
    };
  }
  return {
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-500/40',
    hex: '#10B981',
  };
}

export function detectPlatformFromUrl(url: string): {
  platform: 'twitch' | 'kick' | 'youtube' | null;
  extractedName?: string;
} {
  try {
    const clean = url.trim().toLowerCase();
    if (clean.includes('twitch.tv/')) {
      const match = clean.match(/twitch\.tv\/([a-zA-Z0-9_]+)/);
      return { platform: 'twitch', extractedName: match ? match[1] : undefined };
    }
    if (clean.includes('kick.com/')) {
      const match = clean.match(/kick\.com\/([a-zA-Z0-9_]+)/);
      return { platform: 'kick', extractedName: match ? match[1] : undefined };
    }
    if (clean.includes('youtube.com/') || clean.includes('youtu.be/')) {
      let name: string | undefined;
      const channelMatch =
        clean.match(/youtube\.tv\/@([a-zA-Z0-9_.-]+)/) ||
        clean.match(/youtube\.com\/@([a-zA-Z0-9_.-]+)/);
      if (channelMatch) name = channelMatch[1];
      return { platform: 'youtube', extractedName: name };
    }
    return { platform: null };
  } catch {
    return { platform: null };
  }
}

export function getMediaUrl(path?: string | null): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("blob:") || path.startsWith("data:")) {
    return path;
  }
  const envUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const isRemote =
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1";
  const baseUrl =
    isRemote && (envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))
      ? ""
      : envUrl;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${cleanPath}`;
}
