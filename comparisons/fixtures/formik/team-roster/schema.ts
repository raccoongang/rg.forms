// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
// NOTE: this Formik fixture supports dynamic add/remove/reorder of rows via
// FieldArray. The rg.forms slice it is compared against renders a *static*
// Django formset (fixed row set), so this competitor covers a superset here.

import * as Yup from "yup";

export type Role = "owner" | "admin" | "editor" | "viewer";

export interface TeamMember {
  fullName: string;
  role: Role | "";
  email: string;
  adminNote: string;
}

export interface RosterValues {
  members: TeamMember[];
}

export const emptyMember: TeamMember = {
  fullName: "",
  role: "",
  email: "",
  adminNote: "",
};

export const initialValues: RosterValues = {
  members: [{ ...emptyMember }],
};

const requiresEmail = (role: Role | ""): boolean =>
  role === "owner" || role === "admin";

// Each row validates independently. email is conditionally required by role;
// adminNote is only meaningful for admins (visibility is a rendering concern,
// handled in form.tsx).
const memberSchema: Yup.SchemaOf<TeamMember> = Yup.object({
  fullName: Yup.string().trim().required("Full name is required."),
  role: Yup.mixed<Role>()
    .oneOf(["owner", "admin", "editor", "viewer"], "Select a role.")
    .required("Select a role."),
  email: Yup.string()
    .trim()
    .email("Enter a valid email.")
    .when("role", {
      is: (role: Role | "") => requiresEmail(role),
      then: (s) => s.required("Owners and admins must have an email."),
      otherwise: (s) => s.notRequired(),
    }),
  adminNote: Yup.string().notRequired(),
});

export const rosterSchema: Yup.SchemaOf<RosterValues> = Yup.object({
  members: Yup.array()
    .of(memberSchema)
    .min(1, "Add at least one team member."),
});
