// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import * as Yup from "yup";

// Plan codes are numeric-looking strings with a leading zero on purpose:
// "001" must stay the string "001", never the number 1.
export type PlanCode = "001" | "010" | "100";

export interface Plan {
  code: PlanCode;
  name: string;
  unitPrice: string; // decimal as string to avoid float drift in the preview
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

export interface OrderValues {
  plan: PlanCode | "";
  enterpriseContact: string;
  seats: number;
  coupon: string;
}

export const initialValues: OrderValues = {
  plan: "",
  enterpriseContact: "",
  seats: 1,
  coupon: "",
};

// Preview helpers. The server recomputes the authoritative Decimal total; these
// exist only to show a live preview in the browser.
export const unitPriceFor = (plan: PlanCode | ""): string =>
  plan ? PLANS[plan].unitPrice : "0.00";

export const previewTotal = (plan: PlanCode | "", seats: number): string => {
  const price = Number(unitPriceFor(plan));
  return (price * (seats || 0)).toFixed(2);
};

export const helpTextFor = (plan: PlanCode | ""): string =>
  plan ? PLANS[plan].help : "Select a plan to see pricing.";

export const orderSchema: Yup.SchemaOf<OrderValues> = Yup.object({
  plan: Yup.mixed<PlanCode>()
    .oneOf(["001", "010", "100"], "Select a plan.")
    .required("Select a plan."),
  // Conditional requirement tied to the Enterprise plan code.
  enterpriseContact: Yup.string().when("plan", {
    is: "100",
    then: (s) => s.trim().required("Enterprise orders need a contact name."),
    otherwise: (s) => s.notRequired(),
  }),
  seats: Yup.number()
    .typeError("Seats must be a number.")
    .integer("Seats must be a whole number.")
    .min(1, "At least one seat is required.")
    .required("Seats are required."),
  // Coupon is optional; its validity is confirmed by the server (see api.ts).
  coupon: Yup.string().notRequired(),
});
