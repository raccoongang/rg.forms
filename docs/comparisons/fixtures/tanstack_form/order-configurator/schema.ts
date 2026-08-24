// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { z } from "zod";

// Plan codes are leading-zero strings on purpose ("001" must stay "001").
export type PlanCode = "" | "001" | "010" | "100";

export interface Plan {
  code: Exclude<PlanCode, "">;
  name: string;
  unitPrice: string; // decimal string; parsed to cents client-side, exact on server
  help: string;
}

export const PLANS: Plan[] = [
  { code: "001", name: "Starter", unitPrice: "9.00", help: "Starter is a single-seat plan." },
  { code: "010", name: "Team", unitPrice: "29.00", help: "Team plans start at 1 seat." },
  {
    code: "100",
    name: "Enterprise",
    unitPrice: "99.00",
    help: "Enterprise seats are negotiated with your account manager.",
  },
];

export function planByCode(code: PlanCode): Plan | undefined {
  return PLANS.find((p) => p.code === code);
}

export interface OrderValues {
  plan: PlanCode;
  enterpriseContact: string; // shown + required when plan === "100"
  seats: number; // disabled when plan === "001" (single seat)
  coupon: string;
}

export const defaultOrderValues: OrderValues = {
  plan: "",
  enterpriseContact: "",
  seats: 1,
  coupon: "",
};

// Valid coupons (mirrors the server table). Client validation is a preview only.
export const VALID_COUPONS: Record<string, number> = {
  WELCOME10: 10,
  SAVE20: 20,
  LAUNCH50: 50,
};

export function couponDiscount(code: string): number | undefined {
  return VALID_COUPONS[code.trim().toUpperCase()];
}

// Client-side derived preview of the unit price for the selected plan.
export function unitPriceFor(plan: PlanCode): number {
  const p = planByCode(plan);
  return p ? Number(p.unitPrice) : 0;
}

// Preview total in cents to avoid float drift in the UI; the server recomputes
// the authoritative Decimal total regardless of anything the client sends.
export function previewTotalCents(plan: PlanCode, seats: number): number {
  return Math.round(unitPriceFor(plan) * 100) * Math.max(0, seats);
}

export function formatCents(cents: number): string {
  return (cents / 100).toFixed(2);
}

export const orderFormSchema = z
  .object({
    plan: z.enum(["001", "010", "100"], { errorMap: () => ({ message: "Select a plan." }) }),
    enterpriseContact: z.string().trim().default(""),
    seats: z.number().int().min(1, "At least one seat is required."),
    coupon: z.string().trim().default(""),
  })
  .superRefine((v, ctx) => {
    if (v.plan === "100" && !v.enterpriseContact) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["enterpriseContact"],
        message: "Enterprise orders need an account-manager contact.",
      });
    }
    if (v.coupon && couponDiscount(v.coupon) === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["coupon"],
        message: `Coupon '${v.coupon}' is not valid.`,
      });
    }
  });
