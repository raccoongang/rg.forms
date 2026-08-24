// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { UseFormSetError } from "react-hook-form";
import type { RegistrationValues } from "./schema";

// Shape the Django view returns on a 400 (see server.py): a flat map of
// field name -> list of messages, plus an optional form-level list under
// the "__all__" key (Django's NON_FIELD_ERRORS).
export interface DjangoErrorResponse {
  errors: Record<string, string[]>;
}

async function readCsrfToken(): Promise<string> {
  // Django's standard cookie-based CSRF; in a real app this is read once.
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

// --- Async availability checks (called on blur from form.tsx) ---------------

export interface AvailabilityResult {
  available: boolean;
  message?: string;
}

export async function checkUsername(username: string): Promise<AvailabilityResult> {
  const value = username.trim();
  if (value.length < 3) return { available: true };
  const res = await fetch(`/api/registration/check-username/?username=${encodeURIComponent(value)}`);
  if (!res.ok) return { available: true }; // fail open on the client; server re-checks
  return (await res.json()) as AvailabilityResult;
}

export async function checkEmail(email: string): Promise<AvailabilityResult> {
  const value = email.trim();
  if (!value.includes("@")) return { available: true };
  const res = await fetch(`/api/registration/check-email/?email=${encodeURIComponent(value)}`);
  if (!res.ok) return { available: true };
  return (await res.json()) as AvailabilityResult;
}

// --- Submit ------------------------------------------------------------------

export interface SubmitSuccess {
  ok: true;
}

export interface SubmitFailure {
  ok: false;
  errors: Record<string, string[]>;
}

export async function submitRegistration(
  values: RegistrationValues,
): Promise<SubmitSuccess | SubmitFailure> {
  const res = await fetch("/api/registration/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": await readCsrfToken(),
    },
    body: JSON.stringify(values),
  });

  if (res.ok) return { ok: true };

  if (res.status === 400) {
    const body = (await res.json()) as DjangoErrorResponse;
    return { ok: false, errors: body.errors ?? {} };
  }

  return { ok: false, errors: { root: [`Unexpected error (${res.status}).`] } };
}

// Map a Django field-error map onto RHF via setError. Keys unknown to the form
// (e.g. Django's "__all__") are folded into the form-level "root" error so the
// user still sees them.
export function applyServerErrors(
  errors: Record<string, string[]>,
  setError: UseFormSetError<RegistrationValues>,
  knownFields: ReadonlyArray<keyof RegistrationValues>,
): void {
  const known = new Set<string>(knownFields as readonly string[]);
  for (const [field, messages] of Object.entries(errors)) {
    const message = messages.join(" ");
    if (field === "__all__" || field === "root" || !known.has(field)) {
      setError("root", { type: "server", message });
    } else {
      setError(field as keyof RegistrationValues, { type: "server", message });
    }
  }
}
