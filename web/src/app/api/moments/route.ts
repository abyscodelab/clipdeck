import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const streamerId = searchParams.get("streamer_id");
    const status = searchParams.get("status");
    const limit = parseInt(searchParams.get("limit") || "50", 10);
    const offset = parseInt(searchParams.get("offset") || "0", 10);

    const supabase = getSupabaseAdmin();
    let query = supabase
      .from("moments")
      .select("*, streamer:streamers(*)")
      .order("detected_at", { ascending: false })
      .range(offset, offset + limit - 1);

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
