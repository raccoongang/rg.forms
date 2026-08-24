// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

// Free providers are rejected for business accounts. The server keeps the
// authoritative copy of this list; the client duplicates it for fast feedback.
const FREE_EMAIL_DOMAINS = new Set([
  "gmail.com",
  "yahoo.com",
  "hotmail.com",
  "outlook.com",
  "mail.com",
]);

export const ACCOUNT_TYPES = ["personal", "business"] as const;

function emailDomain(email: string): string {
  const at = email.lastIndexOf("@");
  return at === -1 ? "" : email.slice(at + 1).toLowerCase();
}

// Client-side validation. Cross-field rules (password match, the conditional
// company email) live in .superRefine because a single field schema cannot see
// its siblings. Uniqueness / availability are async and cannot run here — they
// are checked against the API on blur and again on the server (see api.ts,
// form.tsx, server.py).
export const registrationSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(3, "Username must be at least 3 characters.")
      .max(30, "Username must be at most 30 characters."),
    email: z.string().trim().email("Enter a valid email address."),
    password: z.string().min(8, "Password must be at least 8 characters."),
    passwordConfirm: z.string(),
    accountType: z.enum(ACCOUNT_TYPES),
    // Optional in the base shape; promoted to required for business accounts
    // in superRefine below so the message lands on the right field.
    companyEmail: z.string().trim().optional().default(""),
    agreeTerms: z.literal(true, {
      errorMap: () => ({ message: "You must accept the Terms of Service." }),
    }),
  })
  .superRefine((data, ctx) => {
    if (data.password !== data.passwordConfirm) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["passwordConfirm"],
        message: "Passwords do not match.",
      });
    }

    if (data.accountType === "business") {
      const value = data.companyEmail ?? "";
      if (value.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "Business accounts require a company email.",
        });
      } else if (!z.string().email().safeParse(value).success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "Enter a valid company email address.",
        });
      } else if (FREE_EMAIL_DOMAINS.has(emailDomain(value))) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["companyEmail"],
          message: "Use a company email, not a free provider.",
        });
      }
    }
  });

// The resolver's input type (what the form fields carry) differs slightly from
// the parsed output because of .default(); RHF wants the input side.
export type RegistrationInput = z.input<typeof registrationSchema>;
export type RegistrationValues = z.output<typeof registrationSchema>;

export const registrationDefaults: RegistrationInput = {
  username: "",
  email: "",
  password: "",
  passwordConfirm: "",
  accountType: "personal",
  companyEmail: "",
  agreeTerms: false as unknown as true, // starts unchecked; z.literal(true) enforces the tick
};
