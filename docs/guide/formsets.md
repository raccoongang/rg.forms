# Formsets and scoped signals

A Django formset renders the *same* logical field name in every row
(`form-0-role`, `form-1-role`, …). Reactive rules must behave **independently
per row**: typing in row 0 must not change row 1, and a per-row conditional must
fire only for its own row. rg.forms makes standard formsets fully reactive with
no client state engine (ADR-0003).

## It just works

Write your form once, exactly as for a standalone form:

```python
from django.forms import formset_factory
from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

class RowForm(ReactiveForm):
    role = ReactiveChoiceField(choices=[("admin", "Admin"), ("editor", "Editor")])
    admin_note = ReactiveCharField(required=False, visible_when="$role == 'admin'")

RowFormSet = formset_factory(RowForm, extra=2)
```

Render the rows and seed the whole formset's signals:

```html
<form data-signals='{% reactive_formset_signals formset %}'>
  {{ formset.management_form }}
  {% for row in formset.forms %}
    {% render_reactive_field row.role %}
    {% render_reactive_field row.admin_note %}
  {% endfor %}
</form>
```

Each row now:

- binds to its **own** signal — `data-bind="rgForms.<scope>.role"`;
- evaluates its `visible_when` / `required_when` / `computed` against **that
  row's** signal — `$rgForms.<scope>.role`;
- is seeded with its own initial values under `rgForms.<scope>`.

`{% reactive_formset_signals %}` is required for formsets because a single form
cannot see its sibling rows; it emits one nested entry per (row, field).

## How the scope works

The scope key is an injective Base32 encoding of the Django form prefix
(`form-0` → `pmzxxe3jnga`). You never write it — authors keep writing `$role`,
and the renderer rewrites references (on the AST, so string literals and
near-matches like `$role_id` are never touched) to the scoped path.

This applies to **any prefixed form**, not only formsets: a standalone form
constructed with `prefix="…"` also gets scoped signals.

## Unprefixed forms are unchanged

With no prefix the signal name equals the logical name, the rewrite is the
identity, and seeding is flat — byte-compatible with non-formset usage.

## Out of scope (for now)

Dynamic add / remove / reorder of rows (`TOTAL_FORMS` management, `DELETE`/
`ORDER`, server re-render) is a separate concern. This feature delivers the
invariant that makes it possible: **static rows that behave independently.**
