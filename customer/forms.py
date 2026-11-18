from django import forms
from django.core.validators import RegexValidator
from django.db import transaction
from django.utils.translation import gettext_lazy as _

phone_validator = RegexValidator(
    regex=r"^\+?[0-9\s\-()]{10,20}$",
    message=_("Enter a valid phone number, for example +7 701 000 00 00"),
)


class PersonalForm(forms.Form):
    first_name = forms.CharField(label=_("First name"), max_length=150)
    last_name = forms.CharField(label=_("Last name"), max_length=150, required=False)
    phone = forms.CharField(
        label=_("Phone"),
        max_length=20,
        required=False,
        validators=[phone_validator],
    )

    def __init__(self, *args, user, profile, **kwargs):
        self.user = user
        self.profile = profile
        kwargs.setdefault(
            "initial",
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": profile.phone,
            },
        )
        super().__init__(*args, **kwargs)

    @transaction.atomic
    def save(self):
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.save(update_fields=["first_name", "last_name"])
        self.profile.phone = self.cleaned_data["phone"]
        self.profile.save(update_fields=["phone"])


class AddressForm(forms.Form):
    city = forms.CharField(label=_("City"), max_length=100)
    address = forms.CharField(label=_("Address"), max_length=255)

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        kwargs.setdefault(
            "initial",
            {"city": profile.city, "address": profile.address},
        )
        super().__init__(*args, **kwargs)

    def save(self):
        self.profile.city = self.cleaned_data["city"]
        self.profile.address = self.cleaned_data["address"]
        self.profile.save(update_fields=["city", "address"])