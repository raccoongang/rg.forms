// Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  registrationSchema,
  registrationDefaults,
  type RegistrationInput,
  type RegistrationValues,
} from "./schema";
import {
  checkUsername,
  checkEmail,
  submitRegistration,
  applyServerErrors,
} from "./api";

const KNOWN_FIELDS = [
  "username",
  "email",
  "password",
  "passwordConfirm",
  "accountType",
  "companyEmail",
  "agreeTerms",
] as const;

export function RegistrationForm() {
  const {
    register,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<RegistrationInput, unknown, RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    mode: "onBlur",
    defaultValues: registrationDefaults,
  });

  // Drives conditional rendering + requiredness of the company email. In RHF
  // this reactive read is explicit: watch() re-renders the component on change.
  const accountType = watch("accountType");
  const isBusiness = accountType === "business";

  // Async availability: run on blur, alongside the synchronous zod resolver.
  // We set/clear a manual error so it merges with the resolver's messages.
  const onUsernameBlur = async (e: React.FocusEvent<HTMLInputElement>) => {
    const result = await checkUsername(e.target.value);
    if (!result.available) {
      setError("username", {
        type: "availability",
        message: result.message ?? "That username is already taken.",
      });
    } else if (errors.username?.type === "availability") {
      clearErrors("username");
    }
  };

  const onEmailBlur = async (e: React.FocusEvent<HTMLInputElement>) => {
    const result = await checkEmail(e.target.value);
    if (!result.available) {
      setError("email", {
        type: "availability",
        message: result.message ?? "An account with this email already exists.",
      });
    } else if (errors.email?.type === "availability") {
      clearErrors("email");
    }
  };

  const onSubmit = async (values: RegistrationValues) => {
    const result = await submitRegistration(values);
    if (!result.ok) {
      applyServerErrors(result.errors, setError, KNOWN_FIELDS);
    }
  };

  // RHF's register() returns an onBlur; we compose it with our async checker so
  // the resolver's onBlur validation and the availability probe both fire.
  const usernameField = register("username");
  const emailField = register("email");

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {errors.root && <p role="alert">{errors.root.message}</p>}

      <div>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          {...usernameField}
          onBlur={(e) => {
            usernameField.onBlur(e);
            void onUsernameBlur(e);
          }}
        />
        {errors.username && <span role="alert">{errors.username.message}</span>}
      </div>

      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          {...emailField}
          onBlur={(e) => {
            emailField.onBlur(e);
            void onEmailBlur(e);
          }}
        />
        {errors.email && <span role="alert">{errors.email.message}</span>}
      </div>

      <div>
        <label htmlFor="password">Password</label>
        <input id="password" type="password" {...register("password")} />
        {errors.password && <span role="alert">{errors.password.message}</span>}
      </div>

      <div>
        <label htmlFor="passwordConfirm">Confirm password</label>
        <input id="passwordConfirm" type="password" {...register("passwordConfirm")} />
        {errors.passwordConfirm && <span role="alert">{errors.passwordConfirm.message}</span>}
      </div>

      <fieldset>
        <legend>Account type</legend>
        <label>
          <input type="radio" value="personal" {...register("accountType")} /> Personal
        </label>
        <label>
          <input type="radio" value="business" {...register("accountType")} /> Business
        </label>
      </fieldset>

      {isBusiness && (
        <div>
          <label htmlFor="companyEmail">Company email</label>
          <input id="companyEmail" type="email" {...register("companyEmail")} />
          {errors.companyEmail && <span role="alert">{errors.companyEmail.message}</span>}
        </div>
      )}

      <div>
        <label>
          <input type="checkbox" {...register("agreeTerms")} /> I agree to the Terms of Service
        </label>
        {errors.agreeTerms && <span role="alert">{errors.agreeTerms.message}</span>}
      </div>

      <button type="submit" disabled={isSubmitting}>
        Create account
      </button>
    </form>
  );
}
