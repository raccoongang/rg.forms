// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { FormikErrors } from "formik";
import type { RosterValues, TeamMember } from "./schema";

const CSRF_HEADER = "X-CSRFToken";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export interface RosterResult {
  ok: boolean;
  fieldErrors: FormikErrors<RosterValues>;
  formErrors: string[];
}

// The server returns per-row errors as a list aligned with the submitted rows:
// { "errors": { "members": [ {"email": ["..."]}, {}, ... ], "__all__": [...] } }
// Formik expects errors.members to be an array of per-row error objects, so the
// mapping mostly preserves shape and joins Django's message lists.
interface ServerPayload {
  errors?: {
    members?: Array<Record<string, string[]>>;
    __all__?: string[];
  };
}

function mapErrors(payload: ServerPayload): RosterResult {
  const formErrors = payload.errors?.__all__ ?? [];
  const rows = payload.errors?.members ?? [];
  const members: FormikErrors<TeamMember>[] = rows.map((row) => {
    const mapped: Record<string, string> = {};
    for (const [field, messages] of Object.entries(row)) {
      const key = field === "full_name" ? "fullName" : field === "admin_note" ? "adminNote" : field;
      mapped[key] = messages.join(" ");
    }
    return mapped as FormikErrors<TeamMember>;
  });
  return { ok: false, fieldErrors: { members } as FormikErrors<RosterValues>, formErrors };
}

export async function submitRoster(values: RosterValues): Promise<RosterResult> {
  const res = await fetch("/api/team-roster/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      [CSRF_HEADER]: csrfToken(),
    },
    body: JSON.stringify(values),
  });
  if (res.ok) {
    return { ok: true, fieldErrors: {}, formErrors: [] };
  }
  if (res.status === 400) {
    return mapErrors((await res.json()) as ServerPayload);
  }
  return { ok: false, fieldErrors: {}, formErrors: ["Could not save the roster."] };
}
