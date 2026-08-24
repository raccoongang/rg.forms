// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
// NOTE: rows can be added/removed dynamically here (FieldArray), which is beyond
// the static-formset scope of the rg.forms slice this is compared against.

import React from "react";
import {
  Formik,
  Form,
  Field,
  ErrorMessage,
  FieldArray,
  useFormikContext,
} from "formik";
import {
  initialValues,
  rosterSchema,
  emptyMember,
  type RosterValues,
  type Role,
} from "./schema";
import { submitRoster } from "./api";

const requiresEmail = (role: Role | ""): boolean =>
  role === "owner" || role === "admin";

function MemberRow({ index, onRemove }: { index: number; onRemove: () => void }) {
  const { values } = useFormikContext<RosterValues>();
  const role = values.members[index]?.role ?? "";

  return (
    <fieldset className="member-row">
      <div className="field">
        <label htmlFor={`members.${index}.fullName`}>Full name</label>
        <Field id={`members.${index}.fullName`} name={`members.${index}.fullName`} />
        <ErrorMessage name={`members.${index}.fullName`} component="div" className="error" />
      </div>

      <div className="field">
        <label htmlFor={`members.${index}.role`}>Role</label>
        <Field as="select" id={`members.${index}.role`} name={`members.${index}.role`}>
          <option value="">-- Select --</option>
          <option value="owner">Owner</option>
          <option value="admin">Admin</option>
          <option value="editor">Editor</option>
          <option value="viewer">Viewer</option>
        </Field>
        <ErrorMessage name={`members.${index}.role`} component="div" className="error" />
      </div>

      {/* email required (and marked) only for owners/admins */}
      <div className="field">
        <label htmlFor={`members.${index}.email`}>
          Email{requiresEmail(role) ? " *" : ""}
        </label>
        <Field id={`members.${index}.email`} name={`members.${index}.email`} type="email" />
        <ErrorMessage name={`members.${index}.email`} component="div" className="error" />
      </div>

      {/* adminNote rendered only when the row's role is admin */}
      {role === "admin" && (
        <div className="field">
          <label htmlFor={`members.${index}.adminNote`}>Admin note</label>
          <Field id={`members.${index}.adminNote`} name={`members.${index}.adminNote`} />
        </div>
      )}

      <button type="button" className="remove-row" onClick={onRemove}>
        Remove
      </button>
    </fieldset>
  );
}

export function TeamRosterForm() {
  const [formErrors, setFormErrors] = React.useState<string[]>([]);

  return (
    <Formik<RosterValues>
      initialValues={initialValues}
      validationSchema={rosterSchema}
      onSubmit={async (values, helpers) => {
        setFormErrors([]);
        const result = await submitRoster(values);
        if (result.ok) {
          helpers.resetForm();
          return;
        }
        helpers.setErrors(result.fieldErrors);
        setFormErrors(result.formErrors);
      }}
    >
      {({ values, isSubmitting }) => (
        <Form noValidate>
          {formErrors.length > 0 && (
            <div className="form-errors" role="alert">
              {formErrors.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
            </div>
          )}
          <FieldArray name="members">
            {(arrayHelpers) => (
              <>
                {values.members.map((_, index) => (
                  <MemberRow
                    key={index}
                    index={index}
                    onRemove={() => arrayHelpers.remove(index)}
                  />
                ))}
                <button
                  type="button"
                  className="add-row"
                  onClick={() => arrayHelpers.push({ ...emptyMember })}
                >
                  Add member
                </button>
              </>
            )}
          </FieldArray>

          <button type="submit" disabled={isSubmitting}>
            Save roster
          </button>
        </Form>
      )}
    </Formik>
  );
}
