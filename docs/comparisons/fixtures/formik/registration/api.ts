// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { FormikErrors } from "formik";
import type { RegistrationValues } from "./schema";

// Shape of the JSON the Django view returns on a failed submit:
// { "errors": { "<field>": ["message", ...], "__all__": ["message"] } }
interface ServerErrorPayload {
  errors?: Record<string, string[]>;
}

const CSRF_HEADER = "X-CSRFToken";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// --- Async availability checks (called onBlur from the form) ----------------
// Each returns an error message if unavailable, or null if the field is free.

export async function checkUsername(username: string): Promise<string | null> {
  const value = username.trim();
  if (value.length < 3) return null; // format handled by the sync schema
  const res = await fetch(
    `/api/registration/check-username/?username=${encodeURIComponent(value)}`,
  );
  if (!res.ok) return null; // fail open on transport error; submit re-checks
  const data: { available: boolean } = await res.json();
  return data.available ? null : `The username '${value}' is already taken.`;
}

export async function checkEmail(email: string): Promise<string | null> {
  const value = email.trim();
  if (!value.includes("@")) return null;
  const res = await fetch(
    `/api/registration/check-email/?email=${encodeURIComponent(value)}`,
  );
  if (!res.ok) return null;
  const data: { available: boolean } = await res.json();
  return data.available ? null : "An account with this email already exists.";
}

// --- Submit + error mapping -------------------------------------------------

export interface SubmitResult {
  ok: boolean;
  // Field-scoped errors ready to hand to Formik's setErrors.
  fieldErrors: FormikErrors<RegistrationValues>;
  // Non-field ("__all__") errors the form can render as a banner.
  formErrors: string[];
}

// Map Django's {field: [messages]} to Formik's flat {field: message}. Django
// returns a list per field; Formik shows one string, so we join.
function mapErrors(payload: ServerErrorPayload): SubmitResult {
  const fieldErrors: FormikErrors<RegistrationValues> = {};
  const formErrors: string[] = [];
  const errors = payload.errors ?? {};
  for (const [field, messages] of Object.entries(errors)) {
    if (field === "__all__") {
      formErrors.push(...messages);
    } else {
      // Django uses snake_case; the form uses camelCase.
      const key = field === "company_email"
        ? "companyEmail"
        : field === "password_confirm"
          ? "passwordConfirm"
          : field === "account_type"
            ? "accountType"
            : field === "agree_terms"
              ? "agreeTerms"
              : field;
      (fieldErrors as Record<string, string>)[key] = messages.join(" ");
    }
  }
  return { ok: false, fieldErrors, formErrors };
}

// The Django view (server.py) revalidates every rule the client declared.
export async function submitRegistration(
  values: RegistrationValues,
): Promise<SubmitResult> {
  const res = await fetch("/api/registration/", {
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
    return mapErrors((await res.json()) as ServerErrorPayload);
  }
  return { ok: false, fieldErrors: {}, formErrors: ["Something went wrong. Please try again."] };
}
