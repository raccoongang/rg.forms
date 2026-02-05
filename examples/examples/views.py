"""Views for rg.forms examples.

Demonstrates how to use ReactiveForm with function-based views (FBV).
All reactive logic lives in the form class, not the view.
"""

from collections.abc import Generator

from datastar_py.django import DatastarResponse, ServerSentEventGenerator
from datastar_py.sse import DatastarEvent
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .forms import (
    BackendValidationForm,
    CascadingForm,
    ConditionalAttributesForm,
    ContactForm,
    FieldGroupsForm,
    OrderForm,
    PriceCalculatorForm,
    get_product_by_id,
)


def field_groups(request: HttpRequest) -> HttpResponse:
    """Example: Field Groups/Sections.

    Demonstrates organizing fields into logical groups:
    - Shared visibility rules (visible_when on group)
    - Visual grouping with labels and descriptions
    - Custom CSS classes for styling
    """
    if request.method == "POST":
        form = FieldGroupsForm(request.POST)
        if form.is_valid():
            pass  # Process form
    else:
        form = FieldGroupsForm()

    return render(request, "examples/field_groups.html", {"form": form})


def index(request: HttpRequest) -> HttpResponse:
    """Index page listing all examples."""
    return render(request, "examples/index.html")


def risks(request: HttpRequest) -> HttpResponse:
    """Risks and considerations page."""
    return render(request, "examples/risks.html")


def conditional_attributes(request: HttpRequest) -> HttpResponse:
    """Example: Conditional field attributes.

    Demonstrates:
    - disabled_when: conditionally disable fields
    - read_only_when: conditionally make fields read-only
    - help_text_when: dynamic help text
    """
    if request.method == "POST":
        form = ConditionalAttributesForm(request.POST)
        if form.is_valid():
            pass  # Process form
    else:
        form = ConditionalAttributesForm()

    return render(request, "examples/conditional_attributes.html", {"form": form})


def backend_validation(request: HttpRequest) -> HttpResponse:
    """Example: Backend expression evaluation.

    Demonstrates:
    - visible_when: hidden fields skipped in validation
    - required_when: dynamic requirements enforced
    - computed: values recalculated on server
    """
    success_message = None

    if request.method == "POST":
        form = BackendValidationForm(request.POST)
        if form.is_valid():
            success_message = {
                "order_type": form.cleaned_data["order_type"],
                "priority": form.cleaned_data.get("priority"),
                "bulk_discount_code": form.cleaned_data.get("bulk_discount_code"),
                "quantity": form.cleaned_data["quantity"],
                "unit_price": form.cleaned_data["unit_price"],
                "total": form.cleaned_data["total"],  # Computed on server!
            }
    else:
        form = BackendValidationForm()

    return render(
        request,
        "examples/backend_validation.html",
        {"form": form, "success_message": success_message},
    )


def order_form(request: HttpRequest) -> HttpResponse:
    """Example: Order form with visibility rules.

    Demonstrates visible_when attribute showing/hiding fields
    based on order_type selection.
    """
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            # Process form...
            pass
    else:
        form = OrderForm()

    return render(request, "examples/order_form.html", {"form": form})


def price_calculator(request: HttpRequest) -> HttpResponse:
    """Example: Price calculator with computed fields.

    Demonstrates computed attribute for automatic calculations.
    """
    if request.method == "POST":
        form = PriceCalculatorForm(request.POST)
        if form.is_valid():
            # Process form...
            pass
    else:
        form = PriceCalculatorForm()

    return render(request, "examples/price_calculator.html", {"form": form})


def contact_form(request: HttpRequest) -> HttpResponse:
    """Example: Contact form with dynamic requirements.

    Demonstrates required_when attribute for conditional field requirements.
    """
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            # Process form...
            pass
    else:
        form = ContactForm()

    return render(request, "examples/contact_form.html", {"form": form})


def cascading_form(request: HttpRequest) -> HttpResponse | DatastarResponse:
    """Example: Cascading/dependent dropdowns.

    Demonstrates server-side form re-rendering for dependent fields.
    When category changes, form is POSTed via Datastar and re-rendered
    with updated product choices (partial page update via SSE).
    """
    is_datastar = request.headers.get("Datastar-Request") == "true"

    if request.method == "POST":
        if is_datastar:
            # Repopulate request - create UNBOUND form with initial values
            # This avoids validation errors when fields change
            category_id = request.POST.get("category", "")
            product_id = request.POST.get("product", "")
            product = get_product_by_id(product_id) if product_id else None

            # Check if product is valid for current category
            product_valid = False
            if product and category_id:
                product_valid = str(product["category_id"]) == str(category_id)

            initial = {
                "category": category_id,
                "product": product_id if product_valid else "",
                "quantity": request.POST.get("quantity", 1),
                "unit_price": product["price"] if product_valid else 0,
            }
            form = CascadingForm(initial=initial)

            # Partial update - render just the form fragment and patch via SSE
            form_html = render_to_string(
                "examples/_cascading_form_fragment.html",
                {"form": form},
                request,
            )

            def form_updates() -> Generator[DatastarEvent, None, None]:
                yield ServerSentEventGenerator.patch_elements(form_html)

            return DatastarResponse(form_updates())

        # Regular form submission - bind and validate
        form = CascadingForm(request.POST)
        if form.is_valid():
            # Process form...
            pass
    else:
        form = CascadingForm()

    return render(request, "examples/cascading_form.html", {"form": form})
