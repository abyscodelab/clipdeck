import { NextResponse } from "next/server";
import { getAuthUser } from "@/lib/server-auth";

export async function GET(request: Request) {
  try {
    const user = await getAuthUser(request);
    if (!user) {
      return NextResponse.json(
        { detail: "Unauthorized" },
        { status: 401 }
      );
    }

    return NextResponse.json({
      id: user.id,
      username: user.username,
      totp_enabled: Boolean(user.totp_enabled),
      must_change_password: Boolean(user.must_change_password),
      created_at: user.created_at || new Date().toISOString(),
    });
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Failed to get user profile" },
      { status: 500 }
    );
  }
}
