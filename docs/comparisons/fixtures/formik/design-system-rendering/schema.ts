// Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import * as Yup from "yup";

export type Visibility = "public" | "private";

export interface ProfileValues {
  displayName: string;
  email: string;
  visibility: Visibility;
  handle: string;
}

export const initialValues: ProfileValues = {
  displayName: "",
  email: "",
  visibility: "private",
  handle: "",
};

export const profileSchema: Yup.SchemaOf<ProfileValues> = Yup.object({
  displayName: Yup.string().trim().required("Display name is required."),
  email: Yup.string().trim().email("Enter a valid email.").required("Email is required."),
  visibility: Yup.mixed<Visibility>()
    .oneOf(["public", "private"])
    .required(),
  // Conditional: public profiles must claim a handle.
  handle: Yup.string().when("visibility", {
    is: "public",
    then: (s) =>
      s
        .trim()
        .matches(/^[a-z0-9_]+$/i, "Handle may only contain letters, digits, and underscores.")
        .required("Public profiles need a handle."),
    otherwise: (s) => s.notRequired(),
  }),
});
