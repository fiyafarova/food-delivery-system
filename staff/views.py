"""Restaurant staff pages: orders, order details, status change, menu availability.

Owner: Sofiya.

Orders now come from the database (core.models.FoodOrder / OrderItem).
The menu availability page still uses the in-memory test data from
staff/test_data.py (it resets when the server restarts).
TODO: staff login and role check (Group "Restaurant staff").
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import FoodOrder

from .test_data import make_menu

STATUSES = ["Placed", "Preparing", "Delivered", "Cancelled"]

# Allowed status changes (proposal: the team must confirm these rules).
# Delivered and Cancelled are final: no further changes.
TRANSITIONS = {
    "Placed": ["Preparing", "Cancelled"],
    "Preparing": ["Delivered", "Cancelled"],
    "Delivered": [],
    "Cancelled": [],
}

# Bootstrap colour of the status badge
BADGES = {
    "Placed": "secondary",
    "Preparing": "warning",
    "Delivered": "success",
    "Cancelled": "danger",
}

MENU = make_menu()


def reset_test_data():
    """Restore the original menu test data (used by the tests)."""
    MENU[:] = make_menu()


def find_order(order_id):
    """Return the order from the database or raise 404."""
    return get_object_or_404(
        FoodOrder.objects.select_related("customer").prefetch_related("items__food_item"),
        pk=order_id,
    )


def order_total(order):
    """The total is calculated from the order lines: sum of quantity * unit_price."""
    return sum(line.quantity * line.unit_price for line in order.items.all())


def orders(request):
    status = request.GET.get("status", "")
    queryset = FoodOrder.objects.select_related("customer").prefetch_related("items")
    if status in STATUSES:
        queryset = queryset.filter(status=status)

    # newest first (a bigger id means a newer order)
    shown = [
        {
            "id": order.id,
            "customer": order.customer.name,
            "total": order_total(order),
            "status": order.status,
            "badge": BADGES.get(order.status, "secondary"),
        }
        for order in queryset.order_by("-id")
    ]
    return render(request, "staff/orders.html", {
        "orders": shown,
        "statuses": STATUSES,
        "current_status": status,
    })


def order_detail(request, order_id):
    order = find_order(order_id)
    lines = [
        {
            "name": line.food_item.name,
            "unit_price": line.unit_price,
            "quantity": line.quantity,
            "line_total": line.quantity * line.unit_price,
        }
        for line in order.items.all()
    ]
    order_data = {
        "id": order.id,
        "status": order.status,
        "customer": order.customer.name,
        "phone": order.customer.phone,
        "address": order.customer.address,
    }
    return render(request, "staff/order_detail.html", {
        "order": order_data,
        "lines": lines,
        "total": order_total(order),
        "badge": BADGES.get(order.status, "secondary"),
        "next_statuses": TRANSITIONS.get(order.status, []),
    })


@require_POST
def change_status(request, order_id):
    order = find_order(order_id)
    new_status = request.POST.get("status", "")

    if new_status not in STATUSES:
        messages.warning(request, _("Unknown status."))
    elif new_status not in TRANSITIONS.get(order.status, []):
        messages.warning(request, _("This status change is not allowed."))
    else:
        order.status = new_status
        order.save(update_fields=["status"])
        messages.success(request, _("Order status changed."))
    return redirect("staff:order_detail", order_id=order_id)


def menu(request):
    return render(request, "staff/menu.html", {"items": MENU})


@require_POST
def toggle_availability(request, item_id):
    for item in MENU:
        if item["id"] == item_id:
            item["is_available"] = not item["is_available"]
            messages.success(request, _("Availability changed."))
            return redirect("staff:menu")
    raise Http404("Dish not found")