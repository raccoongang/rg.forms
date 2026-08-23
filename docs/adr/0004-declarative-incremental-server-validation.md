# ADR 0004 — Declarative incremental server validation

- Status: Proposed
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Relates to: [ADR-0002](0002-canonical-expression-semantics.md) (consistent values make incremental and final
  validation agree). Reuses the existing SSE machinery (`reactive_form_response`).

## Context

Some rules can only be checked on the server: "is this username taken?", "is this coupon valid?", VAT/format lookups,
cross-field rules that need database state. Today rg.forms enforces these on **submit**: the SSE-validation example
(`examples/…/sse_validation.html` + `reactive_form_response`) binds the whole form, validates, and patches error
fragments back without a page reload. Validating a *single field earlier* — as the user leaves it — is possible but
must be **hand-wired** per field: `data-on:blur` / `data-on:input__debounce.400ms="@post(url, {contentType: 'form'})"`
plus a view that knows which field to validate and how to patch only that fragment.

This is the capability Formik/RHF expose as "async validators / validate-on-blur." It is worth having — but it is not
a client-side concern. It is **ordinary Django validation invoked earlier and returned through SSE**, which fits
rg.forms precisely. The goal of this ADR is to make it *declarative* so authors do not re-implement the wiring, the
stale-response handling, and the pending state every time.

## Problems

### P1 — The wiring is manual and error-prone

Every incremental-validated field needs its own `data-on:*` handler, debounce, content-type, and a matching
view branch. Nothing ties the field declaration to its trigger.

### P2 — No standard "which field triggered this?" contract

A validate request must tell the server which field to check so it can validate just that field (and the cross-field
rules that depend on already-available values) rather than the whole form, and patch only the relevant fragment.

### P3 — Missing lifecycle affordances

A robust implementation needs: **stale-response protection** (a late reply for an old keystroke must not overwrite a
newer state), a **pending indicator** while the check is in flight, a decision on whether `clean()` or only
field-level validation runs, **preservation of unrelated fields' errors** (an incremental check must not clear errors
elsewhere), and **throttling** of expensive database checks.

## Decision

Add a declarative, opt-in trigger on reactive fields and a server helper that runs Django validation incrementally
and patches back a single field (or form) fragment.

### 1. Declarative trigger

Reactive fields accept:

```python
username = ReactiveCharField(validate_on="blur")
coupon = ReactiveCharField(validate_on="change", debounce=400)
```

- `validate_on`: `"blur"` | `"change"` (default: unset → submit-only, today's behavior).
- `debounce`: milliseconds for `"change"` (ignored for `"blur"`).

The renderer emits the appropriate `data-on:*` handler that `@post`s the normal form (`contentType: 'form'`) with an
indication of the triggering field. Authors do not hand-write the handler.

### 2. Server helper

A helper (an extension of `reactive_form_response`, or a sibling `reactive_validate_response`) that, given the request
and form:

- reads the triggering field from the request contract (P2);
- runs that field's cleaning plus the cross-field rules that depend only on already-submitted values;
- returns an SSE patch of **only** that field's fragment (value/error/`aria-*` state), leaving other fields' current
  error state intact (P3);
- falls back to full-form validation on actual submit, exactly as today.

Because the form already knows how to validate itself, the request carries the normal form data plus the triggering
field's identity — no per-field validator URLs or validator-name registries on the field. The form is the authority.

### 3. Lifecycle affordances

- **Stale-response protection**: each validate request carries a monotonically increasing token per field; a response
  is applied only if it is the newest for that field. (Confirm whether Datastar's request handling already supersedes
  in-flight requests; if so, lean on it and document the guarantee.)
- **Pending state**: a per-field signal (e.g. `_validating_<field>`) set while the request is in flight, drivable via
  Datastar's indicator mechanism, so the design system can show a spinner and disable submit if desired.
- **`clean()` vs field-only**: default to field-level cleaning plus cross-field rules whose inputs are already
  present; document how to opt a rule into incremental evaluation.
- **Throttling**: `debounce` on the client; the server side stays a normal view, so expensive checks can be cached or
  rate-limited by the host as usual.

## Backward compatibility

- **Opt-in and additive.** Fields without `validate_on` behave exactly as today (submit-only validation). No change to
  existing forms, templates, or views.
- Using the feature requires wiring an action URL, the same as the current SSE-validation example already does.

## Consequences

- Incremental validation becomes a one-line field declaration instead of bespoke wiring, while remaining ordinary
  server-authoritative Django validation.
- The `_validating_<field>` signal and the triggering-field contract are new, documented surface.
- Reinforces the backend-first thesis: the browser triggers, the server decides.

## Scope boundaries

- Canonical value semantics — [ADR-0002](0002-canonical-expression-semantics.md).
- Row-scoped signals / reactive formsets — [ADR-0003](0003-scoped-signals-and-reactive-formsets.md).
- No client-side validation engine, and no async validators expressed in JavaScript — validation stays in Python.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/fields.py` (`validate_on` / `debounce` kwargs on `ReactiveFieldMixin`),
  `src/rg/forms/templatetags/reactive_forms.py` (emit the `data-on:*` handler + pending signal),
  `src/rg/forms/views.py` (`reactive_validate_response` / extend `reactive_form_response` with the triggering-field
  contract), a single-field fragment template, and docs + an example.
- Tests: a `validate_on="blur"` field posts and patches only its own fragment on error; unrelated fields' errors are
  preserved; a stale response does not overwrite a newer one; a valid value clears the field's error and pending
  state; forms without `validate_on` are unchanged.
- Verify Datastar's in-flight request semantics before choosing between a client token and relying on request
  supersession for stale-response protection.
