import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET() {
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("provider_keys")
      .select("id, provider, key_name, encrypted_value, created_at, updated_at")
      .order("created_at", { ascending: true });

    if (error) {
      return NextResponse.json({ detail: error.message }, { status: 500 });
    }

    const masked = (data || []).map((k) => {
      const val = k.encrypted_value || "";
      const masked_value =
        val.length > 4 ? `••••••••${val.slice(-4)}` : "••••••••";
      return {
        id: k.id,
        provider: k.provider,
        key_name: k.key_name,
        masked_value,
        created_at: k.created_at,
        updated_at: k.updated_at,
      };
    });

    return NextResponse.json(masked);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { provider, key_name, value } = body;

    if (!provider || !key_name || !value) {
      return NextResponse.json(
        { detail: "Provider, key_name, and value are required" },
        { status: 400 }
      );
    }

    const supabase = getSupabaseAdmin();

    // Check if key already exists for this key_name
    const { data: existing } = await supabase
      .from("provider_keys")
      .select("id")
      .eq("key_name", key_name)
      .maybeSingle();

    let result;
    if (existing) {
      const { data, error } = await supabase
        .from("provider_keys")
        .update({
          provider,
          encrypted_value: value,
          updated_at: new Date().toISOString(),
        })
        .eq("id", existing.id)
        .select("id, provider, key_name, created_at, updated_at")
        .single();

      if (error) {
        return NextResponse.json({ detail: error.message }, { status: 400 });
      }
      result = data;
    } else {
      const { data, error } = await supabase
        .from("provider_keys")
        .insert({
          provider,
          key_name,
          encrypted_value: value,
        })
        .select("id, provider, key_name, created_at, updated_at")
        .single();

      if (error) {
        return NextResponse.json({ detail: error.message }, { status: 400 });
      }
      result = data;
    }

    const val = value || "";
    const masked_value =
      val.length > 4 ? `••••••••${val.slice(-4)}` : "••••••••";

    return NextResponse.json({
      ...result,
      masked_value,
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
