import type { MeResponse, Session } from "./types";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthState {
  session: Session | null;
  me: MeResponse | null;
  status: AuthStatus;
}

export const initialAuthState: AuthState = {
  session: null,
  me: null,
  status: "loading",
};

export type AuthEvent =
  | { type: "SESSION_CHANGED"; session: Session | null }
  | { type: "ME_LOADED"; me: MeResponse }
  // A refresh mid-sync replaces session and me together, in one transition, so the
  // effect watching `session` does not re-fire and re-request /api/me a second time.
  | { type: "REFRESHED"; session: Session; me: MeResponse }
  | { type: "ME_LOAD_FAILED" }
  | { type: "SIGNED_OUT" };

const signedOutState: AuthState = {
  session: null,
  me: null,
  status: "unauthenticated",
};

export function authReducer(state: AuthState, event: AuthEvent): AuthState {
  switch (event.type) {
    case "SESSION_CHANGED":
      if (event.session === null) {
        return signedOutState;
      }
      return { ...state, session: event.session };
    case "ME_LOADED":
      return { ...state, me: event.me, status: "authenticated" };
    case "REFRESHED":
      return { session: event.session, me: event.me, status: "authenticated" };
    case "ME_LOAD_FAILED":
    case "SIGNED_OUT":
      return signedOutState;
    default:
      return state;
  }
}
