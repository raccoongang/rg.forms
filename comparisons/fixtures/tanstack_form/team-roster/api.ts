// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { TeamRosterValues } from "./schema";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// Server errors come back indexed per row so they can be mapped onto the matching
// array-item fields, e.g. {"members": {"1": {"email": ["Email is required..."]}}}.
export interface RosterResult {
  ok: boolean;
  // path like "members[1].email" -> first message
  errors: Record<string, string>;
}

export async function submitRoster(values: TeamRosterValues): Promise<RosterResult> {
  const res = await fetch("/api/team-roster/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(values),
  });
  const data = (await res.json()) as {
    ok: boolean;
    errors?: { members?: Record<string, Record<string, string[]>> };
  };

  const flat: Record<string, string> = {};
  const rows = data.errors?.members ?? {};
  for (const [index, rowErrors] of Object.entries(rows)) {
    for (const [field, msgs] of Object.entries(rowErrors)) {
      flat[`members[${index}].${field}`] = msgs[0] ?? "Invalid value.";
    }
  }
  return { ok: data.ok, errors: flat };
}
