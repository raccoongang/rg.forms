// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { UseFormSetError } from "react-hook-form";
import type { OrderValues } from "./schema";

async function readCsrfToken(): Promise<string> {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export interface OrderConfirmation {
  ok: true;
  // The server returns the authoritative Decimal total as a string. The client
  // preview is discarded in favour of this value.
  total: string;
  discountedTotal: string;
}

export interface OrderFailure {
  ok: false;
  errors: Record<string, string[]>;
}

export async function submitOrder(values: OrderValues): Promise<OrderConfirmation | OrderFailure> {
  const res = await fetch("/api/order/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": await readCsrfToken(),
    },
    // Note we do NOT send a client total: the server owns the money math.
    body: JSON.stringify({
      plan: values.plan,
      enterpriseContact: values.enterpriseContact,
      seats: values.seats,
      coupon: values.coupon,
    }),
  });

  if (res.ok) {
    const body = (await res.json()) as { total: string; discountedTotal: string };
    return { ok: true, total: body.total, discountedTotal: body.discountedTotal };
  }

  if (res.status === 400) {
    const body = (await res.json()) as { errors: Record<string, string[]> };
    return { ok: false, errors: body.errors ?? {} };
  }

  return { ok: false, errors: { root: [`Unexpected error (${res.status}).`] } };
}

export function applyServerErrors(
  errors: Record<string, string[]>,
  setError: UseFormSetError<OrderValues>,
  knownFields: ReadonlyArray<keyof OrderValues>,
): void {
  const known = new Set<string>(knownFields as readonly string[]);
  for (const [field, messages] of Object.entries(errors)) {
    const message = messages.join(" ");
    if (field === "__all__" || field === "root" || !known.has(field)) {
      setError("root", { type: "server", message });
    } else {
      setError(field as keyof OrderValues, { type: "server", message });
    }
  }
}
