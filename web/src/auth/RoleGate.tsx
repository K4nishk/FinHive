// Agent-blind (ARD v2.1.0 section 4): must not import from finhive/agent or
// subscribe to agent state. This component only hides UI; the server's RLS /
// required_role checks are the actual control (ARD v2.1.0 section 8).
import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { resolveRoleGateDecision, type RoleGateVariant } from "./roleGateLogic";
import type { Role } from "./types";

export interface RoleGateProps {
  allow: Role[];
  children: ReactNode;
  fallback?: ReactNode;
  variant?: RoleGateVariant;
  redirectTo?: string;
}

type DisableableElement = ReactElement<{ disabled?: boolean; "aria-disabled"?: boolean }>;

export function RoleGate({
  allow,
  children,
  fallback = null,
  variant = "hide",
  redirectTo = "/",
}: RoleGateProps) {
  const { me } = useAuth();
  const decision = resolveRoleGateDecision(me?.role, allow, variant, redirectTo);

  switch (decision.kind) {
    case "children":
      return <>{children}</>;
    case "redirect":
      return <Navigate to={decision.to} replace />;
    case "disable":
      if (isValidElement(children)) {
        return cloneElement(children as DisableableElement, {
          disabled: true,
          "aria-disabled": true,
        });
      }
      return <>{fallback}</>;
    case "fallback":
      return <>{fallback}</>;
  }
}
