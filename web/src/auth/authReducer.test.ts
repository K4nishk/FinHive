import { test } from "node:test";
import assert from "node:assert/strict";
import { authReducer, initialAuthState } from "./authReducer";
import type { MeResponse, Session } from "./types";

const session: Session = {
  access_token: "token",
  refresh_token: "refresh",
  expires_at: 0,
  user: { id: "user-1", email: "viewer@example.com" },
};

const me: MeResponse = {
  user_id: "user-1",
  org_id: "org-1",
  org_name: "Acme",
  role: "viewer",
  features: [],
};

test("initial state is loading with no session or me", () => {
  assert.deepEqual(initialAuthState, {
    session: null,
    me: null,
    status: "loading",
  });
});

test("SESSION_CHANGED with a session keeps status until me loads", () => {
  const next = authReducer(initialAuthState, {
    type: "SESSION_CHANGED",
    session,
  });
  assert.deepEqual(next, { session, me: null, status: "loading" });
});

test("SESSION_CHANGED to a different user clears the previous user's me", () => {
  const authenticated = { session, me, status: "authenticated" as const };
  const otherUser: Session = {
    ...session,
    access_token: "other-token",
    user: { id: "user-2", email: "other@example.com" },
  };
  const next = authReducer(authenticated, {
    type: "SESSION_CHANGED",
    session: otherUser,
  });
  assert.deepEqual(next, { session: otherUser, me: null, status: "loading" });
});

test("SESSION_CHANGED with null signs the user out", () => {
  const authenticated = { session, me, status: "authenticated" as const };
  const next = authReducer(authenticated, {
    type: "SESSION_CHANGED",
    session: null,
  });
  assert.deepEqual(next, {
    session: null,
    me: null,
    status: "unauthenticated",
  });
});

test("ME_LOADED marks the session authenticated", () => {
  const withSession = { session, me: null, status: "loading" as const };
  const next = authReducer(withSession, { type: "ME_LOADED", me });
  assert.deepEqual(next, { session, me, status: "authenticated" });
});

test("REFRESHED replaces session and me in a single transition", () => {
  const refreshedSession: Session = { ...session, access_token: "new-token" };
  const withSession = { session, me: null, status: "loading" as const };
  const next = authReducer(withSession, {
    type: "REFRESHED",
    session: refreshedSession,
    me,
  });
  assert.deepEqual(next, {
    session: refreshedSession,
    me,
    status: "authenticated",
  });
});

test("ME_LOAD_FAILED signs the user out", () => {
  const withSession = { session, me: null, status: "loading" as const };
  const next = authReducer(withSession, { type: "ME_LOAD_FAILED" });
  assert.deepEqual(next, {
    session: null,
    me: null,
    status: "unauthenticated",
  });
});

test("SIGNED_OUT clears session and me from an authenticated state", () => {
  const authenticated = { session, me, status: "authenticated" as const };
  const next = authReducer(authenticated, { type: "SIGNED_OUT" });
  assert.deepEqual(next, {
    session: null,
    me: null,
    status: "unauthenticated",
  });
});
