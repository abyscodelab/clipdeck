import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const momentId = parseInt(id, 10);
    const supabase = getSupabaseAdmin();

    const { data: moment } = await supabase
      .from("moments")
      .select("*")
      .eq("id", momentId)
      .maybeSingle();

    if (!moment) {
      return NextResponse.json({ detail: "Moment not found" }, { status: 404 });
    }

    // Create a clip entry for AI edit
    const { data: clip, error } = await supabase
      .from("clips")
      .insert({
        moment_id: momentId,
        streamer_id: moment.streamer_id,
        title: `AI Highlight #${momentId}`,
        status: moment.file_path ? "rendered" : "rendering",
        duration: moment.clip_duration || 58.0,
        aspect_ratio: "9:16",
        file_path: moment.file_path || null,
        thumbnail_path: moment.thumbnail_path || null,
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }

    return NextResponse.json({
      message: "AI edit job submitted",
      job_id: clip.id,
      clip_id: clip.id,
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
