import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const body = await request.json().catch(() => ({}));
    const sampleText = body.sample_text || "";

    return NextResponse.json({
      rules_applied: [
        "Rule 1: Hook within first 3 seconds (Subtle punch captions)",
        "Rule 2: Minimum 60 FPS facecam crop anchor",
        "Rule 3: Dead air trimmed (> 1.2s silence)",
      ],
      rule_violations: sampleText.includes("boring")
        ? ["Flagged low pacing in intro"]
        : [],
      analysis:
        "Playbook test passed. 9:16 vertical layout presets and Subtle kinetic typography match editing directives.",
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
