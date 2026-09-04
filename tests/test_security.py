"""Security tests: signal seeding must not allow HTML attribute injection."""

import html
import json
import re

from django import forms
from django.forms import formset_factory
from django.template import Context, Template

from rg.forms import ReactiveCharField, ReactiveForm
from rg.forms.templatetags.reactive_forms import reactive_formset_signals, render_reactive_field

# Values that would break out of a single-quoted attribute or inject markup.
_HOSTILE = "x' onfocus='alert(1)"
_HOSTILE_TAG = '</script><b>&"'
# A password value distinctive enough that a substring check is unambiguous.
_SECRET = "hunter2-SUPERSECRET"


class InjectForm(ReactiveForm):
    name = ReactiveCharField(required=False)
    note = ReactiveCharField(required=False)


def _attr_value(rendered: str) -> str:
    """Extract the single-quoted data-signals attribute value."""
    m = re.search(r"data-signals='([^']*)'", rendered)
    assert m, f"no single-quoted data-signals found in: {rendered}"
    return m.group(1)


class TestReactiveSignalsInjection:
    def test_apostrophe_cannot_break_out(self):
        form = InjectForm(initial={"name": _HOSTILE, "note": _HOSTILE_TAG})
        rendered = Template("{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>").render(
            Context({"form": form})
        )

        value = _attr_value(rendered)
        # No raw apostrophe survived inside the attribute (would break out).
        assert "'" not in value
        # No raw markup-opening survived.
        assert "<" not in value and ">" not in value
        # Round-trips: browser-decoded value is exactly the seeded signals.
        decoded = html.unescape(value)
        assert json.loads(decoded) == {"name": _HOSTILE, "note": _HOSTILE_TAG}

    def test_readable_json_double_quotes_preserved(self):
        """Double quotes stay literal so JSON is readable in the (single-quoted) attr."""
        form = InjectForm(initial={"name": "ok"})
        rendered = Template("{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>").render(
            Context({"form": form})
        )
        assert '"name": "ok"' in rendered


class TestFormsetSignalsInjection:
    def test_formset_seed_is_escaped(self):
        formset = formset_factory(InjectForm, extra=1)(
            initial=[{"name": _HOSTILE}],
        )
        rendered = Template(
            "{% load reactive_forms %}<form data-signals='{% reactive_formset_signals formset %}'>"
        ).render(Context({"formset": formset}))

        value = _attr_value(rendered)
        assert "'" not in value
        decoded = html.unescape(value)
        parsed = json.loads(decoded)
        # The hostile value is nested under the row scope but preserved verbatim.
        assert _HOSTILE in json.dumps(parsed)


class PasswordForm(ReactiveForm):
    secret = ReactiveCharField(label="Secret", widget=forms.PasswordInput())


class RenderValuePasswordForm(ReactiveForm):
    """PasswordInput with the opt-in that makes the round-trip explicit."""

    secret = ReactiveCharField(label="Secret", widget=forms.PasswordInput(render_value=True))


class TestPasswordValueNotEchoed:
    """A PasswordInput must not round-trip the submitted value into the HTML."""

    def test_submitted_password_absent_from_rendered_field(self):
        form = PasswordForm(data={"secret": _SECRET})
        rendered = Template("{% load reactive_forms %}{% render_reactive_field form.secret %}").render(
            Context({"form": form})
        )

        assert 'type="password"' in rendered
        assert _SECRET not in rendered
        assert 'value=""' in rendered

    def test_formatted_value_is_suppressed_in_the_context(self):
        """The suppression lives in the context, so template overrides inherit it."""
        form = PasswordForm(data={"secret": _SECRET})
        context = render_reactive_field(form["secret"])

        assert context["formatted_value"] in (None, "")

    def test_render_value_true_still_round_trips(self):
        """Explicit ``render_value=True`` keeps Django's documented opt-in behavior."""
        form = RenderValuePasswordForm(data={"secret": _SECRET})
        context = render_reactive_field(form["secret"])

        assert context["formatted_value"] == _SECRET


class GatedPasswordForm(ReactiveForm):
    """A rule that legitimately reads the secret server-side."""

    secret = ReactiveCharField(required=False, widget=forms.PasswordInput())
    confirm = ReactiveCharField(required=False, required_when="$secret")


