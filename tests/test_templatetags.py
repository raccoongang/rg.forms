"""Tests for reactive_forms template tags."""

import pytest
from django import forms
from django.forms import formset_factory
from django.template import Context, Template

from rg.forms import (
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDateField,
    ReactiveDateTimeField,
    ReactiveEmailField,
    ReactiveForm,
    ReactiveIntegerField,
    ReactiveMultipleChoiceField,
    ReactiveURLField,
)
from rg.forms.templatetags.reactive_forms import render_reactive_field


class VisibilityForm(ReactiveForm):
    """Test form with visibility rules."""

    order_type = ReactiveChoiceField(
        choices=[("standard", "Standard"), ("urgent", "Urgent")]
    )
    priority = ReactiveCharField(
        visible_when="$order_type == 'urgent'",
        required=False,
    )


class ComputedForm(ReactiveForm):
    """Test form with computed field."""

    quantity = ReactiveCharField()
    price = ReactiveCharField()
    total = ReactiveCharField(
        computed="$quantity * $price",
        required=False,
    )


class RequiredWhenForm(ReactiveForm):
    """Test form with required_when."""

    contact_method = ReactiveChoiceField(choices=[("email", "Email"), ("phone", "Phone")])
    email = ReactiveCharField(
        required_when="$contact_method == 'email'",
        required=False,
    )


class TestReactiveWrapperAttrs:
    """Tests for reactive_wrapper_attrs tag."""

    def test_visible_when_generates_data_show(self):
        """visible_when should generate data-show attribute."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_wrapper_attrs form.priority %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        # Expressions are compiled to Datastar/JS before emission (ADR-0002):
        # typed equality -> ===, string literal -> double-quoted.
        assert 'data-show="($order_type === &quot;urgent&quot;)"' in result

    def test_no_visible_when_returns_empty(self):
        """Field without visible_when should return empty string."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_wrapper_attrs form.order_type %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == ""


