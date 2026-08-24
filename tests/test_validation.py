"""Tests for declarative incremental server validation (ADR-0004)."""

import json
import re

import pytest
from django.template import Context, Template
from django.test import Client

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveForm,
    ReactiveMultipleChoiceField,
)
from rg.forms.adapters import signals_to_querydict
from rg.forms.scoping import encode_scope
from rg.forms.templatetags.reactive_forms import (
    append_field_discriminator,
    control_ids,
)
from rg.forms.views import resolve_validate_field


class ValFieldsForm(ReactiveForm):
    username = ReactiveCharField(validate_on="blur")
    coupon = ReactiveCharField(required=False, validate_on="change", debounce=400)
    plain = ReactiveCharField(required=False)


def _render_field(bound_field, **kwargs):
    return Template(
        "{% load reactive_forms %}{% render_reactive_field bf " + " ".join(f"{k}={k}" for k in kwargs) + " %}"
    ).render(Context({"bf": bound_field, **kwargs}))


class TestValidateHandlerRendering:
    def test_blur_emits_json_signal_request_not_form(self):
        form = ValFieldsForm()
        out = _render_field(form["username"], validate_action="/validate/", csrf_token="TOK")
        assert "data-on:blur=" in out
        # JSON-signal request (default), NOT contentType:'form'
        assert "contentType" not in out
        assert "__rg_field=username" in out
        assert "X-CSRFToken" in out
        assert "X-RG-Validate-Field" in out

    def test_change_uses_debounce(self):
        form = ValFieldsForm()
        out = _render_field(form["coupon"], validate_action="/validate/", csrf_token="TOK")
        assert "data-on:change__debounce.400ms=" in out

    def test_pending_indicator_is_local_nested_signal(self):
        form = ValFieldsForm()
        out = _render_field(form["username"], validate_action="/validate/", csrf_token="TOK")
        assert 'data-indicator="_rgForms.validating.username"' in out

    def test_two_fields_hit_distinct_urls(self):
        form = ValFieldsForm()
        u = _render_field(form["username"], validate_action="/validate/", csrf_token="TOK")
        c = _render_field(form["coupon"], validate_action="/validate/", csrf_token="TOK")
        assert "__rg_field=username" in u
        assert "__rg_field=coupon" in c

    def test_no_validate_on_is_unchanged(self):
        form = ValFieldsForm()
        out = _render_field(form["plain"], validate_action="/validate/", csrf_token="TOK")
        assert "data-on:blur" not in out
        assert "data-on:change" not in out
        assert "data-indicator" not in out

    def test_scoped_field_path_in_handler(self):
        form = ValFieldsForm(prefix="form-0")
        out = _render_field(form["username"], validate_action="/validate/", csrf_token="TOK")
        scope = encode_scope("form-0")
        assert f"__rg_field=rgForms.{scope}.username" in out
        assert f"_rgForms.{scope}.validating.username" in out


class TestValidateActionResolution:
    def test_missing_action_raises_config_error(self):
        from django.core.exceptions import ImproperlyConfigured

        form = ValFieldsForm()
        with pytest.raises(ImproperlyConfigured):
            _render_field(form["username"], validate_action=None)


class TestDiscriminatorURL:
    def test_appends_to_empty_url(self):
        assert append_field_discriminator("", "username") == "?__rg_field=username"

    def test_preserves_existing_query_and_fragment(self):
        out = append_field_discriminator("/v/?a=1#frag", "username")
        assert out == "/v/?a=1&__rg_field=username#frag"


class TestControlIds:
    def test_default_auto_id(self):
        ids = control_ids(ValFieldsForm()["username"])
        assert ids["control_id"] == "id_username"
        assert ids["wrapper_id"] == "id_username_field"
        assert ids["error_id"] == "id_username_error"

    def test_empty_id_fallback_for_incremental_field(self):
        form = ValFieldsForm(auto_id=False)
        ids = control_ids(form["username"])
        # validate_on set + empty id_for_label -> injective fallback id
        assert ids["control_id"].startswith("rg_field_")
        assert ids["wrapper_id"].endswith("_field")

    def test_no_fallback_for_non_incremental_field(self):
        form = ValFieldsForm(auto_id=False)
        ids = control_ids(form["plain"])
        # non-incremental + auto_id=False -> unchanged (no id)
        assert ids["control_id"] == ""
        assert ids["wrapper_id"] == ""


class AdapterForm(ReactiveForm):
    name = ReactiveCharField(required=False)
    agree = ReactiveBooleanField(required=False)
    tags = ReactiveMultipleChoiceField(choices=[("a", "A"), ("b", "B"), ("c", "C")], required=False)


