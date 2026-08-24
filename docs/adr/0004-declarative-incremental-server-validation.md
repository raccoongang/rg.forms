# ADR 0004 — Declarative incremental server validation

- Status: Proposed — Revision 2 (redesigned around Datastar request behavior and Django validation boundaries)
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Relates to: [ADR-0002](0002-canonical-expression-semantics.md) (canonical JSON signals are the request payload) and
  [ADR-0003](0003-scoped-signals-and-reactive-formsets.md) (scoped signal paths for the pending indicator and trigger
  identity). Reuses the existing SSE machinery (`reactive_form_response`).

## Revision 2 — decisions resolved

The first draft assumed a `contentType: 'form'` request, which is wrong for this feature. Resolved:

- **Transport: the default Datastar JSON-signal request**, not `contentType: 'form'` (which sends *no signals* and
  runs native form validity gating that would block validation of a partially-filled form). Final submit keeps the
  form POST (Decision §1).
- **Validation boundary: run the whole form, patch one fragment** (Option A). No attempt to infer per-field
  dependencies (Decision §2).
- **Stale responses: rely on Datastar's built-in per-element request cancellation** first; tokens only if integration
  tests prove it insufficient (Decision §3).
- **Pending state: the native `data-indicator`** on a local `_validating_<field>` signal (Decision §3).
- **Validation URL is explicit** — `validate_action`, defaulting to `action` (Decision §4).
- **Trigger identity is untrusted input** and must be verified server-side (Decision §5).
- **Minimal error accessibility** (`aria-invalid`, `aria-describedby`, stable ids) is part of the fragment contract
  from day one (Decision §6).

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

### P2 — The obvious transport (`contentType: 'form'`) does not fit

Datastar's `contentType: 'form'` locates the closest form, runs **native form validation**, sends the form fields,
and sends **no signals**. Two consequences make it wrong for incremental validation:

- **Native validity gating blocks it.** Blurring `username` while another `required` field is still empty can make
  the browser refuse the request entirely — defeating validate-on-blur on a partially-filled form.
- **Signals and trigger identity are not sent.** Local signals (`_validating_username`) and any trigger marker are
  excluded, so the server cannot receive the canonical typed values (ADR-0002) or learn which field fired.

### P3 — Missing lifecycle affordances

A robust implementation needs: **stale-response protection** (a late reply for an old keystroke must not overwrite a
newer state), a **pending indicator** while the check is in flight, a decision on which validation runs, **no
clobbering of unrelated fields' errors**, and **throttling** of expensive database checks. Each has a native Datastar
primitive or a simple rule — the first draft left them unspecified.

## Decision

Add a declarative, opt-in trigger on reactive fields and a server helper that runs Django validation incrementally
and patches back a single field (or form) fragment.

### §1 — Transport: JSON signals for incremental, form POST for submit

Reactive fields accept a declarative trigger:

```python
username = ReactiveCharField(validate_on="blur")
coupon   = ReactiveCharField(validate_on="change", debounce=400)
```

