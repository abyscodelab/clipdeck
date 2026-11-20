import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({
      success: true,
      thumbnail_url: "/thumbnails/demo_thumb_1.jpg",
      headline: body.headline || "INSANE CLUTCH MOMENT",
      mode: body.mode || "cinematic",
    });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
