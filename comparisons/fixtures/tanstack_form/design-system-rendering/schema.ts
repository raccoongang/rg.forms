// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

export type Visibility = "public" | "private";

export interface ProfileValues {
  displayName: string;
  email: string;
  visibility: Visibility;
  handle: string; // shown + required when visibility === "public"
}

export const defaultProfileValues: ProfileValues = {
  displayName: "",
  email: "",
  visibility: "private",
  handle: "",
};

export const displayNameSchema = z.string().trim().min(1, "Display name is required.");
export const emailSchema = z.string().trim().email("Enter a valid email address.");
// A public handle: letters, digits and underscores only.
export const handleSchema = z
  .string()
  .trim()
  .min(3, "Handle must be at least 3 characters.")
  .regex(/^[a-zA-Z0-9_]+$/, "Use letters, digits and underscores only.");

export const profileFormSchema = z
  .object({
    displayName: displayNameSchema,
    email: emailSchema,
    visibility: z.enum(["public", "private"]),
    handle: z.string().trim().default(""),
  })
  .superRefine((v, ctx) => {
    if (v.visibility === "public") {
      const res = handleSchema.safeParse(v.handle);
      if (!res.success) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["handle"],
          message: v.handle ? res.error.issues[0]?.message ?? "Invalid handle." : "A public handle is required.",
        });
      }
    }
  });
