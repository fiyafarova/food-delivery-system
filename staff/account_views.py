"""Registration of employees and managers, password change.

Who registers whom:
- customer  -> registers themself on the website (customer/views.py: register)
- employee  -> registered by a manager (restaurant owner) on /staff/team/
- manager   -> registered by an administrator on /staff/managers/ (together with a restaurant)
- courier   -> registered by an administrator on /staff/couriers/ (staff/courier_views.py)

Employees and managers get a temporary password; they must change it on first login.
Passwords are never stored as text: set_password / create_user save a PBKDF2 hash.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from restaurants.models import Restaurant

from .models import TemporaryPassword
from .permissions import (
    STAFF_GROUP,
    admin_required,
    is_admin,
    is_courier,
    is_manager,
    is_restaurant_staff,
    manager_required,
    restaurants_for,
)

User = get_user_model()


# ---------------------------------------------------------------- password change

@method_decorator(login_required, name="dispatch")
class ChangePasswordView(PasswordChangeView):
    """Change password for any logged-in user (customer, employee, manager, admin)."""

    template_name = "staff/password_change.html"

    def form_valid(self, form):
        response = super().form_valid(form)  # saves the new hash and keeps the user logged in
        TemporaryPassword.objects.filter(user=self.request.user).delete()
        messages.success(self.request, _("Your password has been changed."))
        return response

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url
        if is_courier(self.request.user):
            return reverse("staff:courier")
        if is_restaurant_staff(self.request.user):
            return reverse("staff:orders")
        return reverse("customer:profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["forced"] = TemporaryPassword.objects.filter(user=self.request.user).exists()
        context["next"] = self.request.GET.get("next", "")
        return context


# ---------------------------------------------------------------- shared form

class NewAccountForm(forms.Form):
    """Account with a temporary password (employee or manager)."""

    username = forms.CharField(label=gettext_lazy("Username"), max_length=150)
    email = forms.EmailField(label=gettext_lazy("Email"))
    first_name = forms.CharField(label=gettext_lazy("First name"), max_length=150, required=False)
    last_name = forms.CharField(label=gettext_lazy("Last name"), max_length=150, required=False)
    password = forms.CharField(label=gettext_lazy("Temporary password"), strip=False,
                               widget=forms.PasswordInput)

    def clean_username(self):
        from django.contrib.auth.validators import UnicodeUsernameValidator

        username = self.cleaned_data["username"].strip()
        UnicodeUsernameValidator()(username)
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email is already in use."))
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password"):
            candidate = User(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
            try:
                validate_password(cleaned["password"], candidate)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned

    def create_user(self, role, created_by):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["username"], email=data["email"], password=data["password"],
            first_name=data["first_name"], last_name=data["last_name"], role=role,
        )
        TemporaryPassword.objects.create(user=user, created_by=created_by)
        return user


# ---------------------------------------------------------------- manager -> employees

class EmployeeForm(NewAccountForm):
    restaurant = forms.ModelChoiceField(label=gettext_lazy("Restaurant"), queryset=Restaurant.objects.none())

    field_order = ["restaurant", "username", "email", "first_name", "last_name", "password"]

    def __init__(self, *args, restaurants, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["restaurant"].queryset = restaurants
        if restaurants.count() == 1:
            self.fields["restaurant"].initial = restaurants.first()


@manager_required
def team(request):
    """Manager's page: employees of my restaurants + register a new employee."""
    restaurants = restaurants_for(request.user).order_by("name")
    if not is_admin(request.user):
        restaurants = restaurants.filter(owner=request.user)  # a manager manages only own restaurants

    form = EmployeeForm(request.POST or None, restaurants=restaurants)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            employee = form.create_user(role="customer", created_by=request.user)
            employee.groups.add(Group.objects.get(name=STAFF_GROUP))
            form.cleaned_data["restaurant"].staff.add(employee)
        messages.success(request, _("Employee %(name)s registered. Give them the temporary password; "
                                    "they will have to change it at first login.") % {"name": employee.username})
        return redirect("staff:team")

    return render(request, "staff/team.html", {
        "form": form,
        "restaurants": restaurants.prefetch_related("staff"),
    })


@manager_required
@require_POST
def team_remove(request, restaurant_id, user_id):
    """Remove an employee from my restaurant (the account itself is kept)."""
    restaurants = restaurants_for(request.user)
    if not is_admin(request.user):
        restaurants = restaurants.filter(owner=request.user)
    restaurant = get_object_or_404(restaurants, pk=restaurant_id)
    employee = get_object_or_404(restaurant.staff, pk=user_id)
    restaurant.staff.remove(employee)
    if not employee.staff_restaurants.exists():
        employee.groups.remove(Group.objects.get(name=STAFF_GROUP))  # no restaurant left: no staff role
    messages.success(request, _("Employee %(name)s removed from %(restaurant)s.")
                     % {"name": employee.username, "restaurant": restaurant.name})
    return redirect("staff:team")


# ---------------------------------------------------------------- admin -> managers

class ManagerForm(NewAccountForm):
    restaurant_name = forms.CharField(label=gettext_lazy("Restaurant name"), max_length=150)
    address = forms.CharField(label=gettext_lazy("Restaurant address"), max_length=255)
    city = forms.CharField(label=gettext_lazy("City"), max_length=100, initial="Almaty")
    cuisine = forms.CharField(label=gettext_lazy("Cuisine"), max_length=100, required=False)


@admin_required
def managers(request):
    """Admin's page: managers (restaurant owners) + register a new manager with a restaurant."""
    form = ManagerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            manager = form.create_user(role="owner", created_by=request.user)
            Restaurant.objects.create(owner=manager, name=data["restaurant_name"], address=data["address"],
                                      city=data["city"], cuisine=data["cuisine"])
        messages.success(request, _("Manager %(name)s registered with restaurant %(restaurant)s.")
                         % {"name": manager.username, "restaurant": data["restaurant_name"]})
        return redirect("staff:managers")

    owners = (User.objects.filter(role=User.Role.OWNER)
              .prefetch_related("restaurants").order_by("username"))
    return render(request, "staff/managers.html", {"form": form, "owners": owners})


def account_links(user):
    """Which account pages to show in the staff header."""
    return {"show_team": is_manager(user), "show_managers": is_admin(user), "show_couriers": is_admin(user)}
