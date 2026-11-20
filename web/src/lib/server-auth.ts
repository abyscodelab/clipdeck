import { SignJWT, jwtVerify } from "jose";
import bcrypt from "bcryptjs";
import { getSupabaseAdmin } from "./server-supabase";

const JWT_SECRET =
  process.env.JWT_SECRET || "Xx_3M1uvGmG4v29qvogEK_Zn9sJ_aD6ffos6swIxcd0";
const secretKey = new TextEncoder().encode(JWT_SECRET);

export async function signAccessToken(
  userId: number,
  username: string
): Promise<string> {
  return new SignJWT({
    sub: String(userId),
    username,
    type: "access",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("24h")
    .sign(secretKey);
}

export async function signRefreshToken(
  userId: number,
  username: string
): Promise<string> {
  return new SignJWT({
    sub: String(userId),
    username,
    type: "refresh",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(secretKey);
}

export async function verifyToken(token: string) {
  try {
    const { payload } = await jwtVerify(token, secretKey);
    return payload;
  } catch {
    return null;
  }
}

export async function getAuthUser(request: Request) {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }
  const token = authHeader.substring(7).trim();
  const payload = await verifyToken(token);
  if (!payload || payload.type !== "access" || !payload.sub) {
    return null;
  }

  const userId = parseInt(payload.sub as string, 10);
  const supabase = getSupabaseAdmin();
  const { data: user } = await supabase
    .from("users")
    .select("id, username, totp_enabled, must_change_password, created_at")
    .eq("id", userId)
    .maybeSingle();

  if (!user) {
    return {
      id: userId,
      username: (payload.username as string) || "admin",
      totp_enabled: false,
      must_change_password: false,
      created_at: new Date().toISOString(),
    };
  }
  return user;
}

export function verifyPassword(plain: string, hash: string): boolean {
  try {
    return bcrypt.compareSync(plain, hash);
  } catch {
    return false;
  }
}

export function hashPassword(plain: string): string {
  return bcrypt.hashSync(plain, 12);
}
