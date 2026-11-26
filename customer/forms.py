from django import forms
from accounts.models import SavedCard
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

class SignUpForm(forms.Form):
    """Customer registration on the website. Employees and managers are registered by
    their manager / an administrator on the staff pages, not here."""

    username = forms.CharField(label=_("Username"), max_length=150)
    email = forms.EmailField(label=_("Email"))
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label=_("Repeat password"), widget=forms.PasswordInput, strip=False)

    def clean_username(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.validators import UnicodeUsernameValidator

        username = self.cleaned_data["username"].strip()
        UnicodeUsernameValidator()(username)
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean_email(self):
        from django.contrib.auth import get_user_model

        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email is already in use."))
        return email

    def clean(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password

        cleaned = super().clean()
        password1, password2 = cleaned.get("password1"), cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The two passwords do not match."))
        elif password1:
            # same rules as the API: length, common passwords, only digits, similar to username
            candidate = get_user_model()(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
            try:
                validate_password(password1, candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    @transaction.atomic
    def save(self):
        from django.contrib.auth import get_user_model

        from accounts.models import CustomerProfile

        user = get_user_model().objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],  # create_user stores only the PBKDF2 hash
            role="customer",
        )
        CustomerProfile.objects.create(user=user)
        return user


class SavedCardForm(forms.ModelForm):
    last4 = forms.CharField(
        label=_("Last 4 digits"), min_length=4, max_length=4,
        validators=[RegexValidator(r"^[0-9]{4}$", _("Enter exactly four digits."))],
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric", "autocomplete": "off"}),
    )

    class Meta:
        model = SavedCard
        fields = ["nickname", "brand", "last4"]
        labels = {"nickname": _("Card name"), "brand": _("Card type")}
        widgets = {
            "nickname": forms.TextInput(attrs={"class": "form-control", "placeholder": _("For example, my main card")}),
            "brand": forms.Select(attrs={"class": "form-select"}),
        }
