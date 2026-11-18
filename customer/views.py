
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext

from accounts.models import CustomerProfile, DeliveryAddress
from restaurants.models import Restaurant

from core.access import customer_of
from core.models import FoodOrder

from .cart import build_cart
from .forms import AddressForm, PersonalForm, SignUpForm

@ensure_csrf_cookie
def menu(request):
    restaurants = list(Restaurant.objects.filter(is_open=True).prefetch_related("food_items"))
    cart = build_cart(request)
    return render(request, "customer/menu.html", {
        "restaurants": restaurants,
        "cuisines": sorted({restaurant.cuisine for restaurant in restaurants if restaurant.cuisine}),
        "cart_dish_ids": {line["id"] for line in cart["lines"]},
    })


def cart(request):
    return render(request, "customer/cart.html")


CHECKOUT_DRAFT_KEY = "checkout_draft"
CHECKOUT_FIELD_LIMITS = {"city": 100, "phone": 20, "address": 255, "comment": 500}


@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = build_cart(request)
    ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if not cart["can_checkout"]:
        if ajax:
            return JsonResponse({"error": gettext("Could not update the cart")}, status=409)
        return redirect("customer:cart")

    if request.method == "POST":
        draft = {field: request.POST.get(field, "").strip() for field in CHECKOUT_FIELD_LIMITS}
        if any(len(draft[field]) > limit for field, limit in CHECKOUT_FIELD_LIMITS.items()):
            if ajax:
                return JsonResponse({"saved": False}, status=400)
            return render(request, "customer/checkout.html", {"cart": cart, "draft": draft, "draft_error": True}, status=400)
        request.session[CHECKOUT_DRAFT_KEY] = draft
        if ajax:
            return JsonResponse({"saved": True})
        messages.success(request, gettext("Changes saved"))
        return redirect("customer:checkout")

    draft = request.session.get(CHECKOUT_DRAFT_KEY)
    if draft is None:
        profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
        draft = {field: getattr(profile, field, "") for field in CHECKOUT_FIELD_LIMITS}
    return render(request, "customer/checkout.html", {"cart": cart, "draft": draft})


# Steps shown to the customer on the order page
ORDER_STEPS = ["Placed", "Preparing", "Delivered"]


@login_required
def order_status(request, order_id):
    """A customer sees only their own order (someone else's order -> 404)."""
    customer = customer_of(request.user)
    order = get_object_or_404(
        FoodOrder.objects.select_related("restaurant").prefetch_related("items__food_item"),
        pk=order_id, customer=customer,
    ) if customer else None
    if order is None:
        raise Http404
    lines = [
        {"name": line.food_item.name, "quantity": line.quantity,
         "unit_price": line.unit_price, "total": line.quantity * line.unit_price}
        for line in order.items.all()
    ]
    done = ORDER_STEPS.index(order.status) if order.status in ORDER_STEPS else -1
    steps = [{"name": step, "done": i <= done} for i, step in enumerate(ORDER_STEPS)]
    return render(request, "customer/order_status.html", {
        "order": order,
        "lines": lines,
        "steps": steps,
        "cancelled": order.status == FoodOrder.Status.CANCELLED,
    })

def favorites(request):
    return render(request, "customer/favorites.html")



@login_required
def profile(request):
    user = request.user
    profile_obj, _ = CustomerProfile.objects.get_or_create(user=user)
    profile_url = reverse("customer:profile")

    tab = request.GET.get("tab", "personal")
    if tab not in ("personal", "address", "cards", "orders"):
        tab = "personal"

    editing = request.GET.get("edit") == "1"
    form_type = request.POST.get("form_type") if request.method == "POST" else None
    address_target = ""
    address_obj = profile_obj
    if form_type == "address" or (tab == "address" and editing):
        address_target = request.POST.get("address_target", "") if form_type == "address" else request.GET.get("address_target", "")
        if address_target == "new":
            address_obj = DeliveryAddress(profile=profile_obj)
        elif address_target:
            if not address_target.isascii() or not address_target.isdecimal() or len(address_target) > 18:
                raise Http404
            address_obj = get_object_or_404(profile_obj.delivery_addresses, pk=int(address_target))

    personal_form = PersonalForm(user=user, profile=profile_obj)
    address_form = AddressForm(profile=address_obj)

    if request.method == "POST":
        if form_type == "personal":
            tab = "personal"
            editing = True
            personal_form = PersonalForm(
                request.POST, user=user, profile=profile_obj
            )
            if personal_form.is_valid():
                personal_form.save()
                return redirect(f"{profile_url}?tab=personal")

        elif form_type == "address":
            tab = "address"
            editing = True
            address_form = AddressForm(request.POST, profile=address_obj)
            if address_form.is_valid():
                if address_target == "new":
                    profile_obj.delivery_addresses.create(**address_form.cleaned_data)
                else:
                    address_form.save()
                return redirect(f"{profile_url}?tab=address")

    initials = (user.first_name[:1] + user.last_name[:1]).upper()

    return render(request, "customer/profile.html", {
        "tab": tab,
        "editing": editing,
        "profile": profile_obj,
        "personal_form": personal_form,
        "address_form": address_form,
        "address_target": address_target,
        "delivery_addresses": profile_obj.delivery_addresses.all() if tab == "address" else (),
        "initials": initials or user.get_username()[:2].upper(),
        "profile_url": profile_url,
        "logout_url": reverse("customer:logout"),
        "orders": my_orders(user) if tab == "orders" else (),
    })


def my_orders(user):
    customer = customer_of(user)
    if customer is None:
        return []
    return (FoodOrder.objects.filter(customer=customer)
            .select_related("restaurant").order_by("-order_date"))


@require_http_methods(["GET", "POST"])
def register(request):
    """Customer sign-up: creates a customer account and logs it in."""
    if request.user.is_authenticated:
        return redirect("customer:profile")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, gettext("Welcome to BiteBox!"))
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
            next_url = "customer:profile"  # never redirect to another site
        return redirect(next_url)
    return render(request, "customer/register.html", {"form": form, "next": request.GET.get("next", "")})
