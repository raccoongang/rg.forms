"""Tests for multi-form reactive submission (ADR-0005 ``reactive_forms_response``)."""

from __future__ import annotations

import django.forms as djforms
import pytest
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory

from rg.forms import reactive_forms_response
from rg.forms.views import DatastarResponse

FRAGMENT = "_multi_form.html"


class AlphaForm(djforms.Form):
    name = djforms.CharField()  # required


class BetaForm(djforms.Form):
    code = djforms.CharField()  # required


class RowForm(djforms.Form):
    # max_length lets an over-long (non-empty) value be genuinely invalid — a row
    # whose only field is left blank is treated as an empty extra form and skipped.
    title = djforms.CharField(max_length=3)


RowFormSet = formset_factory(RowForm, extra=0)


def _datastar_post():
    return RequestFactory().post("/create/", HTTP_DATASTAR_REQUEST="true")


def _native_post():
    return RequestFactory().post("/create/")


def _sse_body(response: DatastarResponse) -> str:
    return b"".join(response.streaming_content).decode()


def _formset(rows):
    """Build a bound formset from a list of ``{"title": ...}`` row dicts."""
    data = {
        "form-TOTAL_FORMS": str(len(rows)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for key, value in row.items():
            data[f"form-{i}-{key}"] = value
    return RowFormSet(data)


def _ctx(alpha, beta, **extra):
    return {"marker": "CTX-OK", "alpha_form": alpha, "beta_form": beta, **extra}


class TestEmptyGuard:
    def test_empty_forms_raises(self):
        with pytest.raises(ValueError, match="at least one bound form or formset"):
            reactive_forms_response(_datastar_post(), [], FRAGMENT, context={})


class TestAllValidDatastar:
    def test_sse_redirect_and_on_success_runs_once(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        calls = []
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: calls.append(1) or None,
        )
        assert isinstance(resp, DatastarResponse)
        assert "/done/" in _sse_body(resp)  # SSE redirect carries the target URL
        assert calls == [1]

    def test_on_success_response_short_circuits(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        sentinel = HttpResponse("custom")
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: sentinel,
        )
        assert resp is sentinel

    def test_none_when_no_on_success_and_no_success_url(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        resp = reactive_forms_response(_datastar_post(), [alpha, beta], FRAGMENT, context=_ctx(alpha, beta))
        assert resp is None


class TestAnyInvalidDatastar:
    def test_patches_all_errors_non_short_circuit(self):
        # First member invalid AND a later member invalid — the single patch must show both.
        alpha, beta = AlphaForm({"name": ""}), BetaForm({"code": ""})
        calls = []
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: calls.append(1) or None,
        )
        assert isinstance(resp, DatastarResponse)
        body = _sse_body(resp)
        assert "alpha:This field is required." in body  # first member's error
        assert "beta:This field is required." in body  # later member's error — proves non-short-circuit
        assert calls == []  # on_success not called
        assert "CTX-OK" in body  # supplied context passed through

    def test_every_member_is_valid_runs_in_order(self):
        order = []

        class SpyAlpha(AlphaForm):
            def is_valid(self):
                order.append("alpha")
                return super().is_valid()

        class SpyBeta(BetaForm):
            def is_valid(self):
                order.append("beta")
                return super().is_valid()

        alpha, beta = SpyAlpha({"name": ""}), SpyBeta({"code": "ok"})  # first invalid
        reactive_forms_response(_datastar_post(), [alpha, beta], FRAGMENT, context=_ctx(alpha, beta))
        assert order == ["alpha", "beta"]  # beta validated despite alpha failing, in order

    def test_caller_attached_cross_form_error_blocks_success(self):
        # D5: both individually valid; caller attaches an aggregate error before the call.
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        assert alpha.is_valid() and beta.is_valid()
        beta.add_error("code", "Cross-form rule failed.")
        calls = []
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: calls.append(1) or None,
        )
        assert isinstance(resp, DatastarResponse)
        assert "beta:Cross-form rule failed." in _sse_body(resp)
        assert calls == []


class TestFormsetMember:
    def test_invalid_formset_surfaces_in_same_patch(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        formset = _formset([{"title": "ok"}, {"title": "toolong"}])  # second row invalid (max_length=3)
        calls = []
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta, formset],
            FRAGMENT,
            context=_ctx(alpha, beta, work_formset=formset),
            on_success=lambda: calls.append(1) or None,
        )
        assert isinstance(resp, DatastarResponse)
        assert "formset:title:" in _sse_body(resp)  # the invalid row's error is in the same patch
        assert calls == []

    def test_valid_formset_falls_through_to_success(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        formset = _formset([{"title": "ok"}])
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta, formset],
            FRAGMENT,
            context=_ctx(alpha, beta, work_formset=formset),
            success_url="/done/",
        )
        assert isinstance(resp, DatastarResponse)  # SSE redirect
        assert "/done/" in _sse_body(resp)