class TestPasswordNotSeededIntoSignals:
    """A PasswordInput must not reach the client through ``data-signals`` either.

    ``data-bind`` writes every signal back onto its input, so a seeded secret is
    the same leak as a rendered ``value`` attribute, one indirection later.
    """

    def test_bound_password_seeds_empty(self):
        form = PasswordForm(data={"secret": _SECRET})

        assert form.get_client_signals() == {"secret": ""}
        assert form.get_seed_signals() == {"secret": ""}

    def test_secret_absent_from_the_data_signals_attribute(self):
        form = PasswordForm(data={"secret": _SECRET})
        rendered = Template("{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>").render(
            Context({"form": form})
        )

        assert _SECRET not in rendered
        assert json.loads(html.unescape(_attr_value(rendered))) == {"secret": ""}

    def test_other_fields_on_the_same_form_still_seed(self):
        """Suppression is per-field: only the write-only widget is blanked."""
        form = GatedPasswordForm(data={"secret": _SECRET, "confirm": "typed"})

        assert form.get_client_signals() == {"secret": "", "confirm": "typed"}

    def test_initial_password_is_suppressed_too(self):
        """Unbound is not a safe case — ``initial`` can carry a stored secret."""
        form = PasswordForm(initial={"secret": _SECRET})

        assert form.get_client_signals() == {"secret": ""}
        assert _SECRET not in form.get_signals_json()

    def test_render_value_true_still_seeds_the_value(self):
        """``render_value=True`` is Django's documented opt-in and keeps working."""
        form = RenderValuePasswordForm(data={"secret": _SECRET})

        assert form.get_client_signals() == {"secret": _SECRET}
        assert _SECRET in form.get_signals_json()

    def test_scoped_seed_is_suppressed(self):
        """The nested ``rgForms.<scope>`` seed goes through the same path."""

        class ScopedPasswordForm(PasswordForm):
            reactive_scope = "acct"

        form = ScopedPasswordForm(data={"secret": _SECRET})

        assert form.get_seed_signals() == {"rgForms": {"acct": {"secret": ""}}}
        assert _SECRET not in form.get_signals_json()

    def test_formset_seed_is_suppressed(self):
        """The formset tag merges rows itself, so it must suppress them itself."""
        formset = formset_factory(PasswordForm, extra=1)(
            data={
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-0-secret": _SECRET,
            }
        )

        seed = reactive_formset_signals(formset)

        assert _SECRET not in seed

    def test_whole_form_render_leaks_nowhere(self):
        """End to end: neither the seed attribute nor the input carries it."""
        form = PasswordForm(data={"secret": _SECRET})
        rendered = Template(
            "{% load reactive_forms %}"
            "<form data-signals='{% reactive_signals form %}'>{% render_reactive_field form.secret %}</form>"
        ).render(Context({"form": form}))

        assert _SECRET not in rendered


class TestPasswordStillReachesServerSideRules:
    """The regression guard that matters most: only the *client* copy is blanked.

    ``visible_when`` / ``required_when`` are evaluated server-side against
    ``_get_form_data()``. Blanking a secret there would silently disable a rule
    that gates on whether it was supplied, so the two dicts diverge on purpose.
    """

    def test_get_signals_keeps_the_real_value(self):
        form = PasswordForm(data={"secret": _SECRET})

        assert form.get_signals() == {"secret": _SECRET}

    def test_form_data_keeps_the_real_value(self):
        form = PasswordForm(data={"secret": _SECRET})

        assert form._get_form_data()["secret"] == _SECRET

    def test_required_when_gated_on_a_secret_still_fires(self):
        """The end-to-end rule, not just the dict it reads."""
        form = GatedPasswordForm(data={"secret": _SECRET, "confirm": ""})

        assert form.is_field_required("confirm") is True
        assert not form.is_valid()
        assert "confirm" in form.errors

    def test_the_same_rule_stays_off_when_no_secret_was_supplied(self):
        form = GatedPasswordForm(data={"secret": "", "confirm": ""})

        assert form.is_field_required("confirm") is False
        assert form.is_valid()


class TestWidgetAttrsReachTheDom:
    """``widget.attrs`` is rendered on every dispatch branch of ``field.html``.

    Attaching ``aria-*`` through ``widget.attrs`` is the ordinary Django way to
    mark up an errored control; silently dropping it would be a trap.
    """

    def test_attrs_on_a_text_input_are_rendered(self):
        class AttrsForm(ReactiveForm):
            name = ReactiveCharField(widget=forms.TextInput(attrs={"aria-invalid": "true", "data-testid": "name"}))

        form = AttrsForm(data={"name": ""})
        rendered = Template("{% load reactive_forms %}{% render_reactive_field form.name %}").render(
            Context({"form": form})
        )

        assert 'aria-invalid="true"' in rendered
        assert 'data-testid="name"' in rendered

    def test_attrs_on_a_textarea_are_rendered(self):
        class AreaForm(ReactiveForm):
            note = ReactiveCharField(widget=forms.Textarea(attrs={"aria-describedby": "note-help"}))

        form = AreaForm(data={"note": ""})
        rendered = Template("{% load reactive_forms %}{% render_reactive_field form.note %}").render(
            Context({"form": form})
        )

        assert 'aria-describedby="note-help"' in rendered
