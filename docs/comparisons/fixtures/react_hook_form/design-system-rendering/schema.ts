// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

export const VISIBILITY = ["public", "private"] as const;
export type Visibility = (typeof VISIBILITY)[number];

// handle is shown + required only for public profiles (cross-field, so it lives
// in superRefine). email availability is async and checked against the API on
// blur and again on the server (see api.ts / form.tsx / server.py).
export const profileSchema = z
  .object({
    displayName: z.string().trim().min(1, "Display name is required."),
    email: z.string().trim().email("Enter a valid email address."),
    visibility: z.enum(VISIBILITY),
    handle: z.string().trim().optional().default(""),
  })
  .superRefine((data, ctx) => {
    if (data.visibility === "public") {
      const handle = data.handle ?? "";
      if (handle.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["handle"],
          message: "Public profiles need a handle.",
        });
      } else if (!/^[a-z0-9_]{3,20}$/.test(handle)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["handle"],
          message: "Handle must be 3–20 chars: lowercase letters, digits, underscore.",
        });
      }
    }
  });

export type ProfileInput = z.input<typeof profileSchema>;
export type ProfileValues = z.output<typeof profileSchema>;

export const profileDefaults: ProfileInput = {
  displayName: "",
  email: "",
  visibility: "private",
  handle: "",
};
