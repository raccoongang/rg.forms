// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import * as React from "react";
import { useForm } from "@tanstack/react-form";

import { submitOrder, validateCoupon } from "./api";
import {
  defaultOrderValues,
  formatCents,
  orderFormSchema,
  planByCode,
  PLANS,
  previewTotalCents,
  unitPriceFor,
  type PlanCode,
} from "./schema";

function firstError(errors: unknown[]): string | null {
  const e = errors.find(Boolean);
  if (!e) return null;
  return typeof e === "string" ? e : ((e as { message?: string }).message ?? null);
}

export function OrderConfiguratorForm() {
  const [serverTotal, setServerTotal] = React.useState<string | null>(null);

  const form = useForm({
    defaultValues: defaultOrderValues,
    validators: { onSubmit: orderFormSchema },
    onSubmit: async ({ value, formApi }) => {
      const result = await submitOrder(value);
      if (!result.ok) {
        for (const [name, message] of Object.entries(result.errors)) {
          formApi.setFieldMeta(name as keyof typeof value, (meta) => ({
            ...meta,
            errorMap: { ...meta.errorMap, onServer: message },
          }));
        }
        return;
      }
      // The authoritative Decimal total comes back from the server.
      setServerTotal(result.discountedTotal ?? result.total ?? null);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void form.handleSubmit();
      }}
    >
      <form.Field
        name="plan"
        listeners={{
          // When the plan changes, reset seats for the single-seat Starter plan.
          onChange: ({ value, fieldApi }) => {
            if (value === "001") fieldApi.form.setFieldValue("seats", 1);
          },
        }}
      >
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Plan</label>
            <select
              id={field.name}
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value as PlanCode)}
              onBlur={field.handleBlur}
            >
              <option value="">-- Select a plan --</option>
              {PLANS.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
            <p className="field-error">{firstError(field.state.meta.errors)}</p>
          </div>
        )}
      </form.Field>

      {/* Enterprise contact — shown + required only for plan "100". */}
      <form.Subscribe selector={(state) => state.values.plan}>
        {(plan) =>
          plan === "100" ? (
            <form.Field
              name="enterpriseContact"
              validators={{
                onBlur: ({ value }) =>
                  value.trim() ? undefined : "Enterprise orders need an account-manager contact.",
              }}
            >
              {(field) => (
                <div className="field">
                  <label htmlFor={field.name}>Enterprise contact</label>
                  <input
                    id={field.name}
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                  />
                  <p className="field-error">{firstError(field.state.meta.errors)}</p>
                </div>
              )}
            </form.Field>
          ) : null
        }
      </form.Subscribe>

      {/* Seats — disabled for Starter, with plan-specific help text. */}
      <form.Subscribe selector={(state) => state.values.plan}>
        {(plan) => (
          <form.Field name="seats" validators={{ onChange: ({ value }) => (value >= 1 ? undefined : "At least one seat is required.") }}>
            {(field) => (
              <div className="field">
                <label htmlFor={field.name}>Seats</label>
                <input
                  id={field.name}
                  type="number"
                  min={1}
                  disabled={plan === "001"}
                  value={field.state.value}
                  onChange={(e) => field.handleChange(Number(e.target.value))}
                  onBlur={field.handleBlur}
                />
                <p className="help">{planByCode(plan)?.help ?? "Choose a plan to see seat rules."}</p>
                <p className="field-error">{firstError(field.state.meta.errors)}</p>
              </div>
            )}
          </form.Field>
        )}
      </form.Subscribe>

      {/* Unit price — derived read-only display driven by the selected plan. */}
      <form.Subscribe selector={(state) => state.values.plan}>
        {(plan) => (
          <div className="field">
            <label>Unit price</label>
            <output>{unitPriceFor(plan).toFixed(2)}</output>
          </div>
        )}
      </form.Subscribe>

      <form.Field
        name="coupon"
        validators={{
          onBlurAsyncDebounceMs: 300,
          onBlurAsync: async ({ value }) => validateCoupon(value),
        }}
      >
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Coupon</label>
            <input
              id={field.name}
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            <p className="field-error">{firstError(field.state.meta.errors)}</p>
          </div>
        )}
      </form.Field>

      {/* Live computed total preview (client-side, from plan + seats). */}
      <form.Subscribe selector={(state) => [state.values.plan, state.values.seats] as const}>
        {([plan, seats]) => (
          <div className="field">
            <label>Total (preview)</label>
            <output>{formatCents(previewTotalCents(plan, seats))}</output>
          </div>
        )}
      </form.Subscribe>

      {serverTotal !== null && (
        <p className="server-total">Confirmed total: {serverTotal}</p>
      )}

      <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting] as const}>
        {([canSubmit, isSubmitting]) => (
          <button type="submit" disabled={!canSubmit}>
            {isSubmitting ? "Placing order…" : "Place order"}
          </button>
        )}
      </form.Subscribe>
    </form>
  );
}
