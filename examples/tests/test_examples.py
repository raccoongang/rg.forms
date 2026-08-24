"""Tests for the rg.forms example application (run with testsite.settings)."""

import json
import re
from decimal import Decimal

import pytest
from django.forms import formset_factory
from django.test import Client
from django.urls import reverse

from examples.forms import (
    FeatureFlaggedForm,
    OnboardingForm,
    OrderConfiguratorForm,
    RegistrationForm,
    TeamMemberForm,
)
from examples.views.misc import EXAMPLES

PAGE_URLS = [
    "examples:index",
    "examples:registration",
    "examples:order_configurator",
    "examples:team_roster",
    "examples:settings_dashboard",
    "examples:feature_flags",
    "examples:canonical_values",
    "examples:design_systems",
    "examples:onboarding",
    "examples:cascading_form",
    "examples:sse_validation",
    "examples:risks",
]


@pytest.mark.parametrize("name", PAGE_URLS)
def test_every_page_returns_ok(name):
    assert Client().get(reverse(name)).status_code == 200


def test_index_links_every_example():
    body = Client().get(reverse("examples:index")).content.decode()
    for ex in EXAMPLES:
        assert reverse(ex["url"]) in body


# --- Example 2: order configurator (ADR-0002) --------------------------------
class TestOrderConfigurator:
    def test_exact_decimal_recompute_ignores_tampered_total(self):
        form = OrderConfiguratorForm(data={"plan": "010", "seats": "3", "coupon": "", "total": "999"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["total"] == Decimal("87.00")  # 3 * 29.00, not 999

    def test_leading_zero_code_is_string_typed(self):
        body = Client().get(reverse("examples:order_configurator")).content.decode()
        # compiled, typed equality against the string "100"
        assert "=== &quot;100&quot;" in body

    def test_hidden_field_skipped_server_side(self):
        # enterprise_contact is required_when plan==100 but hidden otherwise.
        form = OrderConfiguratorForm(data={"plan": "001", "seats": "1"})
        assert form.is_valid(), form.errors  # not required because hidden

    def test_enterprise_contact_required_when_visible(self):
        form = OrderConfiguratorForm(data={"plan": "100", "seats": "1", "enterprise_contact": ""})
        assert not form.is_valid()
        assert "enterprise_contact" in form.errors


# --- Example 3: team roster static formset (ADR-0003) ------------------------
class TestTeamRoster:
    def _management(self, n=2):
        return {
            "form-TOTAL_FORMS": str(n), "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        }

    def test_rows_have_distinct_scopes(self):
        body = Client().get(reverse("examples:team_roster")).content.decode()
        scopes = set(re.findall(r"rgForms\.(p[a-z0-9]+)\.role", body))
        assert len(scopes) >= 2

    def test_seed_is_nested_per_row(self):
        body = Client().get(reverse("examples:team_roster")).content.decode()
        # The seed keeps readable JSON (double quotes) inside the single-quoted
        # data-signals attribute.
        assert "rgForms" in body and '"role"' in body

    def test_post_round_trips_to_correct_rows(self):
        FS = formset_factory(TeamMemberForm, extra=2)
        data = self._management()
        data.update({
            "form-0-full_name": "Ann", "form-0-role": "owner", "form-0-email": "ann@x.com",
            "form-1-full_name": "Bo", "form-1-role": "viewer",
        })
        fs = FS(data)
        assert fs.is_valid(), fs.errors
        assert fs.forms[0].cleaned_data["full_name"] == "Ann"

    def test_per_row_required_when(self):
        FS = formset_factory(TeamMemberForm, extra=2)
        data = self._management()
        data.update({
            "form-0-full_name": "Ann", "form-0-role": "owner", "form-0-email": "",  # owner needs email
            "form-1-full_name": "Bo", "form-1-role": "viewer",
        })
        assert not FS(data).is_valid()


# --- Example 4: multi-form scoping (ADR-0003) --------------------------------
class TestSettingsDashboard:
    def test_overlapping_names_get_distinct_scopes(self):
        body = Client().get(reverse("examples:settings_dashboard")).content.decode()
        scopes = set(re.findall(r"rgForms\.(p[a-z0-9]+)\.email", body))
        assert len(scopes) >= 2  # profile.email and notifications.email don't collide


# --- Example 5: external signals (ADR-0002) ----------------------------------
class TestFeatureFlags:
    def test_visibility_follows_server_signal(self):
        assert FeatureFlaggedForm(plan_tier="free").is_field_visible("priority_support") is False
        assert FeatureFlaggedForm(plan_tier="paid").is_field_visible("priority_support") is True

    def test_requiredness_follows_server_signal(self):
        # beta required only when the server enables it
        off = FeatureFlaggedForm(data={"name": "x"}, can_use_beta=False)
        assert off.is_valid(), off.errors
        on = FeatureFlaggedForm(data={"name": "x", "beta_feature_opt_in": ""}, can_use_beta=True)
        assert not on.is_valid()

    def test_external_seed_present_on_page(self):
        body = Client().get(reverse("examples:feature_flags") + "?plan=paid&beta=1").content.decode()
        assert "plan_tier" in body and "can_use_beta" in body


# --- Example 8: onboarding (grouped + incremental + computed) ----------------
class TestOnboarding:
    def test_personal_account_skips_business_fields(self):
        form = OnboardingForm(data={
            "account_type": "personal", "first_name": "A", "last_name": "B", "email": "a@b.com",
        })
        assert form.is_valid(), form.errors

    def test_business_requires_company_and_valid_email(self):
        form = OnboardingForm(data={
            "account_type": "business", "first_name": "A", "last_name": "B",
            "email": "a@gmail.com", "company_name": "", "workspace": "freshspace",
            "seats": "2", "price_per_seat": "29.00", "billing_country": "us",
        })
        assert not form.is_valid()
        assert "company_name" in form.errors  # required_when business
        assert "email" in form.errors  # free-domain rejected for business

    def test_computed_monthly_total_is_exact(self):
        form = OnboardingForm(data={
            "account_type": "business", "first_name": "A", "last_name": "B",
            "email": "a@acme.dev", "company_name": "Acme", "workspace": "freshspace",
            "seats": "4", "price_per_seat": "29.00", "billing_country": "us",
        })
        assert form.is_valid(), form.errors
        assert form.cleaned_data["monthly_total"] == Decimal("116.00")


# --- Incremental validation flow (ADR-0004), CSRF-enforced -------------------
@pytest.mark.django_db
class TestIncrementalValidation:
    def _token(self, client, url):
        resp = client.get(url)
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.content.decode())
        assert m, "csrf token not found"
        return m.group(1)

    def _post(self, client, url, field, signals, token, *, override_disc=None):
        disc = override_disc or field
        return client.post(
            f"{url}?__rg_field={disc}",
            data=json.dumps(signals),
            content_type="application/json",
            HTTP_DATASTAR_REQUEST="true",
            HTTP_X_CSRFTOKEN=token,
            HTTP_X_RG_VALIDATE_FIELD=field,
        )

    def test_available_username_passes(self):
        c = Client(enforce_csrf_checks=True)
        token = self._token(c, "/registration/")
        r = self._post(c, "/registration/validate/", "username", {"username": "freshname"}, token)
        assert r.status_code == 200
        body = b"".join(r.streaming_content).decode()
        assert "id_username_field" in body and "already taken" not in body

    def test_taken_username_shows_error(self):
        c = Client(enforce_csrf_checks=True)
        token = self._token(c, "/registration/")
        r = self._post(c, "/registration/validate/", "username", {"username": "admin"}, token)
        body = b"".join(r.streaming_content).decode()
        assert "already taken" in body and 'aria-invalid="true"' in body

    def test_handler_survives_the_patch(self):
        c = Client(enforce_csrf_checks=True)
        token = self._token(c, "/registration/")
        r = self._post(c, "/registration/validate/", "username", {"username": "admin"}, token)
        body = b"".join(r.streaming_content).decode()
        assert "data-on:blur" in body and "__rg_field=username" in body

    def test_missing_csrf_rejected(self):
        c = Client(enforce_csrf_checks=True)
        self._token(c, "/registration/")
        r = c.post(
            "/registration/validate/?__rg_field=username",
            data=json.dumps({"username": "x"}), content_type="application/json",
            HTTP_DATASTAR_REQUEST="true", HTTP_X_RG_VALIDATE_FIELD="username",
        )
        assert r.status_code == 403

    def test_header_url_mismatch_rejected(self):
        c = Client(enforce_csrf_checks=True)
        token = self._token(c, "/registration/")
        r = self._post(c, "/registration/validate/", "username", {"username": "x"}, token, override_disc="email")
        assert r.status_code == 400

    def test_wrong_scope_rejected(self):
        # settings profile validate expects the "profile" scope; a bad scope path fails.
        from rg.forms.scoping import encode_scope

        c = Client(enforce_csrf_checks=True)
        token = self._token(c, "/settings-dashboard/")
        wrong = f"rgForms.{encode_scope('notifications')}.email"
        r = self._post(c, "/settings-dashboard/validate/", wrong, {}, token)
        assert r.status_code == 400
