// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { OrderValues } from "./schema";

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

// The server is authoritative for the total: it recomputes the exact Decimal
// and applies any coupon. The client only ever renders a preview.
export interface OrderResult {
  ok: boolean;
  errors: Record<string, string>;
  // present on success:
  total?: string; // exact decimal string, e.g. "290.00"
  discountedTotal?: string;
}

export async function submitOrder(values: OrderValues): Promise<OrderResult> {
  const res = await fetch("/api/order/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(values),
  });
  const data = (await res.json()) as {
    ok: boolean;
    errors?: Record<string, string[]>;
    total?: string;
    discounted_total?: string;
  };
  return {
    ok: data.ok,
    errors: Object.fromEntries(
      Object.entries(data.errors ?? {}).map(([f, msgs]) => [f, msgs[0] ?? "Invalid value."]),
    ),
    total: data.total,
    discountedTotal: data.discounted_total,
  };
}

// Optional async coupon validation against the server (authoritative), used by
// the coupon field's onBlurAsync so a coupon retired server-side is caught even
// if the client's static table still lists it.
export async function validateCoupon(code: string): Promise<string | undefined> {
  const value = code.trim();
  if (!value) return undefined;
  const res = await fetch(`/api/order/check-coupon/?code=${encodeURIComponent(value)}`);
  const data = (await res.json()) as { valid: boolean };
  return data.valid ? undefined : `Coupon '${value}' is not valid.`;
}
