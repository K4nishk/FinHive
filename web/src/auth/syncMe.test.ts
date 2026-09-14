import { test } from "node:test";
import assert from "node:assert/strict";
import { syncMe } from "./syncMe.ts";
import type { AuthClient, MeResponse, Session } from "./types.ts";

function makeSession(accessToken: string): Session {
  return {
    access_token: accessToken,
    refresh_token: `${accessToken}-refresh`,
    expires_at: 0,
    user: { id: "user-1", email: "owner@example.com" },
  };
}

const me: MeResponse = {
  user_id: "user-1",
  org_id: "org-1",
  org_name: "Acme",
  role: "owner",
  features: [],
};

test("syncMe: resolves directly when fetchMe succeeds", async () => {
  const session = makeSession("valid");
  const fetchMe = async (token: string) => {
    assert.equal(token, "valid");
    return me;
  };
  const authClient: Pick<AuthClient, "refreshSession"> = {
    refreshSession: async () => {
      throw new Error("should not be called");
    },
  };

  const result = await syncMe(authClient, fetchMe, session);
  assert.deepEqual(result, { kind: "loaded", me });
});

test("syncMe: refreshes once and retries on a 401-style failure", async () => {
  const staleSession = makeSession("stale");
  const freshSession = makeSession("fresh");
  const fetchMe = async (token: string) => {
    if (token === "stale") {
      throw new Error("401");
    }
    return me;
  };
  const authClient: Pick<AuthClient, "refreshSession"> = {
    refreshSession: async () => ({ data: { session: freshSession }, error: null }),
  };

  const result = await syncMe(authClient, fetchMe, staleSession);
  assert.deepEqual(result, { kind: "refreshed", session: freshSession, me });
});

test("syncMe: fails without a second retry when the refreshed session also 401s", async () => {
  const staleSession = makeSession("stale");
  const stillBadSession = makeSession("still-bad");
  let fetchMeCalls = 0;
  const fetchMe = async () => {
    fetchMeCalls += 1;
    throw new Error("401");
  };
  const authClient: Pick<AuthClient, "refreshSession"> = {
    refreshSession: async () => ({ data: { session: stillBadSession }, error: null }),
  };

  const result = await syncMe(authClient, fetchMe, staleSession);
  assert.deepEqual(result, { kind: "failed" });
  assert.equal(fetchMeCalls, 2);
});

test("syncMe: fails when the refresh itself errors", async () => {
  const staleSession = makeSession("stale");
  const fetchMe = async () => {
    throw new Error("401");
  };
  const authClient: Pick<AuthClient, "refreshSession"> = {
    refreshSession: async () => ({ data: { session: null }, error: new Error("refresh failed") }),
  };

  const result = await syncMe(authClient, fetchMe, staleSession);
  assert.deepEqual(result, { kind: "failed" });
});
