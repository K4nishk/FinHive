import { test } from "node:test";
import assert from "node:assert/strict";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { AuthContext, type AuthContextValue } from "./AuthProvider";
import { RoleGate } from "./RoleGate";
import type { MeResponse } from "./types";

function authValue(me: MeResponse | null): AuthContextValue {
  return {
    session: null,
    me,
    status: me ? "authenticated" : "unauthenticated",
    signOut: async () => {},
  };
}

function withAuth(me: MeResponse | null, node: ReactNode) {
  return (
    <MemoryRouter>
      <AuthContext.Provider value={authValue(me)}>{node}</AuthContext.Provider>
    </MemoryRouter>
  );
}

const owner: MeResponse = {
  user_id: "u1",
  org_id: "o1",
  org_name: "Acme",
  role: "owner",
  features: [],
};

const viewer: MeResponse = { ...owner, role: "viewer" };

test("RoleGate: an allowed role renders its children", () => {
  const html = renderToStaticMarkup(
    withAuth(
      owner,
      <RoleGate allow={["owner"]}>
        <button>Delete loan</button>
      </RoleGate>,
    ),
  );
  assert.match(html, /Delete loan/);
});

test("RoleGate hide (default): a disallowed role sees the fallback, not the control", () => {
  const html = renderToStaticMarkup(
    withAuth(
      viewer,
      <RoleGate allow={["owner"]} fallback={<span>Not available</span>}>
        <button>Delete loan</button>
      </RoleGate>,
    ),
  );
  assert.doesNotMatch(html, /Delete loan/);
  assert.match(html, /Not available/);
});

test("RoleGate hide: with no fallback, a disallowed role renders nothing", () => {
  const html = renderToStaticMarkup(
    withAuth(
      viewer,
      <RoleGate allow={["owner"]}>
        <button>Delete loan</button>
      </RoleGate>,
    ),
  );
  assert.equal(html, "");
});

test("RoleGate disable: a disallowed role gets a disabled control, not a hidden one", () => {
  const html = renderToStaticMarkup(
    withAuth(
      viewer,
      <RoleGate allow={["owner"]} variant="disable">
        <button>Delete loan</button>
      </RoleGate>,
    ),
  );
  assert.match(html, /Delete loan/);
  assert.match(html, /disabled=""/);
});

test("RoleGate: an unresolved (null) me is treated as disallowed", () => {
  const html = renderToStaticMarkup(
    withAuth(
      null,
      <RoleGate allow={["owner"]} fallback={<span>Not available</span>}>
        <button>Delete loan</button>
      </RoleGate>,
    ),
  );
  assert.match(html, /Not available/);
});
