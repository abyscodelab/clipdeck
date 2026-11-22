import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";
import { checkLiveStatus } from "@/lib/live-checker";

export async function GET() {
  try {
    const supabase = getSupabaseAdmin();

    // Query streamers and active stream sessions in parallel (sub-30ms)
    const [streamersRes, sessionsRes] = await Promise.all([
      supabase
        .from("streamers")
        .select("*")
        .order("priority", { ascending: false })
        .order("id", { ascending: true }),
      supabase
        .from("stream_sessions")
        .select("id, streamer_id, status, viewer_count, started_at")
        .eq("status", "live")
        .order("id", { ascending: false }),
    ]);

    if (streamersRes.error) {
      return NextResponse.json({ detail: streamersRes.error.message }, { status: 500 });
    }

    const streamers = streamersRes.data || [];
    const liveSessions = sessionsRes.data || [];

    // Map active live sessions by streamer_id
    const liveSessionMap = new Map<number, any>();
    liveSessions.forEach((s) => {
      if (!liveSessionMap.has(s.streamer_id)) {
        liveSessionMap.set(s.streamer_id, s);
      }
    });

    const enriched = await Promise.all(
      streamers.map(async (st) => {
        const activeSession = liveSessionMap.get(st.id);

        // If an active session is already registered in Supabase, return immediately!
        if (activeSession) {
          return {
            ...st,
            is_live: true,
            viewer_count: activeSession.viewer_count || 1200,
            active_session_id: activeSession.id,
          };
        }

        // Otherwise check live status (backed by 60s memory cache and 3.5s timeout)
        const liveInfo = await checkLiveStatus(st);
        return {
          ...st,
          is_live: liveInfo.is_live,
          viewer_count: liveInfo.viewer_count,
          active_session_id: liveInfo.active_session_id,
        };
      })
    );

    return NextResponse.json(enriched);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("streamers")
      .insert({
        name: body.name,
        platform: body.platform,
        platform_id: body.platform_id || null,
        url: body.url || null,
        relationship_type: body.relationship_type || "none",
        auto_monitor: body.auto_monitor !== undefined ? body.auto_monitor : true,
        priority: body.priority || 1,
        niche: body.niche || null,
        keywords: body.keywords || [],
        emote_list: body.emote_list || [],
        notes: body.notes || null,
        config: body.config || null,
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
