"""Security tests: signal seeding must not allow HTML attribute injection."""

import html
import json
import re

from django.forms import formset_factory
from django.template import Context, Template

from rg.forms import ReactiveCharField, ReactiveForm

# Values that would break out of a single-quoted attribute or inject markup.
_HOSTILE = "x' onfocus='alert(1)"
_HOSTILE_TAG = '</script><b>&"'


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
