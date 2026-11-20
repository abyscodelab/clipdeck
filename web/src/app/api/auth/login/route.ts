import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/server-supabase";
import {
  verifyPassword,
  signAccessToken,
  signRefreshToken,
} from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { username, password, totp_code } = body;

    if (!username || !password) {
      return NextResponse.json(
        { detail: "Username and password are required" },
        { status: 400 }
      );
    }

    const supabase = getSupabaseAdmin();
    const { data: user, error } = await supabase
      .from("users")
      .select("*")
      .eq("username", username.trim())
      .maybeSingle();

    if (error || !user) {
      return NextResponse.json(
        { detail: "Invalid credentials" },
        { status: 401 }
      );
    }

    const isValid = verifyPassword(password, user.password_hash);
    if (!isValid) {
      return NextResponse.json(
        { detail: "Invalid credentials" },
        { status: 401 }
      );
    }

    if (user.totp_enabled && !totp_code) {
      return NextResponse.json(
        { detail: "TOTP code required" },
        { status: 401 }
      );
    }

    const access_token = await signAccessToken(user.id, user.username);
    const refresh_token = await signRefreshToken(user.id, user.username);

    return NextResponse.json({
      access_token,
      refresh_token,
      token_type: "bearer",
      must_change_password: Boolean(user.must_change_password),
    });
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Authentication error" },
      { status: 500 }
    );
  }
}
