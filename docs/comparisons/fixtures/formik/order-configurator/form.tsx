// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import React from "react";
import { Formik, Form, Field, ErrorMessage, useFormikContext } from "formik";
import {
  initialValues,
  orderSchema,
  helpTextFor,
  unitPriceFor,
  previewTotal,
  type OrderValues,
} from "./schema";
import { validateCoupon, submitOrder, type CouponResult } from "./api";

function Fields() {
  const { values, setFieldError } = useFormikContext<OrderValues>();
  const [coupon, setCoupon] = React.useState<CouponResult | null>(null);

  const isEnterprise = values.plan === "100";
  const seatsDisabled = values.plan === "001"; // Starter is single-seat
  const unitPrice = unitPriceFor(values.plan);
  const total = previewTotal(values.plan, values.seats);

  const onCouponBlur = async () => {
    const result = await validateCoupon(values.coupon);
    setCoupon(result);
    if (!result.valid && result.message) setFieldError("coupon", result.message);
  };

  return (
    <>
      <div className="field">
        <label htmlFor="plan">Plan</label>
        <Field as="select" id="plan" name="plan">
          <option value="">-- Select a plan --</option>
          <option value="001">Starter</option>
          <option value="010">Team</option>
          <option value="100">Enterprise</option>
        </Field>
        <ErrorMessage name="plan" component="div" className="error" />
      </div>

      {/* Conditional field: shown AND required for the Enterprise plan only. */}
      {isEnterprise && (
        <div className="field">
          <label htmlFor="enterpriseContact">Enterprise contact</label>
          <Field id="enterpriseContact" name="enterpriseContact" />
          <ErrorMessage name="enterpriseContact" component="div" className="error" />
        </div>
      )}

      <div className="field">
        <label htmlFor="seats">Seats</label>
        <Field id="seats" name="seats" type="number" min={1} disabled={seatsDisabled} />
        {/* Dynamic help text driven by the selected plan. */}
        <p className="help">{helpTextFor(values.plan)}</p>
        <ErrorMessage name="seats" component="div" className="error" />
      </div>

      <div className="field">
        <label>Unit price</label>
        {/* Derived, display-only. */}
        <output>{unitPrice}</output>
      </div>

      <div className="field">
        <label htmlFor="coupon">Coupon</label>
        <Field id="coupon" name="coupon" placeholder="WELCOME10" onBlur={onCouponBlur} />
        {coupon?.valid && coupon.discountPercent > 0 && (
          <p className="help">Coupon applies {coupon.discountPercent}% off.</p>
        )}
        <ErrorMessage name="coupon" component="div" className="error" />
      </div>

      <div className="field">
        <label>Total (preview)</label>
        {/* Live preview only — the server recomputes the authoritative total. */}
        <output data-testid="total-preview">{total}</output>
      </div>
    </>
  );
}

export function OrderConfiguratorForm() {
  const [confirmation, setConfirmation] = React.useState<string | null>(null);
  const [formErrors, setFormErrors] = React.useState<string[]>([]);

  return (
    <Formik<OrderValues>
      initialValues={initialValues}
      validationSchema={orderSchema}
      onSubmit={async (values, helpers) => {
        setFormErrors([]);
        setConfirmation(null);
        const result = await submitOrder(values);
        if (result.ok) {
          // Trust the server's Decimal total, not the client preview.
          setConfirmation(
            `Order placed. Authoritative total: ${result.total} (after coupon: ${result.discountedTotal}).`,
          );
          return;
        }
        helpers.setErrors(result.fieldErrors);
        setFormErrors(result.formErrors);
      }}
    >
      <Form noValidate>
        {confirmation && <div className="confirmation">{confirmation}</div>}
        {formErrors.length > 0 && (
          <div className="form-errors" role="alert">
            {formErrors.map((e, i) => (
              <p key={i}>{e}</p>
            ))}
          </div>
        )}
        <Fields />
        <SubmitButton />
      </Form>
    </Formik>
  );
}

function SubmitButton() {
  const { isSubmitting } = useFormikContext<OrderValues>();
  return (
    <button type="submit" disabled={isSubmitting}>
      Place order
    </button>
  );
}
