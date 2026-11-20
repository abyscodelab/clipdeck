import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get("status");
    const queue = searchParams.get("queue");
    const limit = parseInt(searchParams.get("limit") || "50", 10);

    const supabase = getSupabaseAdmin();
    let query = supabase.from("jobs").select("*").order("created_at", { ascending: false }).limit(limit);

    if (status) query = query.eq("status", status);
    if (queue) query = query.eq("queue", queue);

    const { data, error } = await query;
    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }
    return NextResponse.json(data || []);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
