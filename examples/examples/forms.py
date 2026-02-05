"""Example reactive forms demonstrating rg.forms features."""

from django import forms

from rg.forms import (
    FieldGroup,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDecimalField,
    ReactiveEmailField,
    ReactiveForm,
    ReactiveIntegerField,
)


class FieldGroupsForm(ReactiveForm):
    """Example form demonstrating Phase 3 Field Groups.

    Field groups allow organizing fields into logical sections with:
    - Shared visibility rules (visible_when on the group)
    - Visual grouping with labels and descriptions
    - Custom CSS classes for styling
    """

    account_type = ReactiveChoiceField(
        label="Account Type",
        choices=[
            ("", "-- Select --"),
            ("personal", "Personal"),
            ("business", "Business"),
        ],
    )

    # Personal info fields (always visible)
    first_name = ReactiveCharField(label="First Name")
    last_name = ReactiveCharField(label="Last Name")
    email = ReactiveEmailField(label="Email")

    # Business info fields (only for business accounts)
    company_name = ReactiveCharField(label="Company Name")
    company_size = ReactiveChoiceField(
        label="Company Size",
        choices=[
            ("", "-- Select --"),
            ("1-10", "1-10 employees"),
            ("11-50", "11-50 employees"),
            ("51-200", "51-200 employees"),
            ("200+", "200+ employees"),
        ],
    )
    tax_id = ReactiveCharField(label="Tax ID", required=False)

    # Billing info (only for business accounts)
    billing_address = ReactiveCharField(label="Billing Address")
    billing_city = ReactiveCharField(label="City")
    billing_country = ReactiveChoiceField(
        label="Country",
        choices=[
            ("", "-- Select --"),
            ("us", "United States"),
            ("uk", "United Kingdom"),
            ("de", "Germany"),
            ("fr", "France"),
        ],
    )

    class Meta:
        field_groups = {
            "account": FieldGroup(
                fields=["account_type"],
                label="Account Type",
                description="Choose your account type to see relevant options.",
            ),
            "personal": FieldGroup(
                fields=["first_name", "last_name", "email"],
                label="Personal Information",
            ),
            "business": FieldGroup(
                fields=["company_name", "company_size", "tax_id"],
                label="Business Information",
                description="Required for business accounts.",
                visible_when="$account_type == 'business'",
            ),
            "billing": FieldGroup(
                fields=["billing_address", "billing_city", "billing_country"],
                label="Billing Address",
                description="Where should we send invoices?",
                visible_when="$account_type == 'business'",
            ),
        }


class ConditionalAttributesForm(ReactiveForm):
    """Example form demonstrating Phase 2.5 conditional attributes.

    Shows how to use:
    - disabled_when: Conditionally disable fields
    - read_only_when: Conditionally make fields read-only
    - help_text_when: Dynamic help text based on conditions
    """

    subscription_type = ReactiveChoiceField(
        label="Subscription Type",
        choices=[
            ("", "-- Select --"),
            ("free", "Free"),
            ("basic", "Basic"),
            ("premium", "Premium"),
        ],
    )

    # disabled_when: Disabled for free tier
    max_users = ReactiveIntegerField(
        label="Max Users",
        min_value=1,
        initial=1,
        disabled_when="$subscription_type == 'free'",
        help_text_when={
            "$subscription_type == 'free'": "Upgrade to Basic or Premium to customize user limit",
            "$subscription_type == 'basic'": "Basic allows up to 10 users",
            "$subscription_type == 'premium'": "Premium allows unlimited users",
        },
    )

    # read_only_when: Read-only for non-premium
    api_key = ReactiveCharField(
        label="API Key",
        required=False,
        read_only_when="$subscription_type != 'premium'",
        help_text_when={
            "$subscription_type != 'premium'": "API access requires Premium subscription",
            "$subscription_type == 'premium'": "Your API key for programmatic access",
        },
    )

    # visible_when + required_when combo
    billing_email = ReactiveEmailField(
        label="Billing Email",
        required=False,
        visible_when="$subscription_type == 'basic' || $subscription_type == 'premium'",
        required_when="$subscription_type == 'basic' || $subscription_type == 'premium'",
    )


