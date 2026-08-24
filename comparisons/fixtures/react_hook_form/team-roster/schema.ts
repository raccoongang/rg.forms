// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
// NOTE: this competitor (RHF useFieldArray) supports dynamic add/remove of rows at runtime, unlike the rg.forms slice, which is a *static* Django formset (fixed rows). The schema therefore models a variable-length array.

import { z } from "zod";

export const ROLES = ["owner", "admin", "editor", "viewer"] as const;
export type Role = (typeof ROLES)[number];

// email required when role is owner/admin; adminNote surfaced only for admins.
// Both are per-row cross-field rules, so they live in superRefine on the row.
export const memberSchema = z
  .object({
    fullName: z.string().trim().min(1, "Full name is required."),
    role: z.enum(ROLES, { errorMap: () => ({ message: "Select a role." }) }),
    email: z.string().trim().optional().default(""),
    adminNote: z.string().trim().optional().default(""),
  })
  .superRefine((row, ctx) => {
    const needsEmail = row.role === "owner" || row.role === "admin";
    if (needsEmail) {
      if ((row.email ?? "").length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["email"],
          message: "Owners and admins must provide an email.",
        });
      } else if (!z.string().email().safeParse(row.email).success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["email"],
          message: "Enter a valid email address.",
        });
      }
    }
  });

export const rosterSchema = z.object({
  members: z.array(memberSchema).min(1, "Add at least one team member."),
});

export type MemberInput = z.input<typeof memberSchema>;
export type RosterInput = z.input<typeof rosterSchema>;
export type RosterValues = z.output<typeof rosterSchema>;

export const emptyMember: MemberInput = {
  fullName: "",
  role: "viewer",
  email: "",
  adminNote: "",
};

export const rosterDefaults: RosterInput = {
  members: [{ ...emptyMember }],
};
