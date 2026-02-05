# Conditional Attributes

Control field states dynamically — disable, make read-only, or change help text based on other fields.

## `disabled_when`

Conditionally disable a field:

```python
class SubscriptionForm(ReactiveForm):
    subscription_type = ReactiveChoiceField(choices=[
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
    ])

    max_users = ReactiveIntegerField(
        label="Max Users",
        initial=1,
        disabled_when="$subscription_type == 'free'",
    )
```

When `subscription_type` is "free", the `max_users` input is disabled.

## `read_only_when`

Conditionally make a field read-only:

```python
api_key = ReactiveCharField(
    label="API Key",
    required=False,
    read_only_when="$subscription_type != 'premium'",
)
```

## `help_text_when`

Show different help text based on conditions. Pass a dict of `{expression: help_text}`:

```python
max_users = ReactiveIntegerField(
    label="Max Users",
    initial=1,
    disabled_when="$subscription_type == 'free'",
    help_text_when={
        "$subscription_type == 'free'": "Upgrade to Basic or Premium to customize",
        "$subscription_type == 'basic'": "Basic allows up to 10 users",
        "$subscription_type == 'premium'": "Premium allows unlimited users",
    },
)
```

Each entry generates a `<span>` with a `data-show` attribute — only the matching help text is visible.

## `placeholder_when`

Dynamic placeholder text, same dict syntax:

```python
search = ReactiveCharField(
    placeholder_when={
        "$mode == 'simple'": "Search by name...",
        "$mode == 'advanced'": "Use field:value syntax...",
    },
)
```

## `min_when` / `max_when`

Dynamic min/max constraints:

```python
quantity = ReactiveIntegerField(
    min_when={
        "$order_type == 'bulk'": 10,
        "$order_type == 'standard'": 1,
    },
    max_when={
        "$order_type == 'bulk'": 10000,
        "$order_type == 'standard'": 99,
    },
)
```

## Combining attributes

All conditional attributes can be used together:

```python
billing_email = ReactiveEmailField(
    label="Billing Email",
    required=False,
    visible_when="$plan == 'basic' || $plan == 'premium'",
    required_when="$plan == 'basic' || $plan == 'premium'",
    help_text_when={
        "$plan == 'basic'": "We'll send monthly invoices here",
        "$plan == 'premium'": "We'll send monthly invoices and usage reports here",
    },
)
```