class BackendValidationForm(ReactiveForm):
    """Example form demonstrating backend expression evaluation.

    This form shows how rg.forms evaluates expressions on the backend:
    1. visible_when - hidden fields are SKIPPED in validation
    2. required_when - dynamic requirements are ENFORCED
    3. computed - values are RECALCULATED on server (ignores submitted value)

    Try submitting with different values to see backend validation in action.
    """

    order_type = ReactiveChoiceField(
        label="Order Type",
        choices=[
            ("", "-- Select --"),
            ("standard", "Standard"),
            ("urgent", "Urgent"),
            ("bulk", "Bulk"),
        ],
    )

    # visible_when: Only visible for urgent orders
    # Backend SKIPS validation when hidden (even though required=True)
    priority = ReactiveChoiceField(
        label="Priority Level",
        choices=[
            ("", "-- Select --"),
            ("normal", "Normal"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        visible_when="$order_type == 'urgent'",
        required=True,  # Required but only when visible!
    )

    # required_when: Required only for bulk orders
    # Backend ENFORCES this requirement
    bulk_discount_code = ReactiveCharField(
        label="Bulk Discount Code",
        required=False,
        required_when="$order_type == 'bulk'",
        visible_when="$order_type == 'bulk'",
        help_text="Required for bulk orders",
    )

    quantity = ReactiveIntegerField(
        label="Quantity",
        min_value=1,
        initial=1,
    )

    unit_price = ReactiveDecimalField(
        label="Unit Price",
        min_value=0,
        decimal_places=2,
        initial="10.00",
    )

    # computed: Backend RECALCULATES this value
    # Even if user submits a different value, server computes the correct one
    total = ReactiveDecimalField(
        label="Total (computed)",
        computed="$quantity * $unit_price",
        required=False,
        decimal_places=2,
    )


class OrderForm(ReactiveForm):
    """Example order form demonstrating visibility rules.

    Shows how to use visible_when to conditionally show fields
    based on other field values.
    """

    order_type = ReactiveChoiceField(
        choices=[
            ("", "-- Select --"),
            ("standard", "Standard Order"),
            ("urgent", "Urgent Order"),
            ("bulk", "Bulk Order"),
        ],
        label="Order Type",
    )

    # Only visible when order_type is 'urgent'
    priority = ReactiveChoiceField(
        choices=[
            ("normal", "Normal"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        visible_when="$order_type == 'urgent'",
        label="Priority Level",
        required=False,
    )

    # Only visible when order_type is 'bulk'
    quantity = ReactiveIntegerField(
        visible_when="$order_type == 'bulk'",
        label="Bulk Quantity",
        required=False,
        min_value=10,
    )

    # Only visible when order_type is 'bulk'
    discount_code = ReactiveCharField(
        visible_when="$order_type == 'bulk'",
        label="Discount Code",
        required=False,
        max_length=20,
    )


class PriceCalculatorForm(ReactiveForm):
    """Example form demonstrating computed fields.

    Shows how to use computed attribute for automatic calculations.
    """

    quantity = ReactiveIntegerField(
        label="Quantity",
        min_value=1,
        initial=1,
    )

    unit_price = ReactiveDecimalField(
        label="Unit Price",
        min_value=0,
        decimal_places=2,
        initial="10.00",
    )

    # Computed field - will be calculated from quantity * unit_price
    total = ReactiveDecimalField(
        label="Total",
        computed="$quantity * $unit_price",
        required=False,
        decimal_places=2,
    )


class ContactForm(ReactiveForm):
    """Example form demonstrating dynamic requirements and validation.

    Shows how to use required_when for conditional field requirements,
    plus standard Django field validation (EmailField, min_length).
    """

    contact_method = ReactiveChoiceField(
        choices=[
            ("email", "Email"),
            ("phone", "Phone"),
            ("both", "Both"),
        ],
        label="Preferred Contact Method",
    )

    # ReactiveEmailField validates email format via Django's EmailField
    email = ReactiveEmailField(
        label="Email Address",
        required_when="$contact_method == 'email' || $contact_method == 'both'",
        required=False,
    )

    # min_length=10 ensures phone has at least 10 characters
    phone = ReactiveCharField(
        label="Phone Number",
        required_when="$contact_method == 'phone' || $contact_method == 'both'",
        required=False,
        min_length=10,
        help_text="At least 10 digits",
    )


# =============================================================================
# Sample data for cascading example (in real app, this comes from database)
# =============================================================================

CATEGORIES = [
    {"id": 1, "name": "Electronics"},
    {"id": 2, "name": "Clothing"},
    {"id": 3, "name": "Books"},
]

PRODUCTS = [
    # Electronics
    {"id": 101, "category_id": 1, "name": "Laptop", "price": 999.99},
    {"id": 102, "category_id": 1, "name": "Smartphone", "price": 699.99},
    {"id": 103, "category_id": 1, "name": "Headphones", "price": 149.99},
    # Clothing
    {"id": 201, "category_id": 2, "name": "T-Shirt", "price": 29.99},
    {"id": 202, "category_id": 2, "name": "Jeans", "price": 79.99},
    {"id": 203, "category_id": 2, "name": "Jacket", "price": 129.99},
    # Books
    {"id": 301, "category_id": 3, "name": "Python Guide", "price": 49.99},
    {"id": 302, "category_id": 3, "name": "Django Manual", "price": 39.99},
    {"id": 303, "category_id": 3, "name": "Web Development", "price": 59.99},
]


def get_categories():
    """Get all categories (simulates Category.objects.all())."""
    return CATEGORIES


def get_products_for_category(category_id):
    """Get products for a category (simulates Product.objects.filter(category_id=...))."""
    if not category_id:
        return []
    category_id = int(category_id)
    return [p for p in PRODUCTS if p["category_id"] == category_id]


def get_product_by_id(product_id):
    """Get a product by ID."""
    if not product_id:
        return None
    product_id = int(product_id)
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


class CascadingForm(ReactiveForm):
    """Example form demonstrating cascading/dependent dropdowns.

    When category changes, the product dropdown is repopulated via
    server-side form re-rendering (not client-side data fetching).

    This uses DECLARATIVE cascading - no __init__ override needed!
    The ReactiveForm base class handles:
    - Populating choices from choices_from callable
    - Detecting parent value and calling choices_from(parent_value)
    - Resetting dependent field when parent changes
    """

    category = ReactiveChoiceField(
        label="Category",
        choices_from=get_categories,
        value_field="id",
        label_field="name",
        empty_choice="-- Select Category --",
    )

    product = ReactiveChoiceField(
        label="Product",
        choices_from=get_products_for_category,
        depends_on=["category"],
        value_field="id",
        label_template="{name} (${price})",
        empty_choice="-- Select Product --",
        empty_choice_no_parent="-- Select Category First --",
    )

    quantity = ReactiveIntegerField(
        label="Quantity",
        min_value=1,
        initial=1,
    )

    # Hidden field to store selected product's price (set by view on repopulate)
    unit_price = ReactiveDecimalField(
        widget=forms.HiddenInput(),
        required=False,
        initial=0,
    )

    def clean(self):
        """Validate that product belongs to selected category."""
        cleaned_data = super().clean()
        category_id = cleaned_data.get("category")
        product_id = cleaned_data.get("product")

        if product_id and category_id:
            product = get_product_by_id(product_id)
            if product and str(product["category_id"]) != str(category_id):
                self.add_error("product", "This product does not belong to the selected category.")

        return cleaned_data
