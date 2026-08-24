// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
//
// The point of this slice is per-field COMPONENT wiring: a small reusable
// field-component library (TextField, SelectField) built on top of form.Field's
// render-prop API, then a profile form assembled from those components in JSX.

import * as React from "react";
import { useForm, type FormApi, type ReactFormExtendedApi } from "@tanstack/react-form";

import { checkEmail, submitProfile } from "./api";
import {
  defaultProfileValues,
  displayNameSchema,
  emailSchema,
  handleSchema,
  profileFormSchema,
  type ProfileValues,
  type Visibility,
} from "./schema";

// A form instance typed to our values; used to type the wrapper props.
type ProfileForm = ReactFormExtendedApi<ProfileValues, any, any, any, any, any, any, any, any, any>;

function firstError(errors: unknown[]): string | null {
  const e = errors.find(Boolean);
  if (!e) return null;
  return typeof e === "string" ? e : ((e as { message?: string }).message ?? null);
}

// --- Reusable field components (the "design system") ------------------------

interface TextFieldProps {
  form: ProfileForm;
  name: keyof ProfileValues & string;
  label: string;
  type?: "text" | "email";
  validators?: Parameters<ProfileForm["Field"]>[0]["validators"];
  help?: string;
}

export function TextField({ form, name, label, type = "text", validators, help }: TextFieldProps) {
  return (
    <form.Field name={name} validators={validators}>
      {(field) => (
        <div className="ds-field">
          <label className="ds-label" htmlFor={field.name}>
            {label}
          </label>
          <input
            id={field.name}
            className="ds-input"
            type={type}
            value={String(field.state.value ?? "")}
            onChange={(e) => field.handleChange(e.target.value as never)}
            onBlur={field.handleBlur}
            aria-invalid={field.state.meta.errors.length > 0}
          />
          {field.state.meta.isValidating && <span className="ds-pending">checking…</span>}
          {help && <p className="ds-help">{help}</p>}
          <p className="ds-error">{firstError(field.state.meta.errors)}</p>
        </div>
      )}
    </form.Field>
  );
}

interface SelectFieldProps<V extends string> {
  form: ProfileForm;
  name: keyof ProfileValues & string;
  label: string;
  options: ReadonlyArray<{ value: V; label: string }>;
  validators?: Parameters<ProfileForm["Field"]>[0]["validators"];
}

export function SelectField<V extends string>({ form, name, label, options, validators }: SelectFieldProps<V>) {
  return (
    <form.Field name={name} validators={validators}>
      {(field) => (
        <div className="ds-field">
          <label className="ds-label" htmlFor={field.name}>
            {label}
          </label>
          <select
            id={field.name}
            className="ds-select"
            value={String(field.state.value ?? "")}
            onChange={(e) => field.handleChange(e.target.value as never)}
            onBlur={field.handleBlur}
          >
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <p className="ds-error">{firstError(field.state.meta.errors)}</p>
        </div>
      )}
    </form.Field>
  );
}

// --- The profile form assembled from those components -----------------------

export function ProfileForm() {
  const form = useForm({
    defaultValues: defaultProfileValues,
    validators: { onSubmit: profileFormSchema },
    onSubmit: async ({ value, formApi }) => {
      const serverErrors = await submitProfile(value);
      for (const [name, message] of Object.entries(serverErrors)) {
        formApi.setFieldMeta(name as keyof ProfileValues, (meta) => ({
          ...meta,
          errorMap: { ...meta.errorMap, onServer: message },
        }));
      }
    },
  }) as ProfileForm;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void form.handleSubmit();
      }}
    >
      <TextField form={form} name="displayName" label="Display name" validators={{ onBlur: displayNameSchema }} />

      <TextField
        form={form}
        name="email"
        label="Email"
        type="email"
        help="Availability is checked when you leave the field."
        validators={{
          onBlur: emailSchema,
          onBlurAsyncDebounceMs: 400,
          onBlurAsync: async ({ value }) => checkEmail(String(value)),
        }}
      />

      <SelectField<Visibility>
        form={form}
        name="visibility"
        label="Profile visibility"
        options={[
          { value: "public", label: "Public" },
          { value: "private", label: "Private" },
        ]}
      />

      {/* Public handle — shown + required only for public profiles. */}
      <form.Subscribe selector={(state) => state.values.visibility}>
        {(visibility) =>
          visibility === "public" ? (
            <TextField
              form={form}
              name="handle"
              label="Public handle"
              validators={{
                onBlur: ({ value }) => {
                  if (!value) return "A public handle is required.";
                  const res = handleSchema.safeParse(value);
                  return res.success ? undefined : res.error.issues[0]?.message;
                },
              }}
            />
          ) : null
        }
      </form.Subscribe>

      <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting] as const}>
        {([canSubmit, isSubmitting]) => (
          <button type="submit" disabled={!canSubmit}>
            {isSubmitting ? "Saving…" : "Save profile"}
          </button>
        )}
      </form.Subscribe>
    </form>
  );
}
