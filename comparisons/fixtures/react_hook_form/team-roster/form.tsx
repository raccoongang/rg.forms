// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
// NOTE: this competitor (RHF useFieldArray) supports dynamic add/remove of rows at runtime, unlike the rg.forms slice, which is a *static* Django formset (fixed rows).

import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  rosterSchema,
  rosterDefaults,
  emptyMember,
  ROLES,
  type RosterInput,
  type RosterValues,
} from "./schema";
import { submitRoster, applyServerErrors } from "./api";

export function TeamRosterForm() {
  const {
    register,
    control,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RosterInput, unknown, RosterValues>({
    resolver: zodResolver(rosterSchema),
    mode: "onBlur",
    defaultValues: rosterDefaults,
  });

  const { fields, append, remove } = useFieldArray({ control, name: "members" });

  const onSubmit = async (values: RosterValues) => {
    const result = await submitRoster(values);
    if (!result.ok) applyServerErrors(result.errors, setError);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {errors.root && <p role="alert">{errors.root.message}</p>}
      {errors.members?.root && <p role="alert">{errors.members.root.message}</p>}

      {fields.map((field, index) => {
        // Per-row reactive read: role drives email requiredness + the admin note.
        const role = watch(`members.${index}.role`);
        const rowErrors = errors.members?.[index];
        const showAdminNote = role === "admin";

        return (
          <fieldset key={field.id}>
            <legend>Member {index + 1}</legend>

            <div>
              <label>Full name</label>
              <input {...register(`members.${index}.fullName`)} />
              {rowErrors?.fullName && <span role="alert">{rowErrors.fullName.message}</span>}
            </div>

            <div>
              <label>Role</label>
              <select {...register(`members.${index}.role`)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {rowErrors?.role && <span role="alert">{rowErrors.role.message}</span>}
            </div>

            <div>
              <label>Email</label>
              <input type="email" {...register(`members.${index}.email`)} />
              {rowErrors?.email && <span role="alert">{rowErrors.email.message}</span>}
            </div>

            {showAdminNote && (
              <div>
                <label>Admin note</label>
                <input {...register(`members.${index}.adminNote`)} />
                {rowErrors?.adminNote && <span role="alert">{rowErrors.adminNote.message}</span>}
              </div>
            )}

            <button type="button" onClick={() => remove(index)} disabled={fields.length === 1}>
              Remove
            </button>
          </fieldset>
        );
      })}

      <button type="button" onClick={() => append({ ...emptyMember })}>
        Add member
      </button>

      <button type="submit" disabled={isSubmitting}>
        Save roster
      </button>
    </form>
  );
}
