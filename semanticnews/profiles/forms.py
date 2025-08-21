from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)


class DisplayNameForm(forms.ModelForm):
    """Single-field form to edit the display name (first_name)."""

    class Meta:
        model = User
        fields = ["first_name"]
        labels  = {"first_name": _("Display name")}

    def clean_first_name(self):
        name = self.cleaned_data["first_name"].strip()
        if not name:
            raise forms.ValidationError(_("Display name cannot be empty."))

        # Optional uniqueness check ― comment out if duplicates are OK
        if (
            User.objects.filter(first_name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(_("This display name is already taken."))

        return name