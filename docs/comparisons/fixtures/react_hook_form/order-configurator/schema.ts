// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

// Plan codes are numeric-looking strings with a leading zero ("001"); they must
// stay strings so "001" never collapses to the number 1.
export const PLAN_CODES = ["001", "010", "100"] as const;
export type PlanCode = (typeof PLAN_CODES)[number];

export interface Plan {
  code: PlanCode;
  name: string;
  unitPrice: string; // decimal string; never a JS float in the source of truth
  help: string;
}

export const PLANS: Record<PlanCode, Plan> = {
  "001": { code: "001", name: "Starter", unitPrice: "9.00", help: "Starter is a single-seat plan." },
  "010": { code: "010", name: "Team", unitPrice: "29.00", help: "Team plans start at 1 seat." },
  "100": {
    code: "100",
    name: "Enterprise",
    unitPrice: "99.00",
    help: "Enterprise seats are negotiated with your account manager.",
  },
};

export const VALID_COUPONS = new Set(["WELCOME10", "SAVE20", "LAUNCH50"]);

export const orderSchema = z
  .object({
    plan: z.enum(PLAN_CODES, { errorMap: () => ({ message: "Select a plan." }) }),
    // Shown + required only for Enterprise (see form.tsx / superRefine).
    enterpriseContact: z.string().trim().optional().default(""),
    seats: z.coerce
      .number({ invalid_type_error: "Seats must be a number." })
      .int("Seats must be a whole number.")
      .min(1, "At least one seat is required."),
    coupon: z.string().trim().optional().default(""),
  })
  .superRefine((data, ctx) => {
    if (data.plan === "100" && (data.enterpriseContact ?? "").length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["enterpriseContact"],
        message: "Enterprise orders require a contact name.",
      });
    }

    const coupon = (data.coupon ?? "").toUpperCase();
    if (coupon.length > 0 && !VALID_COUPONS.has(coupon)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["coupon"],
        message: `Coupon '${coupon}' is not valid.`,
      });
    }
  });

export type OrderInput = z.input<typeof orderSchema>;
export type OrderValues = z.output<typeof orderSchema>;

export const orderDefaults: OrderInput = {
  plan: "001",
  enterpriseContact: "",
  seats: 1,
  coupon: "",
};

// Client-side preview total. Deliberately a JS-number multiplication so the
// comparison can show the client value is a *preview* only — the server
// recomputes the authoritative Decimal (see server.py).
export function previewTotal(plan: PlanCode | "", seats: number): string {
  if (!plan || !PLANS[plan as PlanCode]) return "0.00";
  const unit = Number.parseFloat(PLANS[plan as PlanCode].unitPrice);
  const n = Number.isFinite(seats) ? seats : 0;
  return (unit * n).toFixed(2);
}
