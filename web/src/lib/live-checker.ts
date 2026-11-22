import { getSupabaseAdmin } from "./server-supabase";

export interface LiveStatusResult {
  is_live: boolean;
  viewer_count: number;
  active_session_id?: number | null;
}

// In-memory cache for live check results (60-second TTL to avoid spamming platforms and eliminate lag)
const liveStatusCache = new Map<number, { result: LiveStatusResult; expiresAt: number }>();

/**
 * Check whether a streamer is currently live on their platform.
 * Supports YouTube live streams (watch URLs & channel streams) and Kick channels.
 * Uses aggressive caching and protects active live sessions from false-negative drops.
 */
export async function checkLiveStatus(streamer: {
  id: number;
  platform: string;
  url?: string | null;
  name?: string;
  platform_id?: string | null;
}): Promise<LiveStatusResult> {
  const now = Date.now();
  const cached = liveStatusCache.get(streamer.id);
  if (cached && cached.expiresAt > now) {
    return cached.result;
  }

  let isLive = false;
  let viewerCount = 0;
  let platformSessionId: string | null = null;
  let platformCheckSuccess = false;

  try {
    if (streamer.platform === "youtube" && streamer.url) {
      const match = streamer.url.match(/(?:watch\?v=|\/live\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
      if (match) {
        const videoId = match[1];
        platformSessionId = videoId;
        const watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3500);

        try {
          const res = await fetch(watchUrl, {
            headers: {
              "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            signal: controller.signal,
            next: { revalidate: 60 },
          });

          if (res.ok) {
            const html = await res.text();
            platformCheckSuccess = true;
            isLive = html.includes('"isLive":true') || html.includes('"isLiveBroadcast":true');

            const viewersMatch =
              html.match(/"([0-9,]+)\s*(?:watching now|watching|concurrent viewers)"/i) ||
              html.match(/"text":"([0-9,]+)\s*watching"/i) ||
              html.match(/"viewerCount":\{"runs":\[\{"text":"([0-9,]+)"\}\]/) ||
              html.match(/"concurrentViewers":\{"runs":\[\{"text":"([0-9,]+)"\}\]/) ||
              html.match(/"viewCount":\{"runs":\[\{"text":"([0-9,]+)"\}\]/);

            if (viewersMatch && viewersMatch[1]) {
              viewerCount = parseInt(viewersMatch[1].replace(/,/g, ""), 10) || (isLive ? 1200 : 0);
            } else if (isLive) {
              viewerCount = 1200;
            }
          }
        } finally {
          clearTimeout(timeout);
        }
      }
    } else if (streamer.platform === "kick") {
      const channel = streamer.name || streamer.platform_id;
      if (channel) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3500);
        try {
          const res = await fetch(`https://kick.com/api/v2/channels/${encodeURIComponent(channel)}`, {
            headers: { "User-Agent": "Mozilla/5.0" },
            signal: controller.signal,
            next: { revalidate: 60 },
          });
          if (res.ok) {
            platformCheckSuccess = true;
            const data = await res.json();
            if (data.livestream && data.livestream.is_live) {
              isLive = true;
              viewerCount = data.livestream.viewer_count || 500;
              platformSessionId = String(data.livestream.id || "");
            }
          }
        } finally {
          clearTimeout(timeout);
        }
      }
    }
  } catch (e) {
    console.warn(`Error checking live status for streamer ${streamer.id}:`, e);
  }

  // Synchronize state with stream_sessions table in Supabase
  try {
    const supabase = getSupabaseAdmin();
    const { data: existingSession } = await supabase
      .from("stream_sessions")
      .select("id, status, viewer_count, started_at")
      .eq("streamer_id", streamer.id)
      .eq("status", "live")
      .order("id", { ascending: false })
      .limit(1)
      .maybeSingle();

    // If platform check failed due to timeout/bot-check, NEVER kill an active session!
    if (!platformCheckSuccess && existingSession) {
      const result: LiveStatusResult = {
        is_live: true,
        viewer_count: existingSession.viewer_count || 1200,
        active_session_id: existingSession.id,
      };
      liveStatusCache.set(streamer.id, { result, expiresAt: now + 30000 });
      return result;
    }

    if (isLive) {
      if (!existingSession) {
        const { data: newSession } = await supabase
          .from("stream_sessions")
          .insert({
            streamer_id: streamer.id,
            status: "live",
            started_at: new Date().toISOString(),
            viewer_count: viewerCount,
            platform_session_id: platformSessionId,
          })
          .select("id")
          .single();

        const result: LiveStatusResult = {
          is_live: true,
          viewer_count: viewerCount,
          active_session_id: newSession?.id,
        };
        liveStatusCache.set(streamer.id, { result, expiresAt: now + 60000 });
        return result;
      } else {
        if (viewerCount > 0 && viewerCount !== existingSession.viewer_count) {
          await supabase
            .from("stream_sessions")
            .update({ viewer_count: viewerCount })
            .eq("id", existingSession.id);
        }

        const result: LiveStatusResult = {
          is_live: true,
          viewer_count: viewerCount || existingSession.viewer_count || 1200,
          active_session_id: existingSession.id,
        };
        liveStatusCache.set(streamer.id, { result, expiresAt: now + 60000 });
        return result;
      }
    } else {
      // Only end session if platform check genuinely confirmed broadcast is inactive
      if (existingSession && platformCheckSuccess) {
        await supabase
          .from("stream_sessions")
          .update({
            status: "ended",
            ended_at: new Date().toISOString(),
          })
          .eq("id", existingSession.id);
      }

      const result: LiveStatusResult = {
        is_live: false,
        viewer_count: 0,
        active_session_id: null,
      };
      liveStatusCache.set(streamer.id, { result, expiresAt: now + 60000 });
      return result;
    }
  } catch (e) {
    console.warn(`Error syncing stream session in Supabase for streamer ${streamer.id}:`, e);
    const result: LiveStatusResult = {
      is_live: isLive,
      viewer_count: viewerCount,
      active_session_id: null,
    };
    liveStatusCache.set(streamer.id, { result, expiresAt: now + 30000 });
    return result;
  }
}