class TestReactiveInputAttrs:
    """Tests for reactive_input_attrs tag."""

    def test_generates_data_bind(self):
        """Should generate data-bind for field signal (key-based syntax, no $ prefix)."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_input_attrs form.order_type %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        # Datastar uses data-bind:fieldname syntax (no $ prefix)
        assert "data-bind:order_type" in result

    def test_computed_generates_data_computed(self):
        """Computed field should generate data-computed and readonly."""
        form = ComputedForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_input_attrs form.total %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        # Compiled arithmetic keeps a guarded, numeric-only form (ADR-0002 §3).
        assert "data-computed=" in result
        assert "$quantity" in result
        assert "$price" in result
        assert "readonly" in result


class TestReactiveSignals:
    """Tests for reactive_signals tag."""

    def test_generates_json_signals(self):
        """Should generate JSON signals from form."""
        form = VisibilityForm(initial={"order_type": "urgent"})
        # Use single quotes for attribute since JSON uses double quotes
        template = Template(
            "{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert '"order_type": "urgent"' in result


class TestSignalNameFilter:
    """Tests for signal_name filter."""

    def test_converts_to_signal_reference(self):
        """Should convert field name to $-prefixed signal."""
        template = Template(
            '{% load reactive_forms %}{{ "my_field"|signal_name }}'
        )
        context = Context({})
        result = template.render(context)

        assert result == "$my_field"


class TestRequiredIndicator:
    """Tests for required_indicator tag."""

    def test_required_when_generates_data_show(self):
        """required_when should generate indicator with data-show."""
        form = RequiredWhenForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.email %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" in result
        # Check for the expression (may be HTML-encoded)
        assert "$contact_method" in result
        assert "email" in result

    def test_static_required_no_data_show(self):
        """Static required should generate indicator without data-show."""
        form = RequiredWhenForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.contact_method %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" not in result
        assert "*" in result

    def test_not_required_returns_empty(self):
        """Non-required field without required_when returns empty."""

        class OptionalForm(ReactiveForm):
            optional = ReactiveCharField(required=False)

        form = OptionalForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.optional %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == ""


class InputTypeForm(ReactiveForm):
    """Form exercising the widget-type -> input_type mapping."""

    name = ReactiveCharField(required=False)
    age = ReactiveIntegerField(required=False)
    email = ReactiveEmailField(required=False)
    website = ReactiveURLField(required=False)
    starts_at = ReactiveDateTimeField(required=False)


class PresentationalForm(ReactiveForm):
    """Form exercising first-class presentational kwargs."""

    plain = ReactiveCharField(
        required=False,
        placeholder="Type here",
        autocomplete="name",
        autofocus=True,
    )
    # Explicit kwarg must win over a value already on the widget's attrs.
    overridden = ReactiveCharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "from widget"}),
        placeholder="from kwarg",
    )


class TestInputType:
    """Tests for the input_type context key (P1)."""

    @pytest.mark.parametrize(
        ("field_name", "expected"),
        [
            ("name", "text"),
            ("age", "number"),
            ("email", "email"),
            ("website", "url"),
            ("starts_at", "datetime-local"),
        ],
    )
    def test_input_type_mapping(self, field_name, expected):
        form = InputTypeForm()
        ctx = render_reactive_field(form[field_name])
        assert ctx["input_type"] == expected
        # widget_type is preserved for branching.
        assert "widget_type" in ctx

    def test_datetime_local_renders_in_template(self):
        form = InputTypeForm()
        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.starts_at %}"
        )
        result = template.render(Context({"form": form}))
        assert 'type="datetime-local"' in result


class TestWidgetAttrs:
    """Tests for the widget_attrs context key and first-class kwargs (P2)."""

    def test_first_class_kwargs_surface_in_widget_attrs(self):
        form = PresentationalForm()
        ctx = render_reactive_field(form["plain"])
        assert ctx["widget_attrs"]["placeholder"] == "Type here"
        assert ctx["widget_attrs"]["autocomplete"] == "name"
        assert ctx["widget_attrs"]["autofocus"] is True

    def test_explicit_kwarg_overrides_widget_attrs(self):
        form = PresentationalForm()
        ctx = render_reactive_field(form["overridden"])
        assert ctx["widget_attrs"]["placeholder"] == "from kwarg"

    def test_widget_attrs_render_in_template(self):
        form = PresentationalForm()
        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.plain %}"
        )
        result = template.render(Context({"form": form}))
        assert 'placeholder="Type here"' in result
        assert 'autocomplete="name"' in result

    def test_managed_attrs_excluded(self):
        """Keys handled elsewhere (id/name/required/...) never leak into widget_attrs."""
        form = PresentationalForm()
        ctx = render_reactive_field(form["plain"])
        for managed in ("id", "name", "required", "maxlength"):
            assert managed not in ctx["widget_attrs"]


class RoleForm(ReactiveForm):
    """Simple form used inside a formset."""

    role = ReactiveCharField()


class TestFormsetNaming:
    """Tests for formset-safe name/id rendering and POST round-trip (P4)."""

    def test_prefixed_name_and_id(self):
        role_formset_cls = formset_factory(RoleForm, extra=2)
        formset = role_formset_cls()
        template = Template(
            "{% load reactive_forms %}"
            "{% for f in formset.forms %}{% render_reactive_field f.role %}{% endfor %}"
        )
        result = template.render(Context({"formset": formset}))

        # Prefixed, non-colliding submit names and ids.
        assert 'name="form-0-role"' in result
        assert 'name="form-1-role"' in result
        assert 'id="id_form-0-role"' in result
        assert 'id="id_form-1-role"' in result
        # The old, buggy unprefixed form must be gone.
        assert 'name="role"' not in result
        assert 'id="id_role"' not in result

    def test_post_round_trips(self):
        role_formset_cls = formset_factory(RoleForm, extra=2)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-role": "admin",
            "form-1-role": "editor",
        }
        formset = role_formset_cls(data)
        assert formset.is_valid(), formset.errors
        assert formset.forms[0].cleaned_data["role"] == "admin"
        assert formset.forms[1].cleaned_data["role"] == "editor"


class RequiredMatrixForm(ReactiveForm):
    """Covers the required_expr matrix (static/conditional x hideable)."""

    trigger = ReactiveChoiceField(
        choices=[("a", "A"), ("b", "B")], required=False
    )
    static_req = ReactiveCharField()  # unconditionally required
    static_req_hideable = ReactiveCharField(visible_when="$trigger == 'a'")
    cond_req = ReactiveCharField(required=False, required_when="$trigger == 'b'")
    cond_req_hideable = ReactiveCharField(
        required=False,
        visible_when="$trigger == 'a'",
        required_when="$trigger == 'b'",
    )
    optional = ReactiveCharField(required=False)


class TestRequiredExpr:
    """Tests for reactive required (P4 of the review / dynamic required)."""

    def test_static_required_no_expr(self):
        ctx = render_reactive_field(RequiredMatrixForm()["static_req"])
        assert ctx["required_expr"] is None  # -> template renders static `required`
        assert ctx["is_required"] is True

    def test_optional_no_expr(self):
        ctx = render_reactive_field(RequiredMatrixForm()["optional"])
        assert ctx["required_expr"] is None
        assert ctx["is_required"] is False

    def test_static_required_hideable_uses_visibility(self):
        ctx = render_reactive_field(RequiredMatrixForm()["static_req_hideable"])
        # Compiled (ADR-0002): typed equality, double-quoted string literal.
        assert ctx["required_expr"] == '($trigger === "a")'

    def test_required_when_only(self):
        ctx = render_reactive_field(RequiredMatrixForm()["cond_req"])
        assert ctx["required_expr"] == '($trigger === "b")'

    def test_required_when_and_visible_when_combined(self):
        ctx = render_reactive_field(RequiredMatrixForm()["cond_req_hideable"])
        # Boolean-coercing, boolean-returning && (never operand-returning).
        assert ctx["required_expr"] == (
            '(Boolean(($trigger === "a")) && Boolean(($trigger === "b")))'
        )

    def test_hidden_field_renders_data_attr_not_static_required(self):
        """A hideable required field must not emit a bare `required` that would
        block native submission while hidden."""
        form = RequiredMatrixForm()
        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.static_req_hideable %}"
        )
        result = template.render(Context({"form": form}))
        assert "data-attr:required=" in result
        # "required" appears exactly once (in data-attr:required) — no extra
        # standalone boolean `required` attribute that would block submission.
        assert result.count("required") == 1


class DynamicAttrsForm(ReactiveForm):
    """Covers placeholder_when / min_when / max_when wiring."""

    mode = ReactiveChoiceField(choices=[("x", "X"), ("y", "Y")], required=False)
    note = ReactiveCharField(
        required=False,
        placeholder_when={"$mode == 'x'": "Enter X", "$mode == 'y'": "Enter Y"},
    )
    qty = ReactiveIntegerField(
        required=False,
        min_when={"$mode == 'x'": 1},
        max_when={"$mode == 'x'": 10},
    )


class TestDynamicWhenExprs:
    """Tests for placeholder_when / min_when / max_when (review finding 5)."""

    def test_placeholder_expr_is_first_match_ternary(self):
        ctx = render_reactive_field(DynamicAttrsForm()["note"])
        # Right-associative ternary (first match wins) over compiled conditions.
        assert ctx["placeholder_expr"] == (
            '(($mode === "x")) ? "Enter X" : (($mode === "y")) ? "Enter Y" : \'\''
        )

    def test_min_max_exprs(self):
        ctx = render_reactive_field(DynamicAttrsForm()["qty"])
        assert ctx["min_expr"] == '(($mode === "x")) ? 1 : null'
        assert ctx["max_expr"] == '(($mode === "x")) ? 10 : null'

    def test_none_when_unset(self):
        ctx = render_reactive_field(RequiredMatrixForm()["optional"])
        assert ctx["placeholder_expr"] is None
        assert ctx["min_expr"] is None
        assert ctx["max_expr"] is None

    def test_placeholder_expr_renders_as_data_attr(self):
        form = DynamicAttrsForm()
        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.note %}"
        )
        result = template.render(Context({"form": form}))
        assert "data-attr:placeholder=" in result


class MultiChoiceForm(ReactiveForm):
    tags = ReactiveMultipleChoiceField(
        choices=[("a", "A"), ("b", "B"), ("c", "C")], required=False
    )


class RadioForm(ReactiveForm):
    color = ReactiveChoiceField(
        choices=[("r", "Red"), ("g", "Green")],
        widget=forms.RadioSelect,
        required=False,
    )


class DateForm(ReactiveForm):
    d = ReactiveDateField(required=False)


class TestWidgetCoverage:
    """Tests for selectmultiple + native fallback (review finding 2)."""

    def test_selectmultiple_renders_multiple_select(self):
        form = MultiChoiceForm()
        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.tags %}"
        )
        result = template.render(Context({"form": form}))
        assert "<select multiple" in result
        assert "data-bind:tags" in result
        assert '<option value="a"' in result

    def test_selectmultiple_not_simple_input(self):
        ctx = render_reactive_field(MultiChoiceForm()["tags"])
        assert ctx["is_simple_input"] is False
        assert ctx["widget_type"] == "selectmultiple"

    def test_unhandled_widget_falls_back_to_native(self):
        form = RadioForm()
        ctx = render_reactive_field(form["color"])
        assert ctx["is_simple_input"] is False

        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.color %}"
        )
        result = template.render(Context({"form": form}))
        # Django's native radio rendering, not our generic text input.
        assert 'type="radio"' in result
        assert 'type="text"' not in result
        # Native fallback does not apply reactive data-bind.
        assert "data-bind:color" not in result


class TestFormattedValue:
    """formatted_value (not field.value) must be rendered (review finding 1)."""

    def test_date_input_renders_formatted_value(self):
        from datetime import date

        form = DateForm(initial={"d": date(2025, 6, 15)})
        ctx = render_reactive_field(form["d"])
        assert ctx["formatted_value"] == "2025-06-15"

        template = Template(
            "{% load reactive_forms %}{% render_reactive_field form.d %}"
        )
        result = template.render(Context({"form": form}))
        assert 'value="2025-06-15"' in result


class TestFormMethods:
    """Tests for ReactiveForm helper methods."""

    def test_get_field_reactive_attrs(self):
        """get_field_reactive_attrs should return field's reactive attributes."""
        form = VisibilityForm()
        attrs = form.get_field_reactive_attrs("priority")

        assert attrs["visible_when"] == "$order_type == 'urgent'"

    def test_get_visible_fields(self):
        """get_visible_fields should return fields with visibility rules."""
        form = VisibilityForm()
        visible_fields = form.get_visible_fields()

        assert "priority" in visible_fields
        assert "order_type" not in visible_fields

    def test_get_computed_fields(self):
        """get_computed_fields should return computed field names."""
        form = ComputedForm()
        computed_fields = form.get_computed_fields()

        assert "total" in computed_fields
        assert "quantity" not in computed_fields
