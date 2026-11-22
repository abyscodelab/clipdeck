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
      .from("provider_keys")
      .update({
        encrypted_value: body.value || "",
        updated_at: new Date().toISOString(),
      })
      .eq("id", parseInt(id, 10))
      .select("id, provider, key_name, created_at, updated_at")
      .single();

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }

    const val = body.value || "";
    const masked_value =
      val.length > 4 ? `••••••••${val.slice(-4)}` : "••••••••";

    return NextResponse.json({
      ...data,
      masked_value,
    });
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
      .from("provider_keys")
      .delete()
      .eq("id", parseInt(id, 10));

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json({ message: "Key removed" });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
