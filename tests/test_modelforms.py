"""Tests for ReactiveModelForm and the hidden-field / model-instance contract."""

import pytest
from django import forms

from rg.forms import (
    FieldGroup,
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveForm,
    ReactiveModelForm,
)

from .models import ProviderConfig

STORED = {
    "name": "id.gov.ua",
    "enabled": True,
    "client_id": "stored-client",
    "token_url": "https://id.gov.ua/token",
    "secret": "stored-secret",
}


class ProviderForm(ReactiveModelForm):
    """The motivating case: a flag gating a block of stored configuration."""

    enabled = ReactiveBooleanField(required=False)
    client_id = ReactiveCharField(required=False, visible_when="$enabled")
    token_url = ReactiveCharField(required=False, visible_when="$enabled")
    secret = ReactiveCharField(required=False, widget=forms.PasswordInput, visible_when="$enabled")

    class Meta:
        model = ProviderConfig
        fields = ["name", "enabled", "client_id", "token_url", "secret"]
        field_groups = {
            "config": FieldGroup(fields=["client_id", "token_url", "secret"], visible_when="$enabled"),
        }


class NaiveComposedForm(ReactiveForm, forms.ModelForm):
    """The hand-rolled composition, without ReactiveModelForm's _post_clean.

    Kept so the regression guard below is demonstrably non-vacuous: this is the
    class shape a consumer writes today, and it loses the stored value.
    """

    enabled = ReactiveBooleanField(required=False)
    client_id = ReactiveCharField(required=False, visible_when="$enabled")

    class Meta:
        model = ProviderConfig
        fields = ["name", "enabled", "client_id"]


def _disable(**overrides):
    """POST data for "untick enabled and save" — nothing else submitted."""
    data = {"name": STORED["name"]}
    data.update(overrides)
    return data


