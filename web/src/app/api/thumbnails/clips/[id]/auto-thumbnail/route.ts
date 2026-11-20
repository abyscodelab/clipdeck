import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    return NextResponse.json({
      success: true,
      thumbnail_url: "/thumbnails/demo_thumb_1.jpg",
      headline: "GTA VI CLUTCH",
      mode: "cinematic",
      clip_id: parseInt(id, 10),
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
