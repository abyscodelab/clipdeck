import { NextResponse } from "next/server";
import { getAuthUser, verifyPassword, hashPassword } from "@/lib/server-auth";
import { getSupabaseAdmin } from "@/lib/server-supabase";

export async function PUT(request: Request) {
  try {
    const user = await getAuthUser(request);
    if (!user) {
      return NextResponse.json(
        { detail: "Unauthorized" },
        { status: 401 }
      );
    }

    const body = await request.json();
    const { current_password, new_password } = body;

    if (!current_password || !new_password) {
      return NextResponse.json(
        { detail: "Both current and new password are required" },
        { status: 400 }
      );
    }

    const supabase = getSupabaseAdmin();
    const { data: dbUser } = await supabase
      .from("users")
      .select("password_hash")
      .eq("id", user.id)
      .maybeSingle();

    if (!dbUser || !verifyPassword(current_password, dbUser.password_hash)) {
      return NextResponse.json(
        { detail: "Current password is incorrect" },
        { status: 400 }
      );
    }

    const newHash = hashPassword(new_password);
    await supabase
      .from("users")
      .update({
        password_hash: newHash,
        must_change_password: false,
      })
      .eq("id", user.id);

    return NextResponse.json({
      message: "Password changed successfully",
    });
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Password change failed" },
      { status: 500 }
    );
  }
}
