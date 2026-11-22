import { NextRequest } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      // Send initial connection event
      controller.enqueue(
        encoder.encode(
          `event: system_alert\ndata: ${JSON.stringify({
            level: "info",
            message: "Connected to ClipDeck Real-Time Events Engine",
            timestamp: new Date().toISOString(),
          })}\n\n`
        )
      );

      // Check active live sessions and push initial status
      try {
        const supabase = getSupabaseAdmin();
        const { data: liveSessions } = await supabase
          .from("stream_sessions")
          .select("id, streamer_id, status, viewer_count")
          .eq("status", "live");

        if (liveSessions && liveSessions.length > 0) {
          for (const s of liveSessions) {
            controller.enqueue(
              encoder.encode(
                `event: streamer_status\ndata: ${JSON.stringify({
                  streamer_id: s.streamer_id,
                  is_live: true,
                  viewer_count: s.viewer_count || 1200,
                  session_id: s.id,
                })}\n\n`
              )
            );
          }
        }
      } catch (err) {
        console.error("Error fetching live sessions for SSE:", err);
      }

      // Keepalive heartbeat ping every 10 seconds
      const timer = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: keepalive\n\n`));
        } catch {
          clearInterval(timer);
        }
      }, 10000);

      request.signal.addEventListener("abort", () => {
        clearInterval(timer);
        try {
          controller.close();
        } catch {}
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
