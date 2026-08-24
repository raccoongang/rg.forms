// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  orderSchema,
  orderDefaults,
  previewTotal,
  PLANS,
  type OrderInput,
  type OrderValues,
  type PlanCode,
} from "./schema";
import { submitOrder, applyServerErrors } from "./api";

const KNOWN_FIELDS = ["plan", "enterpriseContact", "seats", "coupon"] as const;

export function OrderConfiguratorForm() {
  const [confirmedTotal, setConfirmedTotal] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<OrderInput, unknown, OrderValues>({
    resolver: zodResolver(orderSchema),
    mode: "onChange",
    defaultValues: orderDefaults,
  });

  // Reactive reads: plan drives visibility, disabled state, help text and unit
  // price; seats + plan drive the live preview total. All wired by hand.
  const plan = watch("plan") as PlanCode | "";
  const seats = Number(watch("seats"));

  const selectedPlan = plan ? PLANS[plan as PlanCode] : undefined;
  const isEnterprise = plan === "100";
  const seatsDisabled = plan === "001"; // Starter is single-seat
  const unitPrice = selectedPlan?.unitPrice ?? "0.00";
  const help = selectedPlan?.help ?? "";
  const total = previewTotal(plan, seats); // preview only; server is authoritative

  const onSubmit = async (values: OrderValues) => {
    const result = await submitOrder(values);
    if (result.ok) {
      setConfirmedTotal(result.total);
    } else {
      applyServerErrors(result.errors, setError, KNOWN_FIELDS);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {errors.root && <p role="alert">{errors.root.message}</p>}

      <div>
        <label htmlFor="plan">Plan</label>
        <select id="plan" {...register("plan")}>
          {(Object.values(PLANS) as (typeof PLANS)[PlanCode][]).map((p) => (
            <option key={p.code} value={p.code}>
              {p.name}
            </option>
          ))}
        </select>
        {errors.plan && <span role="alert">{errors.plan.message}</span>}
      </div>

      {isEnterprise && (
        <div>
          <label htmlFor="enterpriseContact">Enterprise contact</label>
          <input id="enterpriseContact" {...register("enterpriseContact")} />
          {errors.enterpriseContact && <span role="alert">{errors.enterpriseContact.message}</span>}
        </div>
      )}

      <div>
        <label htmlFor="seats">Seats</label>
        <input
          id="seats"
          type="number"
          min={1}
          disabled={seatsDisabled}
          {...register("seats")}
        />
        {help && <small>{help}</small>}
        {errors.seats && <span role="alert">{errors.seats.message}</span>}
      </div>

      <div>
        <label htmlFor="unitPrice">Unit price</label>
        {/* Display-only, derived from the plan. Not a registered field. */}
        <output id="unitPrice">{unitPrice}</output>
      </div>

      <div>
        <label htmlFor="coupon">Coupon</label>
        <input id="coupon" {...register("coupon")} placeholder="WELCOME10 or SAVE20" />
        {errors.coupon && <span role="alert">{errors.coupon.message}</span>}
      </div>

      <div>
        <label>Total (preview)</label>
        <output>{total}</output>
        <small>Final total is confirmed by the server.</small>
      </div>

      {confirmedTotal !== null && <p>Order placed. Server total: {confirmedTotal}</p>}

      <button type="submit" disabled={isSubmitting}>
        Place order
      </button>
    </form>
  );
}
