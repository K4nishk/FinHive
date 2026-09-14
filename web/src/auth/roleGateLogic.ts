import type { Role } from "./types";

export type RoleGateVariant = "hide" | "disable" | "redirect";

export type RoleGateDecision =
  | { kind: "children" }
  | { kind: "fallback" }
  | { kind: "redirect"; to: string }
  | { kind: "disable" };

export function isRoleAllowed(role: Role | undefined, allow: Role[]): boolean {
  return role !== undefined && allow.includes(role);
}

export function resolveRoleGateDecision(
  role: Role | undefined,
  allow: Role[],
  variant: RoleGateVariant,
  redirectTo: string,
): RoleGateDecision {
  if (isRoleAllowed(role, allow)) {
    return { kind: "children" };
  }
  if (variant === "redirect") {
    return { kind: "redirect", to: redirectTo };
  }
  if (variant === "disable") {
    return { kind: "disable" };
  }
  return { kind: "fallback" };
}
