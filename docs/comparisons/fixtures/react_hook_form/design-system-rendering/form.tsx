// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import type { ReactNode } from "react";
import {
  useForm,
  useController,
  FormProvider,
  useFormContext,
  type Control,
  type FieldValues,
  type FieldPath,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  profileSchema,
  profileDefaults,
  VISIBILITY,
  type ProfileInput,
  type ProfileValues,
} from "./schema";
import { checkEmail, submitProfile, applyServerErrors } from "./api";

// -----------------------------------------------------------------------------
// A tiny reusable field-component library. Each wrapper owns its own label /
// error / control markup so the design system is defined once and every field
// in every form renders consistently. This is the per-field wiring that the
// comparison highlights: with RHF the design system lives in these components,
// and every field must be threaded through them by hand.
// -----------------------------------------------------------------------------

interface FieldShellProps {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}

function FieldShell({ label, htmlFor, error, children }: FieldShellProps) {
  return (
    <div className="ds-field">
      <label className="ds-field__label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error && (
        <span className="ds-field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

interface TextFieldProps<T extends FieldValues> {
  name: FieldPath<T>;
  control: Control<T>;
  label: string;
  type?: string;
  // Optional composed blur hook (used for the async email check).
  onBlurExtra?: (value: string) => void;
}

export function TextField<T extends FieldValues>({
  name,
  control,
  label,
  type = "text",
  onBlurExtra,
}: TextFieldProps<T>) {
  const {
    field,
    fieldState: { error },
  } = useController({ name, control });
  const id = `ds-${String(name)}`;

  return (
    <FieldShell label={label} htmlFor={id} error={error?.message}>
      <input
        id={id}
        type={type}
        className="ds-field__input"
        {...field}
        onBlur={(e) => {
          field.onBlur();
          onBlurExtra?.(e.target.value);
        }}
      />
    </FieldShell>
  );
}

interface SelectFieldProps<T extends FieldValues> {
  name: FieldPath<T>;
  control: Control<T>;
  label: string;
  options: ReadonlyArray<{ value: string; label: string }>;
}

export function SelectField<T extends FieldValues>({
  name,
  control,
  label,
  options,
}: SelectFieldProps<T>) {
  const {
    field,
    fieldState: { error },
  } = useController({ name, control });
  const id = `ds-${String(name)}`;

  return (
    <FieldShell label={label} htmlFor={id} error={error?.message}>
      <select id={id} className="ds-field__select" {...field}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

// -----------------------------------------------------------------------------
// The profile form, assembled from the reusable field components above.
// -----------------------------------------------------------------------------

const KNOWN_FIELDS = ["displayName", "email", "visibility", "handle"] as const;

const VISIBILITY_OPTIONS = VISIBILITY.map((v) => ({
  value: v,
  label: v === "public" ? "Public" : "Private",
}));

export function ProfileForm() {
  const methods = useForm<ProfileInput, unknown, ProfileValues>({
    resolver: zodResolver(profileSchema),
    mode: "onBlur",
    defaultValues: profileDefaults,
  });

  const {
    control,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = methods;

  const isPublic = watch("visibility") === "public";

  const onEmailBlur = async (value: string) => {
    const result = await checkEmail(value);
    if (!result.available) {
      setError("email", {
        type: "availability",
        message: result.message ?? "That email is already registered.",
      });
    } else if (errors.email?.type === "availability") {
      clearErrors("email");
    }
  };

  const onSubmit = async (values: ProfileValues) => {
    const result = await submitProfile(values);
    if (!result.ok) applyServerErrors(result.errors, setError, KNOWN_FIELDS);
  };

  return (
    <FormProvider {...methods}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        {errors.root && <p role="alert">{errors.root.message}</p>}

        <TextField control={control} name="displayName" label="Display name" />
        <TextField control={control} name="email" label="Email" type="email" onBlurExtra={onEmailBlur} />
        <SelectField control={control} name="visibility" label="Profile visibility" options={VISIBILITY_OPTIONS} />

        {isPublic && <TextField control={control} name="handle" label="Public handle" />}

        <button type="submit" disabled={isSubmitting}>
          Save profile
        </button>
      </form>
    </FormProvider>
  );
}

// FormProvider is included so nested field components could also reach the form
// via useFormContext() instead of prop-drilling `control`. Shown here for
// completeness; the fields above take `control` explicitly for clarity.
export function useProfileForm() {
  return useFormContext<ProfileValues>();
}
