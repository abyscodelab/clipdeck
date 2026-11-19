import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey, {
      realtime: {
        params: {
          eventsPerSecond: 10,
        },
      },
    })
  : null;

/**
 * Subscribe to realtime detected moments from Supabase PostgreSQL
 */
export function subscribeToMoments(onInsert: (payload: any) => void, onUpdate?: (payload: any) => void) {
  if (!supabase) return () => {};

  const channel = supabase
    .channel("public:moments")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "moments" },
      (payload) => onInsert(payload.new)
    )
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "moments" },
      (payload) => onUpdate?.(payload.new)
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}

/**
 * Subscribe to realtime clip processing state changes
 */
export function subscribeToClips(onUpdate: (payload: any) => void) {
  if (!supabase) return () => {};

  const channel = supabase
    .channel("public:clips")
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "clips" },
      (payload) => onUpdate(payload.new)
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