- `validate_on`: `"blur"` | `"change"` (default unset → submit-only, today's behavior).
- `debounce`: milliseconds for `"change"` (ignored for `"blur"`).

The renderer emits the `data-on:*` handler that fires a **default Datastar request (JSON signals)** — **not**
`contentType: 'form'`. This sends the canonical typed signals (ADR-0002), is not gated by native whole-form validity,
carries nested/scoped signals (ADR-0003), and can carry the trigger identity in the payload/header. The server helper
adapts the canonical signal JSON into Django form data. Final submission continues to use `contentType: 'form'` (and
native Django POST), which is required for files and normal form handling.

```text
incremental check → JSON signals (typed, ungated)
final submit      → normal Django form POST
```

### §2 — Validation boundary: run the whole form, patch one fragment

Django exposes no dependency metadata for `clean_<field>()` / `Form.clean()` / validators / uniqueness checks, so the
library cannot infer which cross-field rules depend on the triggering field. Therefore, for v1:

```python
form = MyForm(current_values)   # adapted from the JSON signals
form.is_valid()                 # full, exactly like final submit
# ... then patch ONLY the triggered field's fragment
```

This gives exact final-submit semantics, no second validation API, and correct cross-field behavior for free. The
cost — validators/DB checks on unrelated fields also run — is acceptable for v1 and controllable via `debounce`. An
opt-in per-field incremental hook is possible later **only if measurement shows a need**; it is deliberately excluded
now to avoid a second validation surface.

**"Preserve unrelated errors" needs no server state.** Because the SSE response patches only the triggered field's
wrapper, every other field's DOM (including its current error) is untouched automatically. The server computes the
full error set for the request but *selects* only the triggered fragment to patch; it keeps no error-state session.

### §3 — Lifecycle affordances (native primitives)

- **Stale responses**: rely on Datastar's built-in cancellation of in-flight requests to the same URL/method from the
  same initiating element; requests from different fields stay independent. Add a per-field token **only if**
  integration tests show cancellation is insufficient (e.g. the server finishes after a client abort). Document the
  dependency on this Datastar guarantee (verify against the pinned bundle).
- **Pending state**: use the native `data-indicator` on a **local** signal, e.g.
  `data-indicator:_validating_<field>` — the leading underscore keeps it local and out of backend requests by
  default. No custom start/finish bookkeeping. In a formset the indicator signal uses the ADR-0003 scope.
- **Which validation runs**: the whole form (§2). No per-field dependency inference.
- **Throttling**: `debounce` on the client; the view stays a normal Django view, so expensive checks can be cached or
  rate-limited by the host as usual.

### §4 — Validation URL propagation

`render_reactive_field` does not currently know the submit `action`. Make the validation URL explicit and let it
default to the submit action:

```django
{% render_reactive_form form action="/submit/" validate_action="/validate/" %}
```

`validate_action` defaults to `action`. The form *declaration* describes validation **timing** (`validate_on`); the
rendering/view layer supplies the **URL**. `render_reactive_form` threads `validate_action` into each field; standalone
`render_reactive_field` accepts it as a tag argument for manual layouts.

### §5 — Trigger identity is untrusted input

Whatever the transport, the field name in the request is client-supplied. Before acting, the server must verify that
the field **exists**, has `validate_on` **enabled**, the **event is permitted**, and the field **belongs to the
submitted form/formset scope**. Never dispatch to `clean_<name>()` or any method from an arbitrary client-provided
name.

### §6 — Minimal error accessibility (part of the fragment contract)

Incremental errors must be accessible from their first implementation, so the patched field fragment sets:

- `aria-invalid` on the control when it has an error;
- `aria-describedby` linking the control to a **stable** error-message element id;
- the error element carries that stable id.

This is the minimal slice of the future accessibility ADR that this feature cannot ship without; the broader a11y
contract (focus-first-invalid, error summary, grouped-control labeling) remains a separate ADR.

## Backward compatibility

- **Opt-in and additive.** Fields without `validate_on` behave exactly as today (submit-only validation). No change to
  existing forms, templates, or views.
- Using the feature requires wiring an action URL, the same as the current SSE-validation example already does.

## Consequences

- Incremental validation becomes a one-line field declaration instead of bespoke wiring, while remaining ordinary
  server-authoritative Django validation (whole-form run, single-fragment patch).
- New documented surface: `validate_on`/`debounce` kwargs, the `_validating_<field>` local signal, the JSON-signal
  validate request + trigger contract, and `validate_action`.
- Reinforces the backend-first thesis: the browser triggers, the server decides. The two request modes make the split
  explicit — JSON signals for incremental checks, form POST for final submit.

## Scope boundaries

- Canonical value semantics (and the JSON-signal payload shape) — [ADR-0002](0002-canonical-expression-semantics.md).
- Row-scoped signals / reactive formsets (used by the pending indicator and trigger scope) —
  [ADR-0003](0003-scoped-signals-and-reactive-formsets.md).
- Broader accessibility (focus-first-invalid, error summary, grouped-control labeling) — a separate a11y ADR; only the
  minimal per-field error contract (§6) is in scope here.
- No client-side validation engine, no per-field incremental hooks in v1, and no async validators expressed in
  JavaScript — validation stays in Python.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/fields.py` (`validate_on` / `debounce` kwargs on `ReactiveFieldMixin`),
  `src/rg/forms/templatetags/reactive_forms.py` (emit the default JSON-signal `data-on:*` handler, the
  `data-indicator` pending signal, and thread `validate_action`), `src/rg/forms/views.py`
  (`reactive_validate_response`: adapt canonical signal JSON → form data, run full `is_valid()`, verify the trigger
  identity per §5, patch only the triggered fragment), a single-field fragment template carrying the §6 `aria-*`
  contract, and docs + an example.
- Tests: a `validate_on="blur"` field fires a JSON-signal request (not `contentType:'form'`) and patches only its own
  fragment on error; unrelated fields' DOM errors are untouched; a valid value clears the field's error and pending
  state; an untrusted/unknown trigger field is rejected; forms without `validate_on` are unchanged.
- Verify against the pinned Datastar bundle: JSON-signal request contents, `data-indicator` behavior, and in-flight
  request cancellation (before deciding whether a stale-response token is needed at all).