class TestReactiveModelFormComposition:
    """Item 1: the class is a ModelForm and a ReactiveForm at the same time."""

    def test_mro_puts_reactive_clean_fields_ahead_of_the_model_form(self):
        assert ProviderForm._clean_fields.__qualname__ == "ReactiveForm._clean_fields"
        assert ProviderForm._post_clean.__qualname__ == "ReactiveModelForm._post_clean"
        assert issubclass(ReactiveModelForm, forms.ModelForm)
        assert issubclass(ReactiveModelForm, ReactiveForm)

    def test_meta_fields_generate_model_fields(self):
        form = ProviderForm()
        assert set(form.fields) == {"name", "enabled", "client_id", "token_url", "secret"}
        # A declared reactive field wins over the auto-generated model field.
        assert form.fields["client_id"].visible_when == "$enabled"

    def test_meta_carries_both_vocabularies(self):
        form = ProviderForm()
        assert "config" in form.get_field_groups()
        assert form.fields["name"].max_length == 100

    def test_unbound_signals_come_from_the_instance(self):
        form = ProviderForm(instance=ProviderConfig(**STORED))
        signals = form.get_signals()
        assert signals["client_id"] == "stored-client"
        assert signals["enabled"] is True

    def test_unbound_client_signals_still_suppress_a_write_only_widget(self):
        form = ProviderForm(instance=ProviderConfig(**STORED))
        assert form.get_signals()["secret"] == "stored-secret"
        assert form.get_client_signals()["secret"] == ""

    def test_bound_signals_come_from_the_submitted_data(self):
        form = ProviderForm(data=_disable(enabled="on", client_id="typed"), instance=ProviderConfig(**STORED))
        assert form.get_signals()["client_id"] == "typed"

    def test_visible_rules_still_apply(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_field_visible("client_id") is False
        assert form.is_group_visible("config") is False
        form = ProviderForm(data=_disable(enabled="on"), instance=ProviderConfig(**STORED))
        assert form.is_field_visible("client_id") is True

    def test_post_clean_still_runs(self):
        """Model-level validation must still reach the form.

        ``ProviderConfig.clean`` has no form-field counterpart and only
        ``_post_clean`` calls ``instance.full_clean``, so this error can arrive
        by no other route.
        """
        form = ProviderForm(data={"name": "rejected-by-the-model"}, instance=ProviderConfig(**STORED))
        assert not form.is_valid()
        assert "The model rejects this name." in str(form.errors["name"])

    def test_post_clean_still_runs_when_fields_are_withheld(self):
        """Withholding the hidden names must not skip model validation."""
        form = ProviderForm(data=_disable(name="rejected-by-the-model"), instance=ProviderConfig(**STORED))
        assert form.get_hidden_field_names()
        assert not form.is_valid()
        assert "The model rejects this name." in str(form.errors["name"])

    def test_construct_instance_still_writes_the_visible_fields(self):
        """The other half of _post_clean: cleaned_data reaches the instance."""
        form = ProviderForm(data=_disable(enabled="on", client_id="new-client"), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.instance.client_id == "new-client"


class TestHiddenFieldsAreNotWrittenToTheInstance:
    """Item 2: the regression guard that matters most."""

    def test_untick_keeps_the_stored_configuration_on_the_instance(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.instance.client_id == "stored-client"
        assert form.instance.token_url == "https://id.gov.ua/token"
        assert form.instance.secret == "stored-secret"

    def test_the_visible_field_that_did_the_hiding_is_still_written(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.instance.enabled is False

    @pytest.mark.django_db
    def test_the_stored_value_survives_save(self):
        stored = ProviderConfig.objects.create(**STORED)
        form = ProviderForm(data=_disable(), instance=ProviderConfig.objects.get(pk=stored.pk))
        assert form.is_valid(), form.errors
        form.save()

        reloaded = ProviderConfig.objects.get(pk=stored.pk)
        assert reloaded.enabled is False
        assert reloaded.client_id == "stored-client"
        assert reloaded.token_url == "https://id.gov.ua/token"
        assert reloaded.secret == "stored-secret"

    @pytest.mark.django_db
    def test_a_visible_field_still_saves_its_new_value(self):
        stored = ProviderConfig.objects.create(**STORED)
        form = ProviderForm(
            data=_disable(enabled="on", client_id="new-client", token_url="https://x/", secret="new-secret"),
            instance=ProviderConfig.objects.get(pk=stored.pk),
        )
        assert form.is_valid(), form.errors
        form.save()

        reloaded = ProviderConfig.objects.get(pk=stored.pk)
        assert reloaded.client_id == "new-client"
        assert reloaded.secret == "new-secret"

    def test_the_naive_composition_loses_it(self):
        """Without ReactiveModelForm, the same submission nulls the column."""
        form = NaiveComposedForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.instance.client_id is None

    def test_cleaned_data_still_reads_none_for_a_hidden_field(self):
        """The withholding is scoped to _post_clean; cleaned_data is unchanged."""
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["client_id"] is None
        assert form.cleaned_data["secret"] is None
        assert form.cleaned_data["enabled"] is False

    def test_a_submitted_value_on_a_hidden_field_is_still_ignored(self):
        """A hidden control still posts; its value must not reach the instance."""
        form = ProviderForm(data=_disable(client_id="tampered"), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["client_id"] is None
        assert form.instance.client_id == "stored-client"

    def test_a_plain_reactive_form_is_unaffected(self):
        """The ModelForm-only fix must not change Form behaviour."""

        class Plain(ReactiveForm):
            enabled = ReactiveBooleanField(required=False)
            client_id = ReactiveCharField(required=False, visible_when="$enabled")

        form = Plain(data={})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["client_id"] is None


class TestGetHiddenFieldNames:
    def test_reports_the_fields_a_false_rule_hides(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.get_hidden_field_names() == {"client_id", "token_url", "secret"}

    def test_reports_nothing_when_every_rule_is_true(self):
        form = ProviderForm(data=_disable(enabled="on"), instance=ProviderConfig(**STORED))
        assert form.get_hidden_field_names() == set()

    def test_answers_before_validation(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert "client_id" in form.get_hidden_field_names()
        assert not hasattr(form, "cleaned_data")

    def test_answers_for_an_unbound_form(self):
        form = ProviderForm(instance=ProviderConfig(**{**STORED, "enabled": False}))
        assert form.get_hidden_field_names() == {"client_id", "token_url", "secret"}

    def test_a_field_without_a_rule_is_never_hidden(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert "name" not in form.get_hidden_field_names()
        assert "enabled" not in form.get_hidden_field_names()

    def test_is_not_djangos_hidden_fields(self):
        """Django's hidden_fields() means <input type=hidden> — unrelated."""
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.hidden_fields() == []
        assert form.get_hidden_field_names()


class TestVisibleChangedData:
    def test_excludes_edits_the_form_is_hiding(self):
        form = ProviderForm(data=_disable(), instance=ProviderConfig(**STORED))
        assert form.is_valid(), form.errors
        # Django sees the unsubmitted hidden inputs as cleared.
        assert set(form.changed_data) >= {"enabled", "client_id", "token_url", "secret"}
        assert form.visible_changed_data == ["enabled"]

    def test_keeps_edits_to_a_visible_field(self):
        form = ProviderForm(
            data=_disable(enabled="on", client_id="new-client", token_url=STORED["token_url"]),
            instance=ProviderConfig(**STORED),
        )
        assert form.is_valid(), form.errors
        assert "client_id" in form.visible_changed_data

    def test_is_empty_when_nothing_visible_changed(self):
        form = ProviderForm(
            data=_disable(
                enabled="on",
                client_id=STORED["client_id"],
                token_url=STORED["token_url"],
            ),
            instance=ProviderConfig(**STORED),
        )
        assert form.is_valid(), form.errors
        # `secret` is write-only, so its blank submission always reads as a
        # change; it is the one field a "was anything edited?" check must ask
        # about separately.
        assert [name for name in form.visible_changed_data if name != "secret"] == []

    def test_is_available_on_a_plain_reactive_form(self):
        class Plain(ReactiveForm):
            enabled = ReactiveBooleanField(required=False)
            note = ReactiveCharField(required=False, visible_when="$enabled")

        form = Plain(data={"note": "typed"}, initial={"note": ""})
        assert form.is_valid(), form.errors
        assert "note" in form.changed_data
        assert form.visible_changed_data == []
