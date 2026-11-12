from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .cart import (
    add_dish,
    build_cart,
    cart_payload,
    clear_cart,
    set_quantity,
)

def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def respond(request, status=200, extra=None):
    extra = extra or {}
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        payload = cart_payload(build_cart(request))
        payload.update(extra)
        return JsonResponse(payload, status=status)
    if extra.get("error"):
        messages.error(request, extra["error"])
    return redirect("customer:cart")


@require_GET
def cart_page(request):
    context = {
        "cart": build_cart(request),
        "menu_url": reverse("customer:menu"),
        "checkout_url": None,
    }
    return render(request, "customer/cart.html", context)


@require_POST
def cart_add(request):
    dish_id = parse_int(request.POST.get("dish_id"))
    if dish_id is None:
        return respond(request, 400, {"error": _("Invalid dish")})
    replace = request.POST.get("replace") == "1"
    status, info = add_dish(request, dish_id, replace)
    if status == "conflict":
        return respond(request, 409, {"conflict": True, **info})
    if status == "not_found":
        return respond(request, 404, {"error": _("Dish not found")})
    if status == "unavailable":
        return respond(request, 400, {"error": _("This dish is currently unavailable")})
    return respond(request)


@require_POST
def cart_update(request):
    dish_id = parse_int(request.POST.get("dish_id"))
    quantity = parse_int(request.POST.get("quantity"))
    if dish_id is None or quantity is None:
        return respond(request, 400, {"error": _("Invalid quantity")})
    if set_quantity(request, dish_id, quantity) == "not_found":
        return respond(request, 404, {"error": _("This dish is not in the cart")})
    return respond(request)


@require_POST
def cart_remove(request):
    dish_id = parse_int(request.POST.get("dish_id"))
    if dish_id is None:
        return respond(request, 400, {"error": _("Invalid dish")})
    set_quantity(request, dish_id, 0)
    return respond(request)


@require_POST
def cart_clear(request):
    clear_cart(request)
    return respond(request)