import { NextResponse } from "next/server";
import {
  verifyToken,
  signAccessToken,
  signRefreshToken,
} from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { refresh_token } = body;

    if (!refresh_token) {
      return NextResponse.json(
        { detail: "Refresh token is required" },
        { status: 400 }
      );
    }

    const payload = await verifyToken(refresh_token);
    if (!payload || payload.type !== "refresh" || !payload.sub) {
      return NextResponse.json(
        { detail: "Invalid or expired refresh token" },
        { status: 401 }
      );
    }

    const userId = parseInt(payload.sub as string, 10);
    const username = (payload.username as string) || "admin";

    const newAccessToken = await signAccessToken(userId, username);
    const newRefreshToken = await signRefreshToken(userId, username);

    return NextResponse.json({
      access_token: newAccessToken,
      refresh_token: newRefreshToken,
      token_type: "bearer",
      must_change_password: false,
    });
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Token refresh failed" },
      { status: 401 }
    );
  }
}
