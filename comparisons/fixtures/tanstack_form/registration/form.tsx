// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import * as React from "react";
import { useForm } from "@tanstack/react-form";

import { checkEmail, checkUsername, submitRegistration } from "./api";
import {
  defaultRegistrationValues,
  emailSchema,
  isFreeEmailDomain,
  passwordSchema,
  registrationFormSchema,
  usernameSchema,
} from "./schema";

// Small helper to render a field's first error under the input.
function FieldError({ errors }: { errors: unknown[] }) {
  const first = errors.find(Boolean);
  if (!first) return null;
  const msg = typeof first === "string" ? first : (first as { message?: string }).message;
  return <p className="field-error">{msg}</p>;
}

export function RegistrationForm() {
  const form = useForm({
    defaultValues: defaultRegistrationValues,
    // Form-level schema re-checks the cross-field + conditional rules on submit.
    validators: { onSubmit: registrationFormSchema },
    onSubmit: async ({ value, formApi }) => {
      const serverErrors = await submitRegistration(value);
      if (Object.keys(serverErrors).length > 0) {
        // Map Django's field errors back onto the matching fields.
        for (const [name, message] of Object.entries(serverErrors)) {
          formApi.setFieldMeta(name as keyof typeof value, (meta) => ({
            ...meta,
            errorMap: { ...meta.errorMap, onServer: message },
          }));
        }
        return;
      }
      formApi.reset();
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        void form.handleSubmit();
      }}
    >
      <form.Field
        name="username"
        validators={{
          onChange: usernameSchema,
          // Debounced async availability check as the value changes.
          onChangeAsyncDebounceMs: 400,
          onChangeAsync: async ({ value }) => checkUsername(value),
        }}
      >
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Username</label>
            <input
              id={field.name}
              name={field.name}
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            {field.state.meta.isValidating && <span className="pending">checking…</span>}
            <FieldError errors={field.state.meta.errors} />
          </div>
        )}
      </form.Field>

      <form.Field
        name="email"
        validators={{
          onBlur: emailSchema,
          // Availability confirmed when the user leaves the field.
          onBlurAsyncDebounceMs: 400,
          onBlurAsync: async ({ value }) => checkEmail(value),
        }}
      >
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Email</label>
            <input
              id={field.name}
              type="email"
              name={field.name}
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            {field.state.meta.isValidating && <span className="pending">checking…</span>}
            <FieldError errors={field.state.meta.errors} />
          </div>
        )}
      </form.Field>

      <form.Field name="password" validators={{ onChange: passwordSchema }}>
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Password</label>
            <input
              id={field.name}
              type="password"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            <FieldError errors={field.state.meta.errors} />
          </div>
        )}
      </form.Field>

      <form.Field
        name="passwordConfirm"
        validators={{
          // Compare against the sibling password value (read from the form store).
          onChangeListenTo: ["password"],
          onChange: ({ value, fieldApi }) =>
            value !== fieldApi.form.getFieldValue("password")
              ? "Passwords do not match."
              : undefined,
        }}
      >
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Confirm password</label>
            <input
              id={field.name}
              type="password"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            <FieldError errors={field.state.meta.errors} />
          </div>
        )}
      </form.Field>

      <form.Field name="accountType">
        {(field) => (
          <div className="field">
            <label htmlFor={field.name}>Account type</label>
            <select
              id={field.name}
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value as "personal" | "business")}
              onBlur={field.handleBlur}
            >
              <option value="personal">Personal</option>
              <option value="business">Business</option>
            </select>
          </div>
        )}
      </form.Field>

      {/* Conditional field: subscribe to accountType, mount companyEmail only for
          business accounts. Requiredness is enforced by the form-level schema. */}
      <form.Subscribe selector={(state) => state.values.accountType}>
        {(accountType) =>
          accountType === "business" ? (
            <form.Field
              name="companyEmail"
              validators={{
                onBlur: ({ value }) => {
                  if (!value) return "A company email is required for business accounts.";
                  if (isFreeEmailDomain(value)) return "Use a company email, not a free provider.";
                  return undefined;
                },
              }}
            >
              {(field) => (
                <div className="field">
                  <label htmlFor={field.name}>Company email</label>
                  <input
                    id={field.name}
                    type="email"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                  />
                  <FieldError errors={field.state.meta.errors} />
                </div>
              )}
            </form.Field>
          ) : null
        }
      </form.Subscribe>

      <form.Field name="agreeTerms">
        {(field) => (
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={field.state.value}
                onChange={(e) => field.handleChange(e.target.checked)}
                onBlur={field.handleBlur}
              />
              I agree to the Terms of Service
            </label>
            <FieldError errors={field.state.meta.errors} />
          </div>
        )}
      </form.Field>

      <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
        {([canSubmit, isSubmitting]) => (
          <button type="submit" disabled={!canSubmit}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>
        )}
      </form.Subscribe>
    </form>
  );
}
