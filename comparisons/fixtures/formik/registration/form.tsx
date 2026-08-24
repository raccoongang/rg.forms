// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import React from "react";
import { Formik, Form, Field, ErrorMessage, useFormikContext } from "formik";
import {
  initialValues,
  registrationSchema,
  type RegistrationValues,
} from "./schema";
import { checkUsername, checkEmail, submitRegistration } from "./api";

// Runs an async availability check on blur and merges the result into Formik's
// error state without clobbering the synchronous (Yup) errors.
function useAvailabilityCheck() {
  const { setFieldError, values } =
    useFormikContext<RegistrationValues>();

  const runUsername = async () => {
    const msg = await checkUsername(values.username);
    if (msg) setFieldError("username", msg);
  };
  const runEmail = async () => {
    const msg = await checkEmail(values.email);
    if (msg) setFieldError("email", msg);
  };
  return { runUsername, runEmail };
}

function Fields() {
  const { values, isSubmitting } = useFormikContext<RegistrationValues>();
  const { runUsername, runEmail } = useAvailabilityCheck();
  const isBusiness = values.accountType === "business";

  return (
    <>
      <div className="field">
        <label htmlFor="username">Username</label>
        <Field
          id="username"
          name="username"
          placeholder="pick a username"
          onBlur={runUsername}
        />
        <ErrorMessage name="username" component="div" className="error" />
      </div>

      <div className="field">
        <label htmlFor="email">Email</label>
        <Field
          id="email"
          name="email"
          type="email"
          placeholder="you@example.com"
          onBlur={runEmail}
        />
        <ErrorMessage name="email" component="div" className="error" />
      </div>

      <div className="field">
        <label htmlFor="password">Password</label>
        <Field id="password" name="password" type="password" />
        <ErrorMessage name="password" component="div" className="error" />
      </div>

      <div className="field">
        <label htmlFor="passwordConfirm">Confirm password</label>
        <Field id="passwordConfirm" name="passwordConfirm" type="password" />
        <ErrorMessage name="passwordConfirm" component="div" className="error" />
      </div>

      <div className="field">
        <label htmlFor="accountType">Account type</label>
        <Field as="select" id="accountType" name="accountType">
          <option value="personal">Personal</option>
          <option value="business">Business</option>
        </Field>
      </div>

      {/* Conditional field: rendered AND required only for business accounts. */}
      {isBusiness && (
        <div className="field">
          <label htmlFor="companyEmail">Company email</label>
          <Field
            id="companyEmail"
            name="companyEmail"
            type="email"
            placeholder="you@company.com"
          />
          <ErrorMessage name="companyEmail" component="div" className="error" />
        </div>
      )}

      <div className="field field--checkbox">
        <label>
          <Field type="checkbox" name="agreeTerms" />I agree to the Terms of
          Service
        </label>
        <ErrorMessage name="agreeTerms" component="div" className="error" />
      </div>

      <button type="submit" disabled={isSubmitting}>
        Create account
      </button>
    </>
  );
}

export function RegistrationForm() {
  const [formErrors, setFormErrors] = React.useState<string[]>([]);

  return (
    <Formik<RegistrationValues>
      initialValues={initialValues}
      validationSchema={registrationSchema}
      onSubmit={async (values, helpers) => {
        setFormErrors([]);
        const result = await submitRegistration(values);
        if (result.ok) {
          helpers.resetForm();
          return;
        }
        // Push server-side (re)validation errors back onto the matching fields.
        helpers.setErrors(result.fieldErrors);
        setFormErrors(result.formErrors);
      }}
    >
      <Form noValidate>
        {formErrors.length > 0 && (
          <div className="form-errors" role="alert">
            {formErrors.map((e, i) => (
              <p key={i}>{e}</p>
            ))}
          </div>
        )}
        <Fields />
      </Form>
    </Formik>
  );
}
