"""Models backing the :class:`~rg.forms.ReactiveModelForm` tests.

``tests`` is an installed app purely so these get a table; nothing in the
shipped package depends on them. The shape mirrors the case that motivated the
hidden-field fix: one flag gating a block of configuration that must survive
being switched off.
"""

from django.core.exceptions import ValidationError
from django.db import models


class ProviderConfig(models.Model):
    """An external identity provider whose configuration is gated by a flag."""

    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False)
    client_id = models.CharField(max_length=100, blank=True)
    token_url = models.CharField(max_length=200, blank=True)
    secret = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Model-level validation with no form-field counterpart.

        Deliberately not expressible as a form-field rule (a ``max_length``
        would be mirrored onto the generated form field and rejected before the
        model is ever consulted). Nothing but ``_post_clean`` calls
        ``instance.full_clean``, so an error raised here can only reach the form
        through it — which is what makes it usable as proof that it ran.
        """
        if self.name == "rejected-by-the-model":
            raise ValidationError({"name": "The model rejects this name."})
