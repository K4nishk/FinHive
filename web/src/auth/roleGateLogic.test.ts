import { test } from "node:test";
import assert from "node:assert/strict";
import { isRoleAllowed, resolveRoleGateDecision } from "./roleGateLogic";

test("isRoleAllowed: viewer is not allowed on an owner-only gate", () => {
  assert.equal(isRoleAllowed("viewer", ["owner"]), false);
});

test("isRoleAllowed: owner is allowed on an owner-only gate", () => {
  assert.equal(isRoleAllowed("owner", ["owner"]), true);
});

test("isRoleAllowed: bookkeeper is allowed when listed alongside owner", () => {
  assert.equal(isRoleAllowed("bookkeeper", ["owner", "bookkeeper"]), true);
});

test("isRoleAllowed: an unresolved role (undefined) is never allowed", () => {
  assert.equal(
    isRoleAllowed(undefined, ["owner", "bookkeeper", "viewer"]),
    false,
  );
});

test("resolveRoleGateDecision: allowed role renders children regardless of variant", () => {
  assert.deepEqual(resolveRoleGateDecision("owner", ["owner"], "hide", "/"), {
    kind: "children",
  });
  assert.deepEqual(
    resolveRoleGateDecision("owner", ["owner"], "disable", "/"),
    { kind: "children" },
  );
  assert.deepEqual(
    resolveRoleGateDecision("owner", ["owner"], "redirect", "/"),
    { kind: "children" },
  );
});

test("resolveRoleGateDecision: disallowed + hide falls back", () => {
  assert.deepEqual(resolveRoleGateDecision("viewer", ["owner"], "hide", "/"), {
    kind: "fallback",
  });
});

test("resolveRoleGateDecision: disallowed + disable disables", () => {
  assert.deepEqual(
    resolveRoleGateDecision("viewer", ["owner"], "disable", "/"),
    { kind: "disable" },
  );
});

test("resolveRoleGateDecision: disallowed + redirect carries the redirect target", () => {
  assert.deepEqual(
    resolveRoleGateDecision("viewer", ["owner"], "redirect", "/dashboard"),
    {
      kind: "redirect",
      to: "/dashboard",
    },
  );
});
