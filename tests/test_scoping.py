"""Tests for scoped signals and reactive formsets (ADR-0003)."""

from django.forms import formset_factory
from django.template import Context, Template

from rg.forms import (
    FieldGroup,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveForm,
)
from rg.forms.scoping import compile_expression, decode_scope, encode_scope
from rg.forms.templatetags.reactive_forms import render_field_group


class TestScopeEncoder:
    def test_injective_over_adversarial_prefixes(self):
        """The rejected ``-``->``_`` idea collapses these; Base32 must not."""
        assert encode_scope("a-b_c") != encode_scope("a_b-c")

    def test_unicode_prefix(self):
        s = encode_scope("формула-0")
        assert s.isidentifier()
        assert decode_scope(s) == "формула-0"

    def test_always_identifier_safe_leading_letter(self):
        for prefix in ["form-0", "form-1", "a", "x-y-z", "0start"]:
            scope = encode_scope(prefix)
            assert scope[0].isalpha()
            assert scope.isidentifier()
            assert "." not in scope and "-" not in scope

    def test_round_trip(self):
        for prefix in ["form-0", "a-b_c", "a_b-c", "weird prefix!"]:
            assert decode_scope(encode_scope(prefix)) == prefix


class TestCompileScoping:
    FIELDS = {"role", "count"}

    def test_declared_field_is_scoped(self):
        scope = encode_scope("form-0")
        out = compile_expression("$role == 'admin'", scope=scope, field_names=self.FIELDS)
        assert f"$rgForms.{scope}.role" in out
        assert out == f'($rgForms.{scope}.role === "admin")'

    def test_unknown_or_external_reference_left_alone(self):
        scope = encode_scope("form-0")
        out = compile_expression("$feature_enabled", scope=scope, field_names=self.FIELDS)
        assert out == "$feature_enabled"  # not a declared field -> unscoped

    def test_string_literal_not_rewritten(self):
        scope = encode_scope("form-0")
        out = compile_expression("$role == '$role'", scope=scope, field_names=self.FIELDS)
        # The literal '$role' must survive as a string, only the ref is scoped.
        assert '"$role"' in out
        assert f"$rgForms.{scope}.role ===" in out

    def test_near_match_not_rewritten(self):
        """A different field ($role_id) is not a partial-match of $role."""
        scope = encode_scope("form-0")
        out = compile_expression("$role_id == 'x'", scope=scope, field_names={"role"})
        # role_id is not declared -> left unscoped; role is untouched.
        assert "$role_id" in out
        assert f"$rgForms.{scope}.role" not in out

    def test_unprefixed_is_identity(self):
        out = compile_expression("$role == 'admin'", scope=None, field_names=self.FIELDS)
        assert out == '($role === "admin")'


class RowForm(ReactiveForm):
    role = ReactiveChoiceField(choices=[("admin", "Admin"), ("editor", "Editor")])
    admin_note = ReactiveCharField(required=False, visible_when="$role == 'admin'")


class TestPerRowIndependence:
    def test_rows_bind_and_show_distinct_scopes(self):
        formset_cls = formset_factory(RowForm, extra=2)
        formset = formset_cls()
        template = Template(
            "{% load reactive_forms %}"
            "{% for f in formset.forms %}"
            "{% render_reactive_field f.role %}{% render_reactive_field f.admin_note %}"
            "{% endfor %}"
        )
        result = template.render(Context({"formset": formset}))

        scope0 = encode_scope("form-0")
        scope1 = encode_scope("form-1")

        # Each row binds to its own scoped signal (value form preserves case).
        assert f'data-bind="rgForms.{scope0}.role"' in result
        assert f'data-bind="rgForms.{scope1}.role"' in result

        # Each row's visible_when references its own row's signal.
        assert f"rgForms.{scope0}.role" in result
        assert f"rgForms.{scope1}.role" in result
        assert scope0 != scope1

    def test_formset_seed_is_nested_per_row(self):
        formset_cls = formset_factory(RowForm, extra=2)
        formset = formset_cls()
        template = Template("{% load reactive_forms %}<form data-signals='{% reactive_formset_signals formset %}'>")
        result = template.render(Context({"formset": formset}))

        scope0 = encode_scope("form-0")
        scope1 = encode_scope("form-1")
        assert '"rgForms"' in result
        assert f'"{scope0}"' in result
        assert f'"{scope1}"' in result
        assert '"role"' in result


class GroupForm(ReactiveForm):
    account_type = ReactiveChoiceField(choices=[("personal", "Personal"), ("business", "Business")])
    company = ReactiveCharField(required=False)

    class Meta:
        field_groups = {
            "co": FieldGroup(
                fields=["company"],
                label="Company",
                visible_when="$account_type == 'business'",
            ),
        }


class TestGroupScoping:
    def test_group_visible_when_scoped_in_prefixed_form(self):
        form = GroupForm(prefix="form-0")
        ctx = render_field_group({}, form, "co")
        scope = encode_scope("form-0")
        assert ctx["group_visible_when"] == (f'($rgForms.{scope}.account_type === "business")')

    def test_group_visible_when_unscoped_without_prefix(self):
        form = GroupForm()
        ctx = render_field_group({}, form, "co")
        assert ctx["group_visible_when"] == '($account_type === "business")'


class TestSeedScoping:
    def test_standalone_prefixed_form_seed_is_nested(self):
        form = RowForm(prefix="form-0")
        seed = form.get_seed_signals()
        scope = encode_scope("form-0")
        assert set(seed.keys()) == {"rgForms"}
        assert scope in seed["rgForms"]
        assert "role" in seed["rgForms"][scope]

    def test_unprefixed_form_seed_is_flat(self):
        form = RowForm()
        seed = form.get_seed_signals()
        assert "rgForms" not in seed
        assert "role" in seed
