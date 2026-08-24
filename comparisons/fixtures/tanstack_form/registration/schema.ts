// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

// The account type drives conditional visibility + requiredness of companyEmail.
export type AccountType = "personal" | "business";

export interface RegistrationValues {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  accountType: AccountType;
  companyEmail: string;
  agreeTerms: boolean;
}

export const defaultRegistrationValues: RegistrationValues = {
  username: "",
  email: "",
  password: "",
  passwordConfirm: "",
  accountType: "personal",
  companyEmail: "",
  agreeTerms: false,
};

// Free providers are rejected for business company emails (mirrors the server list).
const FREE_EMAIL_DOMAINS = new Set([
  "gmail.com",
  "yahoo.com",
  "hotmail.com",
  "outlook.com",
  "mail.com",
]);

export function isFreeEmailDomain(email: string): boolean {
  const at = email.lastIndexOf("@");
  if (at < 0) return false;
  return FREE_EMAIL_DOMAINS.has(email.slice(at + 1).toLowerCase());
}

// Per-field synchronous validators. Availability (username/email uniqueness) is a
// separate async validator wired in form.tsx — it cannot live in a static schema.
export const usernameSchema = z
  .string()
  .trim()
  .min(3, "Username must be at least 3 characters.")
  .max(30, "Username must be at most 30 characters.");

export const emailSchema = z.string().trim().email("Enter a valid email address.");

export const passwordSchema = z.string().min(8, "Password must be at least 8 characters.");

// Cross-field rules live in a form-level schema because a single field validator
// cannot see sibling values. `.superRefine` lets us attach errors to a path.
export const registrationFormSchema = z
  .object({
    username: usernameSchema,
    email: emailSchema,
    password: passwordSchema,
    passwordConfirm: z.string(),
    accountType: z.enum(["personal", "business"]),
    companyEmail: z.string().trim().default(""),
    agreeTerms: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.password && v.password !== v.passwordConfirm) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["passwordConfirm"],
        message: "Passwords do not match.",
      });
    }
    if (v.accountType === "business") {
      if (!v.companyEmail) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "A company email is required for business accounts.",
        });
      } else if (!z.string().email().safeParse(v.companyEmail).success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "Enter a valid company email address.",
        });
      } else if (isFreeEmailDomain(v.companyEmail)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "Use a company email, not a free provider.",
        });
      }
    }
    if (!v.agreeTerms) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["agreeTerms"],
        message: "You must accept the Terms of Service.",
      });
    }
  });
