import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    return NextResponse.json([
      {
        id: 1,
        clip_id: 1,
        title: "SPEED CLUTCHES IMPOSSIBLE 1v4 IN GTA VI",
        style: "cinematic",
        url: "/thumbnails/demo_thumb_1.jpg",
        created_at: new Date().toISOString(),
      },
    ]);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message }, { status: 500 });
  }
}
