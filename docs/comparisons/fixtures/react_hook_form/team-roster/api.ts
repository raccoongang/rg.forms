// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
// NOTE: this competitor (RHF useFieldArray) supports dynamic add/remove of rows at runtime, unlike the rg.forms slice, which is a *static* Django formset (fixed rows).

import type { UseFormSetError } from "react-hook-form";
import type { RosterValues } from "./schema";

async function readCsrfToken(): Promise<string> {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

// The server returns per-row errors indexed by position:
//   { errors: { "members": ["..."], "members.0.email": ["..."], ... } }
export interface RosterFailure {
  ok: false;
  errors: Record<string, string[]>;
}

export interface RosterSuccess {
  ok: true;
}

export async function submitRoster(values: RosterValues): Promise<RosterSuccess | RosterFailure> {
  const res = await fetch("/api/team-roster/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": await readCsrfToken(),
    },
    body: JSON.stringify(values),
  });

  if (res.ok) return { ok: true };

  if (res.status === 400) {
    const body = (await res.json()) as { errors: Record<string, string[]> };
    return { ok: false, errors: body.errors ?? {} };
  }

  return { ok: false, errors: { root: [`Unexpected error (${res.status}).`] } };
}

// Server error keys use dotted paths ("members.2.email"); RHF's setError accepts
// exactly that dotted form to target a field-array member's field.
export function applyServerErrors(
  errors: Record<string, string[]>,
  setError: UseFormSetError<RosterValues>,
): void {
  for (const [field, messages] of Object.entries(errors)) {
    const message = messages.join(" ");
    if (field === "__all__" || field === "root") {
      setError("root", { type: "server", message });
    } else {
      // e.g. "members.0.email" -> a specific row field; "members" -> array root
      setError(field as never, { type: "server", message });
    }
  }
}
