# Coming from Formik / React Hook Form / TanStack Form

If you build forms with Formik, React Hook Form (RHF), or TanStack Form, this page maps what you already know onto
rg.forms, shows where the two approaches differ in kind, and states honestly what rg.forms does today versus what is
on the roadmap.

## The one-paragraph version

React form libraries are **client-side state engines**: they own the form's values, per-field touched/dirty state,
validation lifecycle, and submission state in the browser, and your server re-validates afterwards. rg.forms inverts
that. The **Python form class is the single source of truth** — fields, rules, validation, and initial state all live
on the server; [Datastar](https://data-star.dev) provides the client reactivity; and your project owns **one rendering
adapter** for its design system instead of hand-written JSX per form. You write the schema once, not twice.

So the framing is:

> **rg.forms does the job of a form library — dynamic, validated, reactive forms — the backend-first way: one Python
> schema, server-authoritative validation, and a swappable design-system renderer.**

It is not a drop-in port (you rewrite the schema in Python rather than translating JS line for line), but for the large
majority of business forms — CRUD, onboarding, configuration, conditional fields, computed totals, cascading dropdowns,
server-validated submits — the backend-first model removes a lot of code and does the job at least as cleanly. Where
responsibilities live, and the handful of interaction-heavy cases where you still reach for a client component, are
covered in [A different philosophy](#a-different-philosophy-not-a-feature-checklist).

## Mental-model shift

| You are used to… | In rg.forms… |
|---|---|
| Defining the shape/validation in JS (Yup/Zod) **and** again on the server | Defining it **once** in a Python `ReactiveForm` |
| `useState`/`useForm` holding values in the browser | Datastar **signals**, bound with `data-bind:field`, seeded from the server |
| `onChange`/`onBlur` handlers wired per input | Declarative expressions (`visible_when`, `required_when`, `computed`) evaluated reactively |
| A `<Field>`/`register()` component per input | One overridable `rg_forms/field.html` adapter for your whole design system |
| Submitting JSON to a REST endpoint, mapping errors back by hand | A normal Django POST (or SSE submit); Django errors render against the same fields |
| Client validation is authoritative until the API rejects it | The **server is always authoritative**; the client mirrors the rules for UX |

## Concept mapping

| Capability | Formik / RHF / TanStack | rg.forms |
|---|---|---|
| Field value / binding | `values`, `register`, controlled inputs | `data-bind:field` signal (two-way) |
| Initial values | `initialValues` / `defaultValues` | Django form `initial=` → serialized to `data-signals` |
| Conditional visibility | render `{show && <Field/>}` | `visible_when="$type == 'urgent'"` (client `data-show` + server skips it) |
| Conditional requirement | `validationSchema` branches | `required_when="…"` (reactive `data-attr:required` + server-enforced) |
| Derived/computed values | `useEffect` recomputes into state | `computed="$qty * $price"` (client + server recompute) |
| Dependent selects | fetch on change, set options in state | `choices_from` + `depends_on` (server re-renders the field) |
| Cross-field validation | schema `.test()` / `superRefine` | `clean()` / `clean_<field>()` on the form |
| Submit | `onSubmit` → fetch/axios | native Django POST, or SSE submit via `render_reactive_form … action=` |
| Error display | `errors`, `<ErrorMessage/>` | `field.errors` in the field template; SSE patches errors without a reload |
| Design-system inputs | a component library of `<Field>`s | one `field.html` dispatcher → your components ([Custom Rendering](guide/custom-rendering.md)) |

A side-by-side of the same form:

=== "Formik (React)"

    ```jsx
    const schema = Yup.object({
      orderType: Yup.string().required(),
      priority: Yup.string().when('orderType', {
        is: 'urgent',
        then: (s) => s.required(),
      }),
    });

    function OrderForm() {
      return (
        <Formik initialValues={{ orderType: 'standard', priority: '' }}
                validationSchema={schema}
                onSubmit={(v) => api.post('/orders/', v)}>
          {({ values }) => (
            <Form>
              <Field as="select" name="orderType">…</Field>
              {values.orderType === 'urgent' && (
                <Field as="select" name="priority">…</Field>
              )}
              <ErrorMessage name="priority" />
            </Form>
          )}
        </Formik>
      );
    }
    // Plus: the same rules re-declared in a Django serializer/view on the server.
    ```

=== "rg.forms (Python)"

    ```python
    class OrderForm(ReactiveForm):
        order_type = ReactiveChoiceField(choices=[("standard", "Standard"), ("urgent", "Urgent")])
        priority = ReactiveChoiceField(
            choices=[("low", "Low"), ("high", "High")],
            required=False,
            visible_when="$order_type == 'urgent'",
            required_when="$order_type == 'urgent'",
        )
    ```

    ```html
    {% render_reactive_form form action="/orders/" %}
    ```

    The visibility, the conditional requirement, and the validation are declared once and enforced on both sides.
    There is no second schema and no REST layer to keep in sync.

## Where rg.forms is the better fit

- **No duplicated schema.** One Python class instead of Yup/Zod on the client plus serializers on the server.
- **No build pipeline or API layer** for the common case — a normal Django form POST, optionally upgraded to SSE.
- **Security by construction.** Every rule is re-evaluated server-side; a client that skips or fakes a rule cannot
  submit past it.
- **Smaller surface.** No client framework, no virtual DOM, minimal JavaScript.

## A different philosophy, not a feature checklist

Formik, RHF, and TanStack Form are **client-side state engines** by design: the browser owns the values, the
touched/dirty bookkeeping, the validation timing, and the submission state; the server re-checks afterwards. rg.forms
is **backend-authoritative by design**, so it does not reproduce that engine — and that is the point, not a shortfall.
Keeping form state and validation logic in the browser is exactly what rg.forms exists to avoid.

The responsibilities a React library keeps in the browser map cleanly onto where rg.forms puts them:

| What a React form library owns in the browser | Where rg.forms puts it |
|---|---|
| The schema and validation rules | On the server, in the `ReactiveForm` — the single source of truth |
| Current field values | Datastar signals (`data-bind`), seeded from the server |
| Rule evaluation (visibility, requiredness, computed) | Declarative expressions — evaluated on the client for UX, re-evaluated on the server for correctness |
| Which fields are valid | The server, authoritatively; errors are patched back via SSE |
| Touched / dirty / submitting UX state | Optional lightweight Datastar signals where a screen wants them — not a bespoke state machine |

There is deliberately **no client form-state engine to build**.

### On the roadmap

A few capabilities are genuinely useful and *reinforce* the server-first model rather than pull against it. They are
not built yet:

- **Inline (incremental) server validation** — validate one field against the server *before* submit, e.g. "is this
  username taken?" as the user leaves the field: debounced, with a pending indicator, cancelling stale requests. This
  is server validation triggered earlier, not client-side logic. The pieces already exist today
  (`reactive_form_response` + `data-on:input__debounce.400ms="@post(...)"` — see
  [SSE Validation](guide/sse-validation.md)); what is missing is a declarative shorthand (e.g. `validate_on="blur"`) so
  you do not hand-wire it each time.
- **Scoped signals for dynamic formsets** — formsets submit correctly today (prefixed `name`/`id` round-trip), but
  sibling rows currently share a Datastar signal. Per-row scoped signals plus add / remove / reorder would make
  repeatable sections fully reactive — the Django analogue of Formik/RHF field arrays.
- **Accessibility wiring** — associating errors to inputs (`aria-invalid`, `aria-describedby`) and focusing the first
  invalid field.

Optional UX niceties such as a `dirty` guard or a `submitting` indicator are not an engine — where a screen wants them,
they are a few Datastar signals, and a small number may become first-class helpers if there is demand.

See the [feature-parity matrix](guide/custom-rendering.md#feature-parity-where-each-rule-is-enforced) for exactly which
layer (browser / Datastar / server) enforces each rule today.

For the genuinely client-interactive cases — rich editors, drag/drop uploads, autocomplete controls, offline/autosave
forms — treat rg.forms as the server-authoritative core and drop to a client component where the interaction needs it.
The [custom rendering](guide/custom-rendering.md) adapter is that escape hatch.

## Choosing between them

**Reach for rg.forms when** the form is fundamentally about capturing and validating data against server-side rules —
which is most business software. You get one schema, server-authoritative validation, and reactive UX without a
frontend application.

**Keep a React form library when** the form itself is the interactive product: real-time client-only state, offline
persistence, heavy client-side computation, or a component ecosystem you must integrate. Even then, rg.forms can own
the pages that are ordinary forms while the client library owns the few that are not.
