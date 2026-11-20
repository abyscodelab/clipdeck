import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const scope = searchParams.get("scope");

    const supabase = getSupabaseAdmin();
    let query = supabase.from("playbooks").select("*").order("priority", { ascending: false });

    if (scope) {
      query = query.eq("scope", scope);
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

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("playbooks")
      .insert({
        name: body.name,
        scope: body.scope || "global",
        target_id: body.target_id || null,
        description: body.description || null,
        priority: body.priority || 50,
        content: body.content || "",
        version: 1,
        enabled: body.enabled !== undefined ? body.enabled : true,
      })
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
