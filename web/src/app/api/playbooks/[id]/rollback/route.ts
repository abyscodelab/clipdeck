import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("playbooks")
      .update({
        version: body.version_number,
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
