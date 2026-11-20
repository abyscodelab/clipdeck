import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET() {
  try {
    const supabase = getSupabaseAdmin();
    const { data: streamers, error } = await supabase
      .from("streamers")
      .select("*")
      .order("priority", { ascending: false })
      .order("id", { ascending: true });

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }

    return NextResponse.json(streamers || []);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("streamers")
      .insert({
        name: body.name,
        platform: body.platform,
        platform_id: body.platform_id || null,
        url: body.url || null,
        relationship_type: body.relationship_type || "none",
        auto_monitor: body.auto_monitor !== undefined ? body.auto_monitor : true,
        priority: body.priority || 1,
        niche: body.niche || null,
        keywords: body.keywords || [],
        emote_list: body.emote_list || [],
        notes: body.notes || null,
        config: body.config || null,
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
