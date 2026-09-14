// Agent-blind (ARD v2.1.0 section 4): must not import from finhive/agent or
// subscribe to agent state.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";
import { authReducer, initialAuthState, type AuthStatus } from "./authReducer";
import { syncMe } from "./syncMe";
import type { AuthClient, MeResponse, Session } from "./types";

export interface AuthContextValue {
  session: Session | null;
  me: MeResponse | null;
  status: AuthStatus;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

async function defaultFetchMe(accessToken: string): Promise<MeResponse> {
  const response = await fetch("/api/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error(`GET /api/me failed with ${response.status}`);
  }
  return (await response.json()) as MeResponse;
}

export interface AuthProviderProps {
  /** The `supabase.auth` client (or a fake implementing the same shape in tests). */
  authClient: AuthClient;
  children: ReactNode;
  fetchMe?: (accessToken: string) => Promise<MeResponse>;
}

export function AuthProvider({ authClient, children, fetchMe = defaultFetchMe }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);

  useEffect(() => {
    let cancelled = false;

    authClient.getSession().then(({ data }) => {
      if (!cancelled) {
        dispatch({ type: "SESSION_CHANGED", session: data.session });
      }
    });

    const { data: subscription } = authClient.onAuthStateChange((session) => {
      if (!cancelled) {
        dispatch({ type: "SESSION_CHANGED", session });
      }
    });

    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, [authClient]);

  useEffect(() => {
    if (!state.session) {
      return;
    }

    let cancelled = false;
    syncMe(authClient, fetchMe, state.session).then((result) => {
      if (cancelled) {
        return;
      }
      if (result.kind === "failed") {
        dispatch({ type: "ME_LOAD_FAILED" });
        return;
      }
      if (result.kind === "refreshed") {
        dispatch({ type: "REFRESHED", session: result.session, me: result.me });
        return;
      }
      dispatch({ type: "ME_LOADED", me: result.me });
    });

    return () => {
      cancelled = true;
    };
  }, [state.session, authClient, fetchMe]);

  const signOut = useCallback(async () => {
    await authClient.signOut();
    dispatch({ type: "SIGNED_OUT" });
  }, [authClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ session: state.session, me: state.me, status: state.status, signOut }),
    [state.session, state.me, state.status, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
