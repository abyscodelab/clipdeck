import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

function unwrapSettings(rows: any[] | null) {
  return (rows || []).map((row) => ({
    ...row,
    value:
      row.value && typeof row.value === "object" && "val" in row.value
        ? row.value.val
        : row.value,
  }));
}

export async function GET() {
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase.from("settings").select("*");
    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }
    return NextResponse.json(unwrapSettings(data));
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const settingsObj = body.settings || {};
    const supabase = getSupabaseAdmin();

    const updates = Object.entries(settingsObj).map(([key, val]) => ({
      key,
      value: val,
      updated_at: new Date().toISOString(),
    }));

    if (updates.length > 0) {
      await supabase.from("settings").upsert(updates, { onConflict: "key" });
    }

    const { data } = await supabase.from("settings").select("*");
    return NextResponse.json(unwrapSettings(data));
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
