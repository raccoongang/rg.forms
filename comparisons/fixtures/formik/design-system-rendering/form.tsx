// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import React from "react";
import { Formik, Form, useField, useFormikContext } from "formik";
import { initialValues, profileSchema, type ProfileValues } from "./schema";
import { checkEmail, submitProfile } from "./api";

// --- Reusable field-component library --------------------------------------
// Each wrapper owns the label + control + error markup for one design system.
// Swapping the design system means editing only these components; every consumer
// (the profile form below) stays untouched.

interface FieldProps {
  name: string;
  label: string;
  type?: string;
  placeholder?: string;
  onBlurExtra?: () => void;
}

export function TextField({ name, label, type = "text", placeholder, onBlurExtra }: FieldProps) {
  const [field, meta] = useField(name);
  const showError = meta.touched && !!meta.error;
  return (
    <div className={`ds-field ${showError ? "ds-field--invalid" : ""}`}>
      <label className="ds-label" htmlFor={name}>
        {label}
      </label>
      <input
        id={name}
        type={type}
        placeholder={placeholder}
        className="ds-input"
        {...field}
        onBlur={(e) => {
          field.onBlur(e); // keep Formik's touched bookkeeping
          onBlurExtra?.();
        }}
      />
      {showError && <div className="ds-error">{meta.error}</div>}
    </div>
  );
}

interface SelectFieldProps {
  name: string;
  label: string;
  options: Array<{ value: string; label: string }>;
}

export function SelectField({ name, label, options }: SelectFieldProps) {
  const [field, meta] = useField(name);
  const showError = meta.touched && !!meta.error;
  return (
    <div className={`ds-field ${showError ? "ds-field--invalid" : ""}`}>
      <label className="ds-label" htmlFor={name}>
        {label}
      </label>
      <select id={name} className="ds-select" {...field}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {showError && <div className="ds-error">{meta.error}</div>}
    </div>
  );
}

// --- The profile form, assembled from the component library ----------------

function ProfileFields() {
  const { values, setFieldError } = useFormikContext<ProfileValues>();
  const isPublic = values.visibility === "public";

  const onEmailBlur = async () => {
    const msg = await checkEmail(values.email);
    if (msg) setFieldError("email", msg);
  };

  return (
    <>
      <TextField name="displayName" label="Display name" placeholder="Ada Lovelace" />
      <TextField name="email" label="Email" type="email" placeholder="ada@example.com" onBlurExtra={onEmailBlur} />
      <SelectField
        name="visibility"
        label="Profile visibility"
        options={[
          { value: "private", label: "Private" },
          { value: "public", label: "Public" },
        ]}
      />
      {/* Shown AND required only for public profiles. */}
      {isPublic && <TextField name="handle" label="Public handle" placeholder="ada_l" />}
    </>
  );
}

export function ProfileForm() {
  const [formErrors, setFormErrors] = React.useState<string[]>([]);

  return (
    <Formik<ProfileValues>
      initialValues={initialValues}
      validationSchema={profileSchema}
      onSubmit={async (values, helpers) => {
        setFormErrors([]);
        const result = await submitProfile(values);
        if (result.ok) {
          helpers.resetForm({ values });
          return;
        }
        helpers.setErrors(result.fieldErrors);
        setFormErrors(result.formErrors);
      }}
    >
      {({ isSubmitting }) => (
        <Form noValidate>
          {formErrors.length > 0 && (
            <div className="form-errors" role="alert">
              {formErrors.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
            </div>
          )}
          <ProfileFields />
          <button type="submit" disabled={isSubmitting}>
            Save profile
          </button>
        </Form>
      )}
    </Formik>
  );
}