class TestNativeFallback:
    def test_all_valid_returns_http_redirect(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        resp = reactive_forms_response(
            _native_post(), [alpha, beta], FRAGMENT, context=_ctx(alpha, beta), success_url="/done/"
        )
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.url == "/done/"

    def test_invalid_returns_none_for_full_page(self):
        alpha, beta = AlphaForm({"name": ""}), BetaForm({"code": ""})
        resp = reactive_forms_response(
            _native_post(), [alpha, beta], FRAGMENT, context=_ctx(alpha, beta), success_url="/done/"
        )
        assert resp is None

    def test_on_success_response_short_circuits_native(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        sentinel = HttpResponse("custom")
        resp = reactive_forms_response(
            _native_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: sentinel,
        )
        assert resp is sentinel

    def test_on_success_none_falls_through_to_redirect_native(self):
        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        resp = reactive_forms_response(
            _native_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            success_url="/done/",
            on_success=lambda: None,
        )
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.url == "/done/"


class TestPublicExport:
    def test_importable_from_package_root(self):
        from rg.forms import reactive_forms_response as exported

        assert exported is reactive_forms_response

    def test_sse_redirect_and_is_datastar_request_exported(self):
        import rg.forms as pkg
        from rg.forms import is_datastar_request, sse_redirect
        from rg.forms.views import sse_redirect as internal

        assert sse_redirect is internal
        assert "sse_redirect" in pkg.__all__
        assert "is_datastar_request" in pkg.__all__
        assert callable(is_datastar_request)


class TestSseRedirect:
    def test_emits_datastar_redirect_to_url(self):
        from rg.forms import sse_redirect

        resp = sse_redirect("/thanks/")
        assert isinstance(resp, DatastarResponse)
        assert "/thanks/" in _sse_body(resp)

    def test_usable_as_dynamic_on_success_redirect(self):
        # The documented pattern: decide the target inside on_success and return it.
        from rg.forms import sse_redirect

        alpha, beta = AlphaForm({"name": "Ann"}), BetaForm({"code": "X1"})
        resp = reactive_forms_response(
            _datastar_post(),
            [alpha, beta],
            FRAGMENT,
            context=_ctx(alpha, beta),
            on_success=lambda: sse_redirect("/created/42/"),
        )
        assert isinstance(resp, DatastarResponse)
        assert "/created/42/" in _sse_body(resp)


class TestSingleFormDelegationUnchanged:
    """D8: reactive_form_response delegates to the plural helper without behavior change."""

    def test_valid_datastar_sse_redirect(self):
        from rg.forms import reactive_form_response

        alpha = AlphaForm({"name": "Ann"})
        resp = reactive_form_response(_datastar_post(), alpha, FRAGMENT, success_url="/done/")
        assert isinstance(resp, DatastarResponse)
        assert "/done/" in _sse_body(resp)

    def test_invalid_datastar_patch_gets_form_in_context(self):
        from rg.forms import reactive_form_response

        alpha = AlphaForm({"name": ""})
        # The single-form context shim injects {"form": alpha}; fragment reads alpha via alias below.
        resp = reactive_form_response(
            _datastar_post(), alpha, FRAGMENT, context={"alpha_form": alpha, "marker": "SINGLE"}
        )
        assert isinstance(resp, DatastarResponse)
        body = _sse_body(resp)
        assert "alpha:This field is required." in body
        assert "SINGLE" in body

    def test_on_success_receives_the_validated_form(self):
        from rg.forms import reactive_form_response

        alpha = AlphaForm({"name": "Ann"})
        received = []
        reactive_form_response(
            _native_post(),
            alpha,
            FRAGMENT,
            on_success=lambda f: received.append(f) or None,
            success_url="/done/",
        )
        assert received == [alpha]

    def test_invalid_native_returns_none(self):
        from rg.forms import reactive_form_response

        alpha = AlphaForm({"name": ""})
        resp = reactive_form_response(_native_post(), alpha, FRAGMENT)
        assert resp is None
