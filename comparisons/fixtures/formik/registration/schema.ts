// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import * as Yup from "yup";

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

export const initialValues: RegistrationValues = {
  username: "",
  email: "",
  password: "",
  passwordConfirm: "",
  accountType: "personal",
  companyEmail: "",
  agreeTerms: false,
};

// Free providers a business account may not register under. The server keeps the
// authoritative copy of this list; this is only the client-side preview.
const FREE_EMAIL_DOMAINS = [
  "gmail.com",
  "yahoo.com",
  "hotmail.com",
  "outlook.com",
  "mail.com",
];

const isFreeDomain = (email: string): boolean => {
  const at = email.lastIndexOf("@");
  if (at < 0) return false;
  return FREE_EMAIL_DOMAINS.includes(email.slice(at + 1).toLowerCase());
};

// Synchronous shape/format rules. Uniqueness (username/email) and the final
// free-domain check are asynchronous and/or server-authoritative — see api.ts
// and server.py. Formik runs this schema on change/blur/submit.
export const registrationSchema: Yup.SchemaOf<RegistrationValues> = Yup.object({
  username: Yup.string()
    .trim()
    .min(3, "Username must be at least 3 characters.")
    .max(30, "Username must be at most 30 characters.")
    .required("Username is required."),
  email: Yup.string()
    .trim()
    .email("Enter a valid email address.")
    .required("Email is required."),
  password: Yup.string()
    .min(8, "Password must be at least 8 characters.")
    .required("Password is required."),
  passwordConfirm: Yup.string()
    // Cross-field rule: must equal password.
    .oneOf([Yup.ref("password")], "Passwords do not match.")
    .required("Please confirm your password."),
  accountType: Yup.mixed<AccountType>()
    .oneOf(["personal", "business"])
    .required(),
  // Conditional requirement: only business accounts must provide a company email,
  // and it must not be a free provider.
  companyEmail: Yup.string().when("accountType", {
    is: "business",
    then: (s) =>
      s
        .trim()
        .email("Enter a valid company email.")
        .test(
          "not-free-domain",
          "Use a company email, not a free provider.",
          (v) => !v || !isFreeDomain(v),
        )
        .required("Business accounts must register a company email."),
    otherwise: (s) => s.notRequired(),
  }),
  agreeTerms: Yup.boolean().oneOf(
    [true],
    "You must accept the Terms of Service.",
  ),
});
