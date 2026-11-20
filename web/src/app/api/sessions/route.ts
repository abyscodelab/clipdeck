import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const streamerId = searchParams.get("streamer_id");

    const supabase = getSupabaseAdmin();
    let query = supabase
      .from("stream_sessions")
      .select("*")
      .order("started_at", { ascending: false });

    if (streamerId) {
      query = query.eq("streamer_id", parseInt(streamerId, 10));
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
