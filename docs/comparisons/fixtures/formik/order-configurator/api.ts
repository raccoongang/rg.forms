// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { FormikErrors } from "formik";
import type { OrderValues } from "./schema";

const CSRF_HEADER = "X-CSRFToken";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// --- Coupon validation (called onBlur from the coupon field) ---------------
export interface CouponResult {
  valid: boolean;
  discountPercent: number; // 0 when not valid / not applied
  message: string | null;
}

export async function validateCoupon(code: string): Promise<CouponResult> {
  const value = code.trim();
  if (!value) return { valid: true, discountPercent: 0, message: null };
  const res = await fetch(
    `/api/order/validate-coupon/?code=${encodeURIComponent(value)}`,
  );
  if (!res.ok) return { valid: true, discountPercent: 0, message: null };
  const data: CouponResult = await res.json();
  return data;
}

// --- Submit ----------------------------------------------------------------
// The server returns the authoritative Decimal totals; the client preview is
// discarded. On error it returns Django-style field errors.
export interface OrderConfirmation {
  ok: true;
  plan: string;
  seats: number;
  unitPrice: string;
  total: string; // authoritative Decimal, as a string
  discountedTotal: string;
}

export interface OrderRejection {
  ok: false;
  fieldErrors: FormikErrors<OrderValues>;
  formErrors: string[];
}

export type OrderResult = OrderConfirmation | OrderRejection;

function mapErrors(errors: Record<string, string[]>): OrderRejection {
  const fieldErrors: FormikErrors<OrderValues> = {};
  const formErrors: string[] = [];
  for (const [field, messages] of Object.entries(errors)) {
    if (field === "__all__") {
      formErrors.push(...messages);
    } else {
      const key = field === "enterprise_contact" ? "enterpriseContact" : field;
      (fieldErrors as Record<string, string>)[key] = messages.join(" ");
    }
  }
  return { ok: false, fieldErrors, formErrors };
}

export async function submitOrder(values: OrderValues): Promise<OrderResult> {
  const res = await fetch("/api/order/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      [CSRF_HEADER]: csrfToken(),
    },
    body: JSON.stringify(values),
  });
  if (res.ok) {
    return (await res.json()) as OrderConfirmation;
  }
  if (res.status === 400) {
    const data: { errors: Record<string, string[]> } = await res.json();
    return mapErrors(data.errors);
  }
  return { ok: false, fieldErrors: {}, formErrors: ["Could not place the order."] };
}
