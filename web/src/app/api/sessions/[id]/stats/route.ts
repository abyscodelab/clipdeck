import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get("limit") || "60", 10);

    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("chat_stats_buckets")
      .select("*")
      .eq("session_id", parseInt(id, 10))
      .order("timestamp", { ascending: false })
      .limit(limit);

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }
    return NextResponse.json(data || []);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
