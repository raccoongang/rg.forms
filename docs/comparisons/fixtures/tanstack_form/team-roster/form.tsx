// Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
//
// NOTE: unlike the rg.forms static-formset slice, this uses a genuine DYNAMIC
// array field — rows are added/removed at runtime via pushValue/removeValue.

import * as React from "react";
import { useForm } from "@tanstack/react-form";

import { submitRoster } from "./api";
import {
  defaultRosterValues,
  emailRequiredFor,
  emptyMember,
  rosterFormSchema,
  type MemberRole,
} from "./schema";

function firstError(errors: unknown[]): string | null {
  const e = errors.find(Boolean);
  if (!e) return null;
  return typeof e === "string" ? e : ((e as { message?: string }).message ?? null);
}

export function TeamRosterForm() {
  const form = useForm({
    defaultValues: defaultRosterValues,
    validators: { onSubmit: rosterFormSchema },
    onSubmit: async ({ value, formApi }) => {
      const result = await submitRoster(value);
      if (!result.ok) {
        for (const [path, message] of Object.entries(result.errors)) {
          formApi.setFieldMeta(path as never, (meta) => ({
            ...meta,
            errorMap: { ...meta.errorMap, onServer: message },
          }));
        }
      }
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void form.handleSubmit();
      }}
    >
      <form.Field name="members" mode="array">
        {(membersField) => (
          <div className="roster">
            {membersField.state.value.map((_, i) => (
              <fieldset key={i} className="member-row">
                <legend>Member {i + 1}</legend>

                <form.Field
                  name={`members[${i}].fullName`}
                  validators={{
                    onBlur: ({ value }) => (value.trim() ? undefined : "Full name is required."),
                  }}
                >
                  {(field) => (
                    <div className="field">
                      <label>Full name</label>
                      <input
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                      />
                      <p className="field-error">{firstError(field.state.meta.errors)}</p>
                    </div>
                  )}
                </form.Field>

                <form.Field name={`members[${i}].role`}>
                  {(field) => (
                    <div className="field">
                      <label>Role</label>
                      <select
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value as MemberRole)}
                        onBlur={field.handleBlur}
                      >
                        <option value="">-- Select --</option>
                        <option value="owner">Owner</option>
                        <option value="admin">Admin</option>
                        <option value="editor">Editor</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    </div>
                  )}
                </form.Field>

                {/* Email — required only when this row's role is owner/admin.
                    Re-validates whenever this row's role changes. */}
                <form.Field
                  name={`members[${i}].email`}
                  validators={{
                    onChangeListenTo: [`members[${i}].role`],
                    onBlur: ({ value, fieldApi }) => {
                      const role = fieldApi.form.getFieldValue(`members[${i}].role`) as MemberRole;
                      if (emailRequiredFor(role) && !value.trim()) {
                        return "Email is required for owners and admins.";
                      }
                      return undefined;
                    },
                  }}
                >
                  {(field) => (
                    <div className="field">
                      <label>Email</label>
                      <input
                        type="email"
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        onBlur={field.handleBlur}
                      />
                      <p className="field-error">{firstError(field.state.meta.errors)}</p>
                    </div>
                  )}
                </form.Field>

                {/* Admin note — shown only when this row's role is admin. */}
                <form.Subscribe selector={(state) => state.values.members[i]?.role}>
                  {(role) =>
                    role === "admin" ? (
                      <form.Field name={`members[${i}].adminNote`}>
                        {(field) => (
                          <div className="field">
                            <label>Admin note</label>
                            <input
                              value={field.state.value}
                              onChange={(e) => field.handleChange(e.target.value)}
                              onBlur={field.handleBlur}
                            />
                          </div>
                        )}
                      </form.Field>
                    ) : null
                  }
                </form.Subscribe>

                <button
                  type="button"
                  onClick={() => membersField.removeValue(i)}
                  disabled={membersField.state.value.length <= 1}
                >
                  Remove member
                </button>
              </fieldset>
            ))}

            <button type="button" onClick={() => membersField.pushValue({ ...emptyMember })}>
              Add member
            </button>
          </div>
        )}
      </form.Field>

      <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting] as const}>
        {([canSubmit, isSubmitting]) => (
          <button type="submit" disabled={!canSubmit}>
            {isSubmitting ? "Saving roster…" : "Save roster"}
          </button>
        )}
      </form.Subscribe>
    </form>
  );
}
