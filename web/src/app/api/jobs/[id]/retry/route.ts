import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const supabase = getSupabaseAdmin();
    await supabase
      .from("jobs")
      .update({ status: "pending", attempts: 0 })
      .eq("id", parseInt(id, 10));

    return NextResponse.json({ message: "Job retried" });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
