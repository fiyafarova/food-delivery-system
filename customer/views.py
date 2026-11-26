from core.promotions import PROMOTIONS

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

from accounts.models import CustomerProfile, DeliveryAddress, SavedCard
from restaurants.models import Restaurant

from core.access import customer_of
from core.models import FoodOrder

from .cards import SELECTED_CARD_KEY
from .tracking import tracking_state
from .cart import build_cart
from .forms import AddressForm, PersonalForm, SignUpForm, SavedCardForm

@ensure_csrf_cookie
def menu(request):
    restaurants = list(Restaurant.objects.filter(is_open=True).prefetch_related("food_items"))
    cart = build_cart(request)
    active_order = None
    if request.user.is_authenticated:
        active_order = FoodOrder.objects.filter(
            customer__user=request.user,
            status__in=[FoodOrder.Status.PLACED, FoodOrder.Status.PREPARING],
        ).exclude(delivery__delivery_status="Delivered").select_related(
            "restaurant", "delivery").order_by("-order_date", "-pk").first()
    return render(request, "customer/menu.html", {
        "active_order": active_order,
        "active_tracking": tracking_state(active_order) if active_order else None,
        "restaurants": restaurants,
        "cuisines": sorted({restaurant.cuisine for restaurant in restaurants if restaurant.cuisine}),
        "cart_dish_ids": {line["id"] for line in cart["lines"]},
    })


def cart(request):
    return render(request, "customer/cart.html")


CHECKOUT_DRAFT_KEY = "checkout_draft"
CHECKOUT_FIELD_LIMITS = {"city": 100, "phone": 20, "address": 255, "comment": 500}


@login_required
@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = build_cart(request)
    cards = request.user.saved_cards.all()
    selected_card = cards.filter(pk=request.session.get(SELECTED_CARD_KEY)).first()
    card_context = {"saved_cards": cards, "selected_card": selected_card, "promotions": PROMOTIONS}
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
            return render(request, "customer/checkout.html", {"cart": cart, "draft": draft, "draft_error": True, **card_context}, status=400)
        request.session[CHECKOUT_DRAFT_KEY] = draft
        if ajax:
            return JsonResponse({"saved": True})
        messages.success(request, gettext("Changes saved"))
        return redirect("customer:checkout")

    draft = request.session.get(CHECKOUT_DRAFT_KEY)
    if draft is None:
        profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
        draft = {field: getattr(profile, field, "") for field in CHECKOUT_FIELD_LIMITS}
    return render(request, "customer/checkout.html", {"cart": cart, "draft": draft, **card_context})


@login_required
def order_status(request, order_id):
    """A customer sees only their own order (someone else's order -> 404)."""
    customer = customer_of(request.user)
    order = get_object_or_404(
        FoodOrder.objects.select_related("restaurant", "delivery", "payment_card").prefetch_related("items__food_item"),
        pk=order_id, customer=customer,
    ) if customer else None
    if order is None:
        raise Http404
    tracking = tracking_state(order)
    if request.GET.get("tracking") == "1":
        response = JsonResponse(tracking)
        response["Cache-Control"] = "no-store"
        return response
    lines = [
        {"name": line.food_item.name, "quantity": line.quantity,
         "unit_price": line.unit_price, "total": line.quantity * line.unit_price}
        for line in order.items.all()
    ]
    return render(request, "customer/order_status.html", {
        "order": order,
        "tracking": tracking,
        "lines": lines,
    })

@ensure_csrf_cookie
def favorites(request):
    cart = build_cart(request)
    return render(request, "customer/favorites.html", {
        "cart_dish_ids": [str(line["id"]) for line in cart["lines"]],
    })



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
    card_form = SavedCardForm(request.POST if form_type == "card" else None)

    if request.method == "POST":
        if form_type == "card":
            tab = "cards"
            if card_form.is_valid():
                card = card_form.save(commit=False)
                card.user = user
                card.save()
                return redirect(f"{profile_url}?tab=cards")
        elif form_type == "delete_card":
            card_id = request.POST.get("card_id", "")
            if not card_id.isascii() or not card_id.isdecimal() or len(card_id) > 18:
                raise Http404
            card = get_object_or_404(SavedCard, user=user, pk=card_id)
            if request.session.get(SELECTED_CARD_KEY) == card.pk:
                request.session.pop(SELECTED_CARD_KEY, None)
            card.delete()
            return redirect(f"{profile_url}?tab=cards")
        elif form_type == "personal":
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
        "saved_cards": user.saved_cards.all() if tab == "cards" else (),
        "card_form": card_form,
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
