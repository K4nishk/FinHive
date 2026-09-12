// Types for the MVP2 identity contract (ARD v2.1.0 section 2, "Identity").

export type Role = "owner" | "bookkeeper" | "viewer";

export interface MeResponse {
  user_id: string;
  org_id: string;
  org_name: string;
  role: Role;
  features: string[];
}

export interface SessionUser {
  id: string;
  email: string | null;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: SessionUser;
}

export type AuthStateChangeCallback = (session: Session | null) => void;

export interface RefreshSessionResult {
  data: { session: Session | null };
  error: unknown;
}

// Minimal shape of `supabase.auth` (ARD v2.1.0 section 2 lists
// signInWithPassword/refreshSession as the SDK-typed bindings). AuthProvider depends
// on this interface rather than importing @supabase/supabase-js directly, so it is
// testable without a network-backed client and so KCH-107 can pass the real
// `supabase.auth` object straight through once the SDK is wired in.
export interface AuthClient {
  getSession(): Promise<{ data: { session: Session | null } }>;
  refreshSession(): Promise<RefreshSessionResult>;
  onAuthStateChange(callback: AuthStateChangeCallback): {
    data: { subscription: { unsubscribe(): void } };
  };
  signOut(): Promise<void>;
}