class TestAdapter:
    def test_round_trips_scalars_bools_arrays_null(self):
        form = AdapterForm()
        signals = {"name": "Ann", "agree": True, "tags": ["a", "c"]}
        qd = signals_to_querydict(form, signals)
        assert qd["name"] == "Ann"
        assert qd["agree"] == "on"
        assert qd.getlist("tags") == ["a", "c"]

    def test_false_boolean_is_absent(self):
        form = AdapterForm()
        qd = signals_to_querydict(form, {"agree": False})
        assert "agree" not in qd

    def test_null_becomes_empty(self):
        form = AdapterForm()
        qd = signals_to_querydict(form, {"name": None})
        assert qd["name"] == ""

    def test_scoped_paths_read_only_own_scope(self):
        form = AdapterForm(prefix="form-0")
        scope = encode_scope("form-0")
        other = encode_scope("form-9")
        signals = {"rgForms": {scope: {"name": "Mine"}, other: {"name": "NotMine"}}}
        qd = signals_to_querydict(form, signals)
        # Keyed by prefixed HTML name, only this form's scope is read.
        assert qd["form-0-name"] == "Mine"
        assert "NotMine" not in qd.urlencode()

    def test_rejects_scope_not_belonging_via_resolve(self):
        form = AdapterForm(prefix="form-0")
        other = encode_scope("form-9")
        # A trigger path for a different scope must not resolve.
        assert resolve_validate_field(form, f"rgForms.{other}.name") is None


class TestResolveValidateField:
    def test_unknown_field(self):
        assert resolve_validate_field(ValFieldsForm(), "nope") is None

    def test_field_without_validate_on(self):
        assert resolve_validate_field(ValFieldsForm(), "plain") is None

    def test_valid_field(self):
        assert resolve_validate_field(ValFieldsForm(), "username") == "username"

    def test_malformed_scoped_path_with_extra_components_is_rejected(self):
        """Reviewer hardening: only exactly rgForms.<scope>.<name> resolves."""
        form = ValFieldsForm(prefix="form-0")
        scope = encode_scope("form-0")
        assert resolve_validate_field(form, f"rgForms.{scope}.username.injected") is None
        # The well-formed scoped path still resolves.
        assert resolve_validate_field(form, f"rgForms.{scope}.username") == "username"


class TestJsStringEncoding:
    """Reviewer hardening: proper JS-string encoding (no hand-built quoting)."""

    def test_escapes_line_separators_and_quotes(self):
        from rg.forms.templatetags.reactive_forms import _js_str

        assert _js_str("a b") == '"a\\u2028b"'
        assert _js_str("a b") == '"a\\u2029b"'
        assert _js_str("a'b\"c") == '"a\'b\\"c"'
        assert _js_str("line\nbreak") == '"line\\nbreak"'


@pytest.mark.django_db
class TestCsrfEnforcedFlow:
    """Integration through a CSRF-enforced view (tests/urls.py)."""

    def _masked_token(self, client):
        resp = client.get("/page/")
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.content.decode())
        assert match, "csrf token not found on page"
        return match.group(1)

    def test_valid_value_passes_csrf_and_patches_only_field(self):
        client = Client(enforce_csrf_checks=True)
        token = self._masked_token(client)
        resp = client.post(
            "/validate/?__rg_field=username",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            HTTP_DATASTAR_REQUEST="true",
            HTTP_X_CSRFTOKEN=token,
            HTTP_X_RG_VALIDATE_FIELD="username",
        )
        assert resp.status_code == 200
        body = b"".join(resp.streaming_content).decode()
        assert "id_username_field" in body  # patched this field's wrapper
        assert "id_other_field" not in body  # unrelated field untouched

    def test_invalid_value_patches_error(self):
        client = Client(enforce_csrf_checks=True)
        token = self._masked_token(client)
        resp = client.post(
            "/validate/?__rg_field=username",
            data=json.dumps({"username": "taken"}),
            content_type="application/json",
            HTTP_DATASTAR_REQUEST="true",
            HTTP_X_CSRFTOKEN=token,
            HTTP_X_RG_VALIDATE_FIELD="username",
        )
        assert resp.status_code == 200
        body = b"".join(resp.streaming_content).decode()
        assert "taken" in body
        assert 'aria-invalid="true"' in body

    def test_missing_csrf_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        self._masked_token(client)
        resp = client.post(
            "/validate/?__rg_field=username",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            HTTP_DATASTAR_REQUEST="true",
            HTTP_X_RG_VALIDATE_FIELD="username",
        )
        assert resp.status_code == 403  # CsrfViewMiddleware rejects

    def test_header_url_mismatch_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        token = self._masked_token(client)
        resp = client.post(
            "/validate/?__rg_field=other",  # discriminator disagrees with header
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            HTTP_DATASTAR_REQUEST="true",
            HTTP_X_CSRFTOKEN=token,
            HTTP_X_RG_VALIDATE_FIELD="username",
        )
        assert resp.status_code == 400
