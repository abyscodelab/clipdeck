import { createClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://gwzcoxeddnyvsolvzsgv.supabase.co";

const supabaseKey =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3emNveGVkZG55dnNvbHZ6c2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUxMTc5NjYsImV4cCI6MjExMDY5Mzk2Nn0.w9nP7cHFHZtNAPJFMvpvsKB9fMTxtmhiE13IV6ZP4c8";

export function getSupabaseAdmin() {
  return createClient(supabaseUrl, supabaseKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });
}
