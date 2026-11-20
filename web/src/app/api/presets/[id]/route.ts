import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("layout_presets")
      .update(body)
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
      .from("layout_presets")
      .delete()
      .eq("id", parseInt(id, 10));

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json({ message: "Preset deleted" });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
