# Team roster comparison

**Requirement:** a repeatable section of team-member rows, each with a role that
conditionally requires an email (owner/admin) and conditionally shows an admin
note (admin) — behaving **independently per row** — validated on the server.

- **rg.forms (runnable):**
  [`forms/team_formset.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/forms/team_formset.py) ·
  [`views/team_formset.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/views/team_formset.py) ·
  [`team_formset/page.html`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/templates/examples/team_formset/page.html)
- **Competitor fixtures (illustrative):**
  [`formik/team-roster/`](fixtures/formik/team-roster/form.tsx) ·
  [`react_hook_form/team-roster/`](fixtures/react_hook_form/team-roster/form.tsx) ·
  [`tanstack_form/team-roster/`](fixtures/tanstack_form/team-roster/form.tsx)

## Important: not the same feature

This is the one scenario where the slices are **not** functionally equal, and the
comparison says so up front:

- **rg.forms** implements a **static** Django formset (a fixed set of rows) whose
  rows are now independently reactive (ADR-0003). Dynamic **add / remove /
  reorder is not implemented yet** (a separate planned ADR).
- The **client stacks** implement a **dynamic** field array (`FieldArray` /
  `useFieldArray` / array mode) that adds and removes rows in the browser.

So the line counts below compare rg.forms's static-row implementation against a
strictly larger competitor feature. They still show where per-row wiring goes,
but read them with that asymmetry in mind.

## Measured result

| Layer | rg.forms (static) | Formik (dynamic) | RHF (dynamic) | TanStack (dynamic) |
|---|---:|---:|---:|---:|
| Row schema + validation | 27 | 42 | 43 | 44 |
| Rendering + reactivity | 37 | 115 | 83 | 151 |
| Client transport | — | 48 | 42 | 28 |
| Backend validation + endpoint | — | 50 | 62 | 42 |
| **Total** | **79** | **255** | **230** | **265** |

## Where the code went

- Per-row independence is automatic in rg.forms: each row gets a scoped signal
  namespace, so `required_when="$role == 'owner' || $role == 'admin'"` fires for
  *that* row with no per-row wiring. The client stacks index every field by array
  position (`members.${i}.email`) in both the schema and the JSX.
- Row binding and validation are `formset.is_valid()` in rg.forms; the client
  stacks map an array of rows to/from the API and re-validate each row on the
  server.

## Trade-offs

rg.forms's slice is static, so this is not an apples-to-apples feature match. But
the answer to "I need dynamic rows today" is **not** a client framework:
add / remove / reorder (drag-and-drop included) is a natural server-driven
interaction — a small Datastar handler posts the action (or the new order) and
the server re-renders the affected rows over SSE, the same mechanism Anders
Murphy's [one-billion-checkboxes demo](https://news.ycombinator.com/item?id=43971164)
uses to mutate cells in real time. What rg.forms lacks today is a *declarative*
helper that generates that wiring (a planned ADR); until then you write the
handler directly — still less code, and more performant, than introducing a
client field array. For a fixed or server-sized set of rows you need none of
that.

## Reproduce

```bash
python tools/measure_comparisons.py
```
