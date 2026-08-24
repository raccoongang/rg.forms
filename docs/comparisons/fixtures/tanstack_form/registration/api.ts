// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { RegistrationValues } from "./schema";

// The Django JSON view returns {ok: false, errors: {field: [msg, ...]}} on
// failure (mirrors Django's Form.errors shape) and {ok: true} on success.
export interface FieldErrorResponse {
  ok: false;
  errors: Record<string, string[]>;
}
export interface OkResponse {
  ok: true;
}
export type ApiResponse = OkResponse | FieldErrorResponse;

// Read the CSRF token Django sets as a cookie so POSTs are accepted.
function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

async function postJson(url: string, body: unknown): Promise<ApiResponse> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(body),
  });
  return (await res.json()) as ApiResponse;
}

// --- Async availability checks (called from onChangeAsync / onBlurAsync) -----
// Each returns a single error string, or undefined when the value is available.
// TanStack treats a returned string as the field error and undefined as valid.

export async function checkUsername(username: string): Promise<string | undefined> {
  const value = username.trim();
  if (value.length < 3) return undefined; // let the sync validator report length
  const res = await fetch(
    `/api/registration/check-username/?username=${encodeURIComponent(value)}`,
  );
  const data = (await res.json()) as { available: boolean };
  return data.available ? undefined : `The username '${value}' is already taken.`;
}

export async function checkEmail(email: string): Promise<string | undefined> {
  const value = email.trim();
  if (!value.includes("@")) return undefined;
  const res = await fetch(
    `/api/registration/check-email/?email=${encodeURIComponent(value)}`,
  );
  const data = (await res.json()) as { available: boolean };
  return data.available ? undefined : "An account with this email already exists.";
}

// --- Final submit ------------------------------------------------------------
// Returns a per-field error map (empty when the submit succeeded) so the caller
// can push server errors back onto the matching TanStack fields.
export async function submitRegistration(
  values: RegistrationValues,
): Promise<Record<string, string>> {
  const data = await postJson("/api/registration/", values);
  if (data.ok) return {};
  // Django gives a list of messages per field; the form shows the first.
  return Object.fromEntries(
    Object.entries(data.errors).map(([field, msgs]) => [field, msgs[0] ?? "Invalid value."]),
  );
}
