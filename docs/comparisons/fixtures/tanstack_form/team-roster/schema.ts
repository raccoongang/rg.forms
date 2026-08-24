// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
//
// NOTE: this competitor supports genuine dynamic add/remove of rows (mode="array"
// with pushValue/removeValue), unlike the rg.forms slice, which uses a *static*
// Django formset. The comparison should account for that capability difference.

import { z } from "zod";

export type MemberRole = "" | "owner" | "admin" | "editor" | "viewer";

export interface TeamMember {
  fullName: string;
  role: MemberRole;
  email: string; // required when role is owner/admin
  adminNote: string; // shown when role === "admin"
}

export interface TeamRosterValues {
  members: TeamMember[];
}

export const emptyMember: TeamMember = {
  fullName: "",
  role: "",
  email: "",
  adminNote: "",
};

export const defaultRosterValues: TeamRosterValues = {
  members: [{ ...emptyMember }],
};

export function emailRequiredFor(role: MemberRole): boolean {
  return role === "owner" || role === "admin";
}

const memberSchema = z
  .object({
    fullName: z.string().trim().min(1, "Full name is required."),
    role: z.enum(["owner", "admin", "editor", "viewer"], {
      errorMap: () => ({ message: "Select a role." }),
    }),
    email: z.string().trim().default(""),
    adminNote: z.string().trim().default(""),
  })
  .superRefine((m, ctx) => {
    if (emailRequiredFor(m.role)) {
      if (!m.email) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["email"], message: "Email is required for owners and admins." });
      } else if (!z.string().email().safeParse(m.email).success) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["email"], message: "Enter a valid email address." });
      }
    }
  });

export const rosterFormSchema = z.object({
  members: z.array(memberSchema).min(1, "Add at least one team member."),
});
