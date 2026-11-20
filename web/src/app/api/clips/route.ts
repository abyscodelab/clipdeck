import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const streamerId = searchParams.get("streamer_id");
    const status = searchParams.get("status");
    const limit = parseInt(searchParams.get("limit") || "50", 10);

    const supabase = getSupabaseAdmin();
    let query = supabase
      .from("clips")
      .select("*, streamer:streamers(*), moment:moments(*)")
      .order("created_at", { ascending: false })
      .limit(limit);

    if (streamerId) {
      query = query.eq("streamer_id", parseInt(streamerId, 10));
    }
    if (status) {
      query = query.eq("status", status);
    }

    const { data, error } = await query;
    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }

    return NextResponse.json(data || []);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("clips")
      .insert({
        moment_id: body.moment_id,
        streamer_id: body.streamer_id,
        title: body.title || "Vertical Highlight Clip",
        status: "rendering",
        duration: body.duration || 60,
        aspect_ratio: "9:16",
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
