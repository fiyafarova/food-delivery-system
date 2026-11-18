
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext

from accounts.models import CustomerProfile

from .forms import AddressForm, PersonalForm
from django.shortcuts import render

# Temporary test data (replace with queries to core.models later)
TEST_MENU = [
    {"id": 1, "name": "Pizza", "price": 2500, "category": "Main", "is_available": True},
    {"id": 2, "name": "Burger", "price": 1800, "category": "Main", "is_available": True},
    {"id": 3, "name": "Cola", "price": 600, "category": "Drinks", "is_available": False},
]


def menu(request):
    return render(request, "customer/menu.html", {"items": TEST_MENU})


def cart(request):
    return render(request, "customer/cart.html")


def checkout(request):
    return render(request, "customer/checkout.html")


def order_status(request, order_id):
    return render(request, "customer/order_status.html", {"order_id": order_id})

def favorites(request):
    return render(request, "customer/favorites.html")



@login_required
def profile(request):
    user = request.user
    profile_obj, _ = CustomerProfile.objects.get_or_create(user=user)
    profile_url = reverse("customer:profile")

    tab = request.GET.get("tab", "personal")
    if tab not in ("personal", "address"):
        tab = "personal"

    editing = request.GET.get("edit") == "1"
    personal_form = PersonalForm(user=user, profile=profile_obj)
    address_form = AddressForm(profile=profile_obj)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "personal":
            tab = "personal"
            editing = True
            personal_form = PersonalForm(
                request.POST, user=user, profile=profile_obj
            )
            if personal_form.is_valid():
                personal_form.save()
                messages.success(request, gettext("Changes saved"))
                return redirect(f"{profile_url}?tab=personal")

        elif form_type == "address":
            tab = "address"
            editing = True
            address_form = AddressForm(request.POST, profile=profile_obj)
            if address_form.is_valid():
                address_form.save()
                messages.success(request, gettext("Changes saved"))
                return redirect(f"{profile_url}?tab=address")

    initials = (user.first_name[:1] + user.last_name[:1]).upper()
    favorites_url = reverse("customer:favorites")

    return render(request, "customer/profile.html", {
        "tab": tab,
        "editing": editing,
        "profile": profile_obj,
        "personal_form": personal_form,
        "address_form": address_form,
        "initials": initials or user.get_username()[:2].upper(),
        "profile_url": profile_url,
        "logout_url": None,
        "favorites_url": favorites_url,
        "extra_nav": [
            {"key": "favorites", "label": gettext("Favorites"), "url": favorites_url},
        ],
    })
