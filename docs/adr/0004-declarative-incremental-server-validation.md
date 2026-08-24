# ADR 0004 — Declarative incremental server validation

- Status: Proposed — Revision 2 (redesigned around Datastar request behavior and Django validation boundaries)
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Relates to: [ADR-0002](0002-canonical-expression-semantics.md) (canonical JSON signals are the request payload) and
  [ADR-0003](0003-scoped-signals-and-reactive-formsets.md) (scoped signal paths for the pending indicator and trigger
  identity). Reuses the existing SSE machinery (`reactive_form_response`).

## Revisions 2–3 — decisions resolved

The first draft assumed a `contentType: 'form'` request, which is wrong for this feature. Revision 3 also completes
the request contract (CSRF, trigger transport, JSON→form adapter, ID contract):

- **Transport: the default Datastar JSON-signal request**, not `contentType: 'form'` (which sends *no signals* and
  runs native form validity gating that would block validation of a partially-filled form). Final submit keeps the
  form POST (Decision §1).
- **CSRF**: the render tag is context-aware and sends Django's token as an `X-CSRFToken` header, serialized as a safe
  JS string literal, with token-rotation tested; never `csrf_exempt` (Decision §1a).
- **Trigger transport: an `X-RG-Validate-Field` header** carrying the canonical field path (scoped for formsets), not
  a marker mixed into the signal object; cross-checked against the URL discriminator (Decision §5).
- **JSON→form adapter** is a first-class component with a defined mapping table, **scope authorization** (a decoded
  scope must belong to the form being validated), and **signal-scope filtering** (only the current form's scope is
  read) (Decision §2a).
- **Validation boundary: run the whole form, patch one fragment** (Option A). No per-field dependency inference
  (Decision §2).
- **Stale responses: use Datastar 1.0.2's method+URL cancellation** (it cancels by method+URL regardless of element),
  turned into per-field independence via a **`?__rg_field=<path>` URL discriminator** (Decision §3).
- **Pending state: the native `data-indicator`** on a scoped local signal `_rgForms.<scope>.validating.<field>`
  (Decision §3).
- **Validation URL is explicit** — `validate_action`, with defined unset/empty/inherit semantics (Decision §4).
- **Trigger identity is untrusted input** and must be verified server-side (Decision §5).
- **Stable wrapper/error IDs** (with an `id_for_label`-empty fallback, exposed in the renderer context) make the
  single-field patch implementable; minimal `aria-*` is in the fragment contract from day one (Decision §6).

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

### §1a — CSRF

A JSON Datastar POST does **not** carry the form's hidden `csrfmiddlewaretoken` field, so a normal CSRF-protected view
rejects it. The generated handler must send the token as an `X-CSRFToken` header, which `CsrfViewMiddleware` accepts:

```html
data-on:blur="@post('/validate/', {headers: {'X-CSRFToken': '<token>'}})"
```

To supply `<token>`, the render tag becomes **context-aware** (reads the request's CSRF token from the template
context) and injects the header into every generated incremental request. Two implementation requirements:

- **serialize the token and the URL as safe JavaScript string literals** (e.g. `json.dumps`/`escapejs`), never
  hand-built quoting — the token and a `?__rg_field=…` URL both end up inside a JS expression attribute;
- **test CSRF token rotation/masking** with Django's normal CSRF test client (the per-response masked token must be
  accepted).

`CsrfViewMiddleware` is required. `csrf_exempt` is **not** an acceptable solution.

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

### §2a — JSON-signals → Django form-data adapter

Adapting the canonical signal JSON into the `QueryDict` a Django form binds is more than flattening. It is a
first-class component (built on the ADR-0002 normalization and ADR-0003 scoping), with this mapping:

| Signal (canonical) | Django form-data |
|---|---|
| scoped path `rgForms.<scope>.name` | prefixed HTML name `form-0-name` (reverse of the ADR-0003 scope map) |
| unscoped path `name` | `name` |
| array value | multiple `QueryDict` entries under one key (`getlist` semantics) |
| boolean `true` | the widget's checked value (e.g. `"on"`) |
| boolean `false` | key **absent** (native unchecked-checkbox semantics) |
| `null` / empty | the field's empty form representation (per ADR-0002 §2) |
| `external_signals` / reserved (`rgForms`, `_rgForms…`) | **dropped** — never become form fields |
| file inputs | unavailable in incremental validation — skipped (files validate on submit only) |

