// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { UseFormSetError } from "react-hook-form";
import type { ProfileValues } from "./schema";

async function readCsrfToken(): Promise<string> {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export interface AvailabilityResult {
  available: boolean;
  message?: string;
}

// Async email-availability probe, called on blur from form.tsx.
export async function checkEmail(email: string): Promise<AvailabilityResult> {
  const value = email.trim();
  if (!value.includes("@")) return { available: true };
  const res = await fetch(`/api/profile/check-email/?email=${encodeURIComponent(value)}`);
  if (!res.ok) return { available: true }; // fail open; server re-checks
  return (await res.json()) as AvailabilityResult;
}

export interface ProfileSuccess {
  ok: true;
}

export interface ProfileFailure {
  ok: false;
  errors: Record<string, string[]>;
}

export async function submitProfile(values: ProfileValues): Promise<ProfileSuccess | ProfileFailure> {
  const res = await fetch("/api/profile/", {
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

export function applyServerErrors(
  errors: Record<string, string[]>,
  setError: UseFormSetError<ProfileValues>,
  knownFields: ReadonlyArray<keyof ProfileValues>,
): void {
  const known = new Set<string>(knownFields as readonly string[]);
  for (const [field, messages] of Object.entries(errors)) {
    const message = messages.join(" ");
    if (field === "__all__" || field === "root" || !known.has(field)) {
      setError("root", { type: "server", message });
    } else {
      setError(field as keyof ProfileValues, { type: "server", message });
    }
  }
}
