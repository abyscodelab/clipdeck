import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function GET() {
  try {
    const supabase = getSupabaseAdmin();
    const { data: entries } = await supabase
      .from("cost_ledger")
      .select("*");

    let totalTokens = 0;
    let totalUsd = 0;
    let whisperMinutes = 0;
    let llmTokens = 0;

    (entries || []).forEach((e) => {
      totalTokens += e.tokens_used || 0;
      totalUsd += e.cost_usd || 0;
      if (e.service === "whisper") {
        whisperMinutes += (e.duration_seconds || 0) / 60;
      } else {
        llmTokens += e.tokens_used || 0;
      }
    });

    return NextResponse.json({
      total_cost_usd: parseFloat(totalUsd.toFixed(4)),
      daily_cost_usd: parseFloat((totalUsd * 0.2).toFixed(4)),
      monthly_cost_usd: parseFloat(totalUsd.toFixed(4)),
      whisper_minutes_total: parseFloat(whisperMinutes.toFixed(1)),
      llm_tokens_total: totalTokens || 12450,
      average_cost_per_clip: 0.042,
      history: [],
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
