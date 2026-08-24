// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { FormikErrors } from "formik";
import type { ProfileValues } from "./schema";

const CSRF_HEADER = "X-CSRFToken";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// Async availability check for the email field (called onBlur).
export async function checkEmail(email: string): Promise<string | null> {
  const value = email.trim();
  if (!value.includes("@")) return null;
  const res = await fetch(
    `/api/profile/check-email/?email=${encodeURIComponent(value)}`,
  );
  if (!res.ok) return null;
  const data: { available: boolean } = await res.json();
  return data.available ? null : "That email is already registered.";
}

export interface ProfileResult {
  ok: boolean;
  fieldErrors: FormikErrors<ProfileValues>;
  formErrors: string[];
}

function mapErrors(errors: Record<string, string[]>): ProfileResult {
  const fieldErrors: FormikErrors<ProfileValues> = {};
  const formErrors: string[] = [];
  for (const [field, messages] of Object.entries(errors)) {
    if (field === "__all__") {
      formErrors.push(...messages);
    } else {
      const key = field === "display_name" ? "displayName" : field;
      (fieldErrors as Record<string, string>)[key] = messages.join(" ");
    }
  }
  return { ok: false, fieldErrors, formErrors };
}

export async function submitProfile(values: ProfileValues): Promise<ProfileResult> {
  const res = await fetch("/api/profile/", {
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
    const data: { errors: Record<string, string[]> } = await res.json();
    return mapErrors(data.errors);
  }
  return { ok: false, fieldErrors: {}, formErrors: ["Could not save the profile."] };
}
