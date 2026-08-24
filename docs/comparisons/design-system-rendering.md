# Design-system rendering comparison

**Requirement:** render a profile form (with an async email check and a
conditional public-handle field) in the project's own visual style — the concern
here is the **rendering layer**, not the rules.

- **rg.forms (runnable):**
  [`forms/design_systems.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/forms/design_systems.py) ·
  [`views/design_systems.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/views/design_systems.py) ·
  [`design_systems/page.html`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/templates/examples/design_systems/page.html)
- **Competitor fixtures (illustrative):**
  [`formik/design-system-rendering/`](fixtures/formik/design-system-rendering/form.tsx) ·
  [`react_hook_form/design-system-rendering/`](fixtures/react_hook_form/design-system-rendering/form.tsx) ·
  [`tanstack_form/design-system-rendering/`](fixtures/tanstack_form/design-system-rendering/form.tsx)

## Measured result

| Layer | rg.forms | Formik | RHF | TanStack |
|---|---:|---:|---:|---:|
| Form + server validation | 26¹ | 30 | 36 | 40 |
| Rendering (page, both adapters) | 35 | 117 | 156 | 157 |
| Client transport | — | 53 | 55 | 24 |
| Backend endpoint | 21¹ | 49 | 64 | 49 |
| **Total** | **82** | **249** | **311** | **270** |

¹ rg.forms's server validation lives in the *form* row; the 21-line "view" is
the page + validate endpoint (transport), not a re-declared server schema — the
competitors' backend column is endpoint **plus** duplicated validation rules.

The rendering row is the crux: the client stacks build a reusable field-component
library (`TextField`, `SelectField` wrappers around `useField`/`useController`/
field render-props) and wire each field through it. rg.forms fields go through the
**one** project-wide `rg_forms/field.html` adapter — the example's page even shows
the *same* form rendered by two adapters (style-switched so ids never collide)
with no form-class change.

## Where the code went — and a fairness note

The measured rg.forms rendering here is the demo page plus its *second* minimal
adapter, written out for illustration. In a real project the
design-system adapter is written **once** and amortized across every form (it is
excluded as shared infrastructure in all other scenarios, symmetrically with the
client stacks' generic component libraries). The client stacks, by contrast, wire
each field to a component **per form**. The more forms a project has, the wider
this gap grows, because rg.forms's rendering cost is paid once, not per form.

## Trade-offs

A mature React design system already ships form-aware field components; if you
have one, its per-field wiring is cheap incremental work. rg.forms's model is a
single template contract ([documented here](../reference/template-tags.md#context-contract))
rather than a component API — different ergonomics, same goal.

## Reproduce

```bash
python tools/measure_comparisons.py
```
