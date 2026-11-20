import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("stream_sessions")
      .select("*")
      .eq("id", parseInt(id, 10))
      .maybeSingle();

    if (error || !data) {
      return NextResponse.json({ detail: "Session not found" }, { status: 404 });
    }
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
