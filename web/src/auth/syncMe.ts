import type { AuthClient, MeResponse, Session } from "./types";

export type SyncMeResult =
  | { kind: "loaded"; me: MeResponse }
  | { kind: "refreshed"; session: Session; me: MeResponse }
  | { kind: "failed" };

// Resolves `me` for a session, transparently refreshing once if the fetch is
// unauthorized. A `TOKEN_REFRESHED` event from the SDK's own background refresh
// (autoRefreshToken) is the common path; this covers the case where GET /api/me
// still 401s despite that (e.g. a stale token at mount, or clock skew), and gives
// up after a single retry rather than looping.
export async function syncMe(
  authClient: Pick<AuthClient, "refreshSession">,
  fetchMe: (accessToken: string) => Promise<MeResponse>,
  session: Session,
  attempt = 0,
): Promise<SyncMeResult> {
  try {
    const me = await fetchMe(session.access_token);
    return { kind: "loaded", me };
  } catch {
    if (attempt > 0) {
      return { kind: "failed" };
    }

    const { data, error } = await authClient.refreshSession();
    if (error || !data.session) {
      return { kind: "failed" };
    }

    const retried = await syncMe(
      authClient,
      fetchMe,
      data.session,
      attempt + 1,
    );
    if (retried.kind !== "loaded") {
      return { kind: "failed" };
    }
    return { kind: "refreshed", session: data.session, me: retried.me };
  }
}
