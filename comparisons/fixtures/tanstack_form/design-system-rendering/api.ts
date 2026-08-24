// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { ProfileValues } from "./schema";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// Async email availability check, wired into the email field's onBlurAsync.
export async function checkEmail(email: string): Promise<string | undefined> {
  const value = email.trim();
  if (!value.includes("@")) return undefined;
  const res = await fetch(`/api/profile/check-email/?email=${encodeURIComponent(value)}`);
  const data = (await res.json()) as { available: boolean };
  return data.available ? undefined : "That email is already registered.";
}

export async function submitProfile(values: ProfileValues): Promise<Record<string, string>> {
  const res = await fetch("/api/profile/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(values),
  });
  const data = (await res.json()) as { ok: boolean; errors?: Record<string, string[]> };
  if (data.ok) return {};
  return Object.fromEntries(
    Object.entries(data.errors ?? {}).map(([f, msgs]) => [f, msgs[0] ?? "Invalid value."]),
  );
}