The adapter is shared and tested, not ad-hoc logic inside the view helper.

**Scope authorization (not just decoding).** A valid Base32 scope is not an authorized one. The adapter must resolve
each scoped path against the *specific* form/formset instance it was handed and drop/reject any path whose scope does
not belong to it — a client must not submit an encoded prefix for a different form and have it flattened into
arbitrary form keys.

**Signal-scope filtering.** Datastar sends all non-local signals, so on a page with several reactive forms the request
carries unrelated signal trees. For v1 the **helper selects only the current form's scope** (plus that form's declared
`external_signals`) from the received object and ignores the rest. Consequently, multiple *unprefixed* forms on one
page must use **distinct Django prefixes** to avoid signal collisions — document this. (A client-side `filterSignals`
on the generated request is a possible later optimization.)

### §3 — Lifecycle affordances (native primitives)

- **Stale responses (Datastar 1.0.2 model)**: 1.0.2 *"cancel[s] in-flight requests with the same method and URL,
  **regardless of the element** that initiated the request."* So a single shared `POST /validate/` endpoint would make
  fields cancel **each other** (blurring `email` would abort an in-flight `username` check). We turn that into
  correct per-field behavior with a **per-field URL discriminator**:

  ```text
  POST /validate/?__rg_field=username
  POST /validate/?__rg_field=rgForms.<scope>.email     # URL-encoded field path
  ```

  Same field re-fires → same method+URL → Datastar cancels the stale request; different fields → different URLs →
  concurrent. The authoritative trigger contract remains the `X-RG-Validate-Field` header (§5); the query
  discriminator exists to give Datastar the right cancellation key, and the server **cross-checks** the query value
  against the header and rejects a mismatch. (A per-field `AbortController` is the alternative but adds local state and
  generated expressions; the URL key uses 1.0.2 as-is.)
- **Pending state**: use the native `data-indicator` on a **local** signal under the reserved scope:
  `_rgForms.validating.<field>` (unprefixed) or `_rgForms.<scope>.validating.<field>` (scoped, per ADR-0003). A
  leading-underscore path component keeps the signal local and out of backend requests — verify that underscore-prefix
  exclusion still applies to a *nested* path component in the targeted bundle. No custom start/finish bookkeeping.
- **Which validation runs**: the whole form (§2). No per-field dependency inference.
- **Throttling**: `debounce` on the client; the view stays a normal Django view, so expensive checks can be cached or
  rate-limited by the host as usual.

### §4 — Validation URL propagation

`render_reactive_field` does not currently know the submit `action`. Make the validation URL explicit and let it
default to the submit action:

```django
{% render_reactive_form form action="/submit/" validate_action="/validate/" %}
```

The form *declaration* describes validation **timing** (`validate_on`); the rendering/view layer supplies the **URL**.
`render_reactive_form` threads `validate_action` into each field; standalone `render_reactive_field` accepts it as a
tag argument for manual layouts. Because `action` itself defaults to `""`, the three states are distinguished
explicitly (so "unset" and "current URL" are never the same accident):

| `validate_action` | Meaning |
|---|---|
| omitted | inherit `action` |
| `""` | validate against the **current URL** (intentional) |
| a URL | validate against that URL |
| `None` (a field has `validate_on` but no resolvable action) | the field cannot render its handler → a system-check/config error, not a silent no-op |

### §5 — Trigger identity: header transport, treated as untrusted

The triggering field travels in a **header**, not mixed into the canonical signal object (which keeps the signal
payload clean):

```text
X-RG-Validate-Field: username                    # ordinary form
X-RG-Validate-Field: rgForms.<scope>.username     # scoped form / formset row
```

