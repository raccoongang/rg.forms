# Order configurator comparison

**Requirement:** a plan/order form with conditional fields (enterprise contact
shown+required only for the Enterprise plan), a disabled seats field for the
single-seat plan, per-plan help text and unit price, a live total, coupon
validation, and — critically — a total the **server recomputes exactly** and
refuses to accept from the client.

- **rg.forms (runnable):**
  [`forms/order_configurator.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/forms/order_configurator.py) ·
  [`views/order_configurator.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/views/order_configurator.py) ·
  [`order_configurator/page.html`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/templates/examples/order_configurator/page.html)
- **Competitor fixtures (illustrative):**
  [`formik/order-configurator/`](fixtures/formik/order-configurator/form.tsx) ·
  [`react_hook_form/order-configurator/`](fixtures/react_hook_form/order-configurator/form.tsx) ·
  [`tanstack_form/order-configurator/`](fixtures/tanstack_form/order-configurator/form.tsx)

## Measured result

| Layer | rg.forms | Formik | RHF | TanStack |
|---|---:|---:|---:|---:|
| Form schema + validation | 69¹ | 54 | 61 | 74 |
| Rendering + reactivity | 23 | 115 | 98 | 173 |
| Client transport | —¹ | 67 | 54 | 39 |
| Backend validation + endpoint | —¹ | 78 | 68 | 65 |
| **Total** | **111** | **314** | **281** | **351** |

¹ rg.forms's 69-line form holds the fields, the conditional rules, the coupon
validation, **and** the authoritative Decimal recompute; the 19-line view just
renders and echoes the result.

## Where the code went

- Conditional visibility/requiredness/disabled state is `watch()`-driven JSX plus
  matching server-side branches in the client stacks; in rg.forms it is
  `visible_when` / `required_when` / `disabled_when`, enforced on both sides from
  one declaration.
- **The computed total has no faithful client-library equivalent.** The client
  stacks compute a preview in JS and then must *re-implement the exact rule on the
  server* to avoid trusting the browser. rg.forms shows the same float preview but
  the server recomputes the total with `Decimal` in `clean` and ignores any
  submitted value — the example's test asserts a tampered `total=999` is dropped.
- The leading-zero plan code `"001"` stays a **string** on both sides (strict
  canonical semantics), so `visible_when="$plan == '100'"` cannot silently break;
  the client stacks must be careful not to coerce it to a number.

## Trade-offs

`disabled_when` / `min_when` / `max_when` are client-only in rg.forms (documented
in the [parity matrix](../guide/custom-rendering.md#feature-parity-where-each-rule-is-enforced));
authoritative bounds go in a validator or `clean()`. The client stacks enforce
their client rules in the browser regardless, but still need the server copy.

## Reproduce

```bash
python tools/measure_comparisons.py
```
