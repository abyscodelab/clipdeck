import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";
import { checkLiveStatus } from "@/lib/live-checker";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("streamers")
      .select("*")
      .eq("id", parseInt(id, 10))
      .maybeSingle();

    if (error || !data) {
      return NextResponse.json({ detail: "Streamer not found" }, { status: 404 });
    }

    const liveInfo = await checkLiveStatus(data);

    return NextResponse.json({
      ...data,
      is_live: liveInfo.is_live,
      viewer_count: liveInfo.viewer_count,
      active_session_id: liveInfo.active_session_id,
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("streamers")
      .update({
        ...body,
        updated_at: new Date().toISOString(),
      })
      .eq("id", parseInt(id, 10))
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

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = getSupabaseAdmin();
    const { error } = await supabase
      .from("streamers")
      .delete()
      .eq("id", parseInt(id, 10));

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json({ message: "Streamer deleted" });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
