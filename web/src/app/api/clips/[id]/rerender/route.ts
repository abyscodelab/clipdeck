import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const clipId = parseInt(id, 10);
    const body = await request.json().catch(() => ({}));

    const supabase = getSupabaseAdmin();
    await supabase
      .from("clips")
      .update({
        status: "rendering",
        updated_at: new Date().toISOString(),
      })
      .eq("id", clipId);

    return NextResponse.json({
      message: "Rerender job enqueued",
      job_id: clipId,
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
