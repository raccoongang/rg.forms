"""Tests for reactive_forms template tags."""

from pathlib import Path

import pytest
from django import forms
from django.conf import settings
from django.forms import formset_factory
from django.template import Context, Template
from django.test import override_settings

from rg.forms import (
    FieldGroup,
    ReactiveBooleanField,
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

_OVERRIDE_DIR = Path(__file__).resolve().parent / "templates_override"


def _override_indicator_template():
    """Put a consumer's template dir ahead of the app loader for one block."""
    engine = settings.TEMPLATES[0]
    return override_settings(TEMPLATES=[{**engine, "DIRS": [_OVERRIDE_DIR, *engine["DIRS"]]}])


class VisibilityForm(ReactiveForm):
    """Test form with visibility rules."""

    order_type = ReactiveChoiceField(choices=[("standard", "Standard"), ("urgent", "Urgent")])
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
        template = Template("{% load reactive_forms %}{% reactive_wrapper_attrs form.priority %}")
        context = Context({"form": form})
        result = template.render(context)

        # Expressions are compiled to Datastar/JS before emission (ADR-0002):
        # typed equality -> ===, string literal -> double-quoted.
        assert 'data-show="($order_type === &quot;urgent&quot;)"' in result

    def test_no_visible_when_returns_empty(self):
        """Field without visible_when should return empty string."""
        form = VisibilityForm()
        template = Template("{% load reactive_forms %}{% reactive_wrapper_attrs form.order_type %}")
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == ""


class TestReactiveInputAttrs:
    """Tests for reactive_input_attrs tag."""

    def test_generates_data_bind(self):
        """Should generate data-bind for field signal (key-based syntax, no $ prefix)."""
        form = VisibilityForm()
        template = Template("{% load reactive_forms %}{% reactive_input_attrs form.order_type %}")
        context = Context({"form": form})
        result = template.render(context)

        # Datastar uses data-bind:fieldname syntax (no $ prefix)
        assert "data-bind:order_type" in result

    def test_computed_field_emits_no_data_computed(self):
        """A key-less data-computed is a silent no-op, and fights data-bind.

        ``data-computed`` declares a derived signal; it never writes an element
        value. The tag must not emit it — computed fields are rendered as
        display-only markup (``data-text``) by field.html instead.
        """
        form = ComputedForm()
        template = Template("{% load reactive_forms %}{% reactive_input_attrs form.total %}")
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == "data-bind:total"
        assert "data-computed" not in result
        assert "readonly" not in result


class TestReactiveSignals:
    """Tests for reactive_signals tag."""

    def test_generates_json_signals(self):
        """Should generate JSON signals from form."""
        form = VisibilityForm(initial={"order_type": "urgent"})
        # Use single quotes for attribute since JSON uses double quotes
        template = Template("{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>")
        context = Context({"form": form})
        result = template.render(context)

        assert '"order_type": "urgent"' in result


class TestSignalNameFilter:
    """Tests for signal_name filter."""

    def test_converts_to_signal_reference(self):
        """Should convert field name to $-prefixed signal."""
        template = Template('{% load reactive_forms %}{{ "my_field"|signal_name }}')
        context = Context({})
        result = template.render(context)

        assert result == "$my_field"


class TestRequiredIndicator:
    """Tests for required_indicator tag."""

    def test_required_when_generates_data_show(self):
        """required_when should generate indicator with data-show."""
        form = RequiredWhenForm()
        template = Template("{% load reactive_forms %}{% required_indicator form.email %}")
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" in result
        # Check for the expression (may be HTML-encoded)
        assert "$contact_method" in result
        assert "email" in result

    def test_static_required_no_data_show(self):
        """Static required should generate indicator without data-show."""
        form = RequiredWhenForm()
        template = Template("{% load reactive_forms %}{% required_indicator form.contact_method %}")
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" not in result
        assert "*" in result

    def test_not_required_returns_empty(self):
        """Non-required field without required_when returns empty."""

        class OptionalForm(ReactiveForm):
            optional = ReactiveCharField(required=False)

        form = OptionalForm()
        template = Template("{% load reactive_forms %}{% required_indicator form.optional %}")
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
        template = Template("{% load reactive_forms %}{% render_reactive_field form.starts_at %}")
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
        template = Template("{% load reactive_forms %}{% render_reactive_field form.plain %}")
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
            "{% load reactive_forms %}{% for f in formset.forms %}{% render_reactive_field f.role %}{% endfor %}"
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

    trigger = ReactiveChoiceField(choices=[("a", "A"), ("b", "B")], required=False)
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
        assert ctx["required_expr"] == ('(Boolean(($trigger === "a")) && Boolean(($trigger === "b")))')

    def test_hidden_field_renders_data_attr_not_static_required(self):
        """A hideable required field must not emit a bare `required` that would
        block native submission while hidden."""
        form = RequiredMatrixForm()
        template = Template("{% load reactive_forms %}{% render_reactive_field form.static_req_hideable %}")
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
        assert ctx["placeholder_expr"] == ('(($mode === "x")) ? "Enter X" : (($mode === "y")) ? "Enter Y" : \'\'')

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
        template = Template("{% load reactive_forms %}{% render_reactive_field form.note %}")
        result = template.render(Context({"form": form}))
        assert "data-attr:placeholder=" in result


class MultiChoiceForm(ReactiveForm):
    tags = ReactiveMultipleChoiceField(choices=[("a", "A"), ("b", "B"), ("c", "C")], required=False)


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
        template = Template("{% load reactive_forms %}{% render_reactive_field form.tags %}")
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

        template = Template("{% load reactive_forms %}{% render_reactive_field form.color %}")
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

        template = Template("{% load reactive_forms %}{% render_reactive_field form.d %}")
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


class ComputedWidgetForm(ReactiveForm):
    """Computed fields keep the widget they were declared with."""

    a = ReactiveCharField(required=False)
    b = ReactiveCharField(required=False)
    computed_select = ReactiveChoiceField(
        choices=[("x", "X"), ("y", "Y")],
        required=False,
        computed="$a * $b",
    )
    computed_textarea = ReactiveCharField(
        required=False,
        computed="$a * $b",
        widget=forms.Textarea(),
    )
    computed_checkbox = ReactiveBooleanField(required=False, computed="$a * $b")
    computed_text = ReactiveCharField(required=False, computed="$a * $b")


def _render_field(form, field_name):
    return Template("{% load reactive_forms %}{% render_reactive_field form." + field_name + " %}").render(
        Context({"form": form})
    )


class TestComputedBranchWinsOverWidgetType:
    """A computed field is display-only whatever widget it carries."""

    @pytest.mark.parametrize(
        "field_name,widget_tag",
        [
            ("computed_select", "<select"),
            ("computed_textarea", "<textarea"),
            ("computed_checkbox", 'type="checkbox"'),
            ("computed_text", 'type="text"'),
        ],
    )
    def test_computed_renders_a_data_text_span_not_the_widget(self, field_name, widget_tag):
        rendered = _render_field(ComputedWidgetForm(), field_name)

        assert "data-text=" in rendered
        assert widget_tag not in rendered

    def test_computed_span_carries_no_data_bind(self):
        """A display-only span must not also be a writer for the signal."""
        rendered = _render_field(ComputedWidgetForm(), "computed_select")

        assert "data-bind" not in rendered

    def test_computed_label_has_no_dangling_for(self):
        """A <span> is not labelable, so the label must not point at it."""
        rendered = _render_field(ComputedWidgetForm(), "computed_text")

        assert "<label" in rendered
        assert "for=" not in rendered


class CheckboxForm(ReactiveForm):
    mode = ReactiveCharField(required=False)
    agree = ReactiveBooleanField(label="I agree to the terms")
    subscribe = ReactiveBooleanField(
        label="Subscribe",
        required=False,
        required_when="$mode == 'newsletter'",
    )


class TestCheckboxLabelIsNotDuplicated:
    """The checkbox branch wraps its own label; the outer one must be skipped."""

    def test_label_text_appears_once(self):
        rendered = _render_field(CheckboxForm(), "agree")

        assert rendered.count("I agree to the terms") == 1
        assert rendered.count("<label") == 1

    def test_static_required_indicator_survives_on_the_wrapping_label(self):
        rendered = _render_field(CheckboxForm(), "agree")

        assert "has-text-danger" in rendered
        assert "data-show=" not in rendered

    def test_required_when_indicator_survives_on_the_wrapping_label(self):
        rendered = _render_field(CheckboxForm(), "subscribe")

        assert rendered.count("Subscribe") == 1
        assert 'class="has-text-danger" data-show=' in rendered

    def test_non_checkbox_widgets_keep_their_outer_label(self):
        rendered = _render_field(CheckboxForm(), "mode")

        assert rendered.count("<label") == 1
        assert 'for="id_mode"' in rendered


class TestRequiredIndicatorIsOverridable:
    """The indicator markup lives in a template, not in Python."""

    @pytest.mark.parametrize(
        "field_name,expects_data_show",
        [("contact_method", False), ("email", True)],
    )
    def test_a_consumer_override_replaces_the_markup(self, field_name, expects_data_show):
        """Both the static and the required_when arm come from the template."""
        form = RequiredWhenForm()
        source = "{% load reactive_forms %}{% required_indicator form." + field_name + " %}"

        # The Template must be built inside the override: an inclusion tag
        # resolves its template through the engine that compiled the caller.
        with _override_indicator_template():
            result = Template(source).render(Context({"form": form}))

        assert "my-ds-required" in result
        assert "has-text-danger" not in result
        assert ("data-show=" in result) is expects_data_show

    def test_no_presentation_class_is_hardcoded_in_python(self):
        import inspect

        from rg.forms.templatetags import reactive_forms

        source = inspect.getsource(reactive_forms)

        assert "has-text-danger" not in source


class InitialVisibilityForm(ReactiveForm):
    """Server-rendered initial visibility (the flash-of-visible fix)."""

    enabled = ReactiveBooleanField(required=False)
    client_id = ReactiveCharField(required=False, visible_when="$enabled")
    always = ReactiveCharField(required=False)

    class Meta:
        field_groups = {
            "config": FieldGroup(fields=["client_id"], label="Config", visible_when="$enabled"),
            "plain": FieldGroup(fields=["always"], label="Always"),
        }


class TestInitiallyHidden:
    """`initially_hidden` — the server's answer to what data-show does later."""

    def test_true_when_the_rule_is_already_false(self):
        form = InitialVisibilityForm(data={})
        assert render_reactive_field(form["client_id"])["initially_hidden"] is True

    def test_false_when_the_rule_is_already_true(self):
        form = InitialVisibilityForm(data={"enabled": "on"})
        assert render_reactive_field(form["client_id"])["initially_hidden"] is False

    def test_false_for_a_field_with_no_rule(self):
        form = InitialVisibilityForm(data={})
        assert render_reactive_field(form["always"])["initially_hidden"] is False

    def test_unbound_form_uses_initial(self):
        assert render_reactive_field(InitialVisibilityForm()["client_id"])["initially_hidden"] is True
        assert (
            render_reactive_field(InitialVisibilityForm(initial={"enabled": True})["client_id"])["initially_hidden"]
            is False
        )

    def test_a_non_reactive_form_is_never_reported_hidden(self):
        """The tag must stay usable on a plain Django form."""

        class Plain(forms.Form):
            name = forms.CharField()

        assert render_reactive_field(Plain()["name"])["initially_hidden"] is False

    def test_visible_when_is_still_emitted_alongside(self):
        """The client rule must survive: the server state is only the first paint."""
        context = render_reactive_field(InitialVisibilityForm(data={})["client_id"])
        assert context["visible_when"] == "$enabled"
        assert context["initially_hidden"] is True

    def test_shipped_template_hides_the_wrapper(self):
        template = Template("{% load reactive_forms %}{% render_reactive_field form.client_id %}")
        hidden = template.render(Context({"form": InitialVisibilityForm(data={})}))
        shown = template.render(Context({"form": InitialVisibilityForm(data={"enabled": "on"})}))

        assert 'style="display: none"' in hidden
        assert 'data-show="$enabled"' in hidden
        assert 'style="display: none"' not in shown

    def test_shipped_template_leaves_an_unruled_field_alone(self):
        template = Template("{% load reactive_forms %}{% render_reactive_field form.always %}")
        assert 'style="display: none"' not in template.render(Context({"form": InitialVisibilityForm(data={})}))


class TestGroupInitiallyHidden:
    def test_group_with_a_false_rule_renders_hidden(self):
        template = Template('{% load reactive_forms %}{% render_field_group form "config" %}')
        hidden = template.render(Context({"form": InitialVisibilityForm(data={})}))
        shown = template.render(Context({"form": InitialVisibilityForm(data={"enabled": "on"})}))

        assert 'style="display: none"' in hidden
        assert 'data-show="$enabled"' in hidden
        assert 'style="display: none"' not in shown

    def test_group_without_a_rule_is_never_hidden(self):
        template = Template('{% load reactive_forms %}{% render_field_group form "plain" %}')
        assert 'style="display: none"' not in template.render(Context({"form": InitialVisibilityForm(data={})}))

    def test_fields_inside_a_hidden_group_carry_their_own_state(self):
        """The group hides the fieldset; each field still answers for itself."""
        template = Template('{% load reactive_forms %}{% render_field_group form "config" %}')
        html = template.render(Context({"form": InitialVisibilityForm(data={})}))
        assert html.count('style="display: none"') == 2