The server resolves that path against the known form/formset structure. Because it is client-supplied, it must verify
that the field **exists**, has `validate_on` **enabled**, the **event is permitted**, and the field **belongs to the
submitted form/formset scope** — and only then act. Never dispatch to `clean_<name>()` or any method from an arbitrary
client-provided name. The scope is derivable from the path, so no separate scope header is required. The server also
**cross-checks the header against the `?__rg_field=` URL discriminator (§3)** and rejects a mismatch.

### §6 — Patch-target contract and minimal error accessibility

A single-field patch needs a **guaranteed, formset-safe wrapper id** to target. `field.id_for_label` is prefix-safe
but can be **empty** (e.g. `auto_id=False`), which would collapse every wrapper to `_field`. So the contract derives
ids from a guaranteed-non-empty `control_id`:

```text
control_id = field.id_for_label or ("rg_field_" + b32(field.html_name))   # injective, id-safe fallback
```

| Element | Id |
|---|---|
| input/control | `{control_id}` |
| field wrapper (patch target) | `{control_id}_field` |
| help text | `{control_id}_help` |
| error message | `{control_id}_error` |

These ids are **exposed in the stable renderer context** (`control_id`, `wrapper_id`, `help_id`, `error_id`) so
override templates do not reproduce the algorithm. Then the accessibility attributes, present from first
implementation:

- `aria-invalid` on the control when it has an error;
- `aria-describedby` linking the control to the error (and help) ids above.

Without the stable wrapper id, "patch only this field" is not generically implementable. The broader a11y contract
(focus-first-invalid, error summary, grouped-control labeling) remains a separate ADR; only this per-field slice is in
scope here.

## Backward compatibility

- **Opt-in and additive.** Fields without `validate_on` behave exactly as today (submit-only validation). No change to
  existing forms, templates, or views.
- Using the feature requires wiring an action URL, the same as the current SSE-validation example already does.

## Consequences

- Incremental validation becomes a one-line field declaration instead of bespoke wiring, while remaining ordinary
  server-authoritative Django validation (whole-form run, single-fragment patch).
- New documented surface: `validate_on`/`debounce` kwargs, the `_rgForms.…validating.<field>` local signal, the
  JSON-signal validate request, the `X-CSRFToken` + `X-RG-Validate-Field` header contract, the JSON→form-data adapter,
  the deterministic fragment ids, and `validate_action`.
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
  `src/rg/forms/templatetags/reactive_forms.py` (context-aware CSRF-token injection with safe-literal serialization
  §1a, emit the default JSON-signal `data-on:*` handler posting to `?__rg_field=<encoded path>` §3 + the
  `X-RG-Validate-Field` header, the `data-indicator` pending signal, expose the §6 ids in context, and thread
  `validate_action` with the §4 unset/empty/inherit rules), `src/rg/forms/views.py` (`reactive_validate_response`:
  run the §2a adapter with scope authorization + signal-scope filtering, full `is_valid()`, cross-check the trigger
  header against the URL discriminator §5, patch only the §6 wrapper), the shared JSON→form-data adapter (§2a, built
  on ADR-0002/0003), a single-field fragment template carrying the §6 id + `aria-*` contract, and docs + an example.
- Tests: a `validate_on="blur"` field fires a JSON-signal request (not `contentType:'form'`) to `?__rg_field=…`
  carrying `X-CSRFToken` and `X-RG-Validate-Field`, and passes a **CSRF-enforced** view (incl. masked/rotated token);
  two different fields hit **distinct** URLs (so 1.0.2 method+URL cancellation keeps them concurrent) while the same
  field's re-fire cancels the stale request; it patches only its own §6 wrapper on error; unrelated fields' DOM errors
  are untouched; a value clears the field's error and pending state; the adapter round-trips arrays / booleans / null
  / scoped paths and **rejects a scope not belonging to the form**; a header/URL-discriminator mismatch is rejected;
  an empty `id_for_label` still yields a unique wrapper id; forms without `validate_on` are unchanged.
- Verify against **Datastar 1.0.2**: JSON-signal request contents, `data-indicator` on a nested `_`-prefixed path, and
  the method+URL cancellation behavior that the `?__rg_field=` discriminator relies on.
