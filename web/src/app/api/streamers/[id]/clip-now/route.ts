import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const streamerId = parseInt(id, 10);
    const body = await request.json().catch(() => ({}));
    const duration = body.duration || 60;

    const supabase = getSupabaseAdmin();

    // Create a manual moment
    const { data: moment, error: momentErr } = await supabase
      .from("moments")
      .insert({
        streamer_id: streamerId,
        hype_score: 95.0,
        detected_at: new Date().toISOString(),
        clip_duration: duration,
        status: "detected",
        trigger_type: "manual",
        chat_data: { manual_trigger: true, duration },
      })
      .select()
      .single();

    if (momentErr) {
      return NextResponse.json({ detail: momentErr.message }, { status: 500 });
    }

    // Also register in clips table with rendering status
    await supabase.from("clips").insert({
      moment_id: moment.id,
      streamer_id: streamerId,
      title: `Manual Highlight (${duration}s)`,
      status: "rendering",
      duration: duration,
      aspect_ratio: "9:16",
    });

    return NextResponse.json({
      message: "Clip triggered successfully",
      job_id: moment.id,
      moment_id: moment.id,
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
