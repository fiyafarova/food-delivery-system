"""Restaurant staff pages: orders, order details, status change, menu availability.

Owner: Sofiya.

Data comes from the database: orders from core.models (FoodOrder, OrderItem),
dishes from restaurants.models.FoodItem.
Every view is protected by @staff_required (see staff/permissions.py):
only employees ("Restaurant staff" group), owners/admins and superusers can open them,
and each user sees only the restaurants returned by restaurants_for(user).
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import FoodOrder
from restaurants.models import FoodItem

from .permissions import restaurants_for, staff_required

STATUSES = [choice for choice, _label in FoodOrder.Status.choices]

# Allowed status changes (agreed in the weekly report, section 2).
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


def visible_orders(user):
    return FoodOrder.objects.filter(restaurant__in=restaurants_for(user))


def find_order(user, order_id):
    """Return the order with its customer and lines, or 404 (also for other restaurants' orders)."""
    return get_object_or_404(
        visible_orders(user).select_related("customer", "restaurant").prefetch_related("items__food_item"),
        pk=order_id,
    )


def order_total(order):
    """The total is calculated from the order lines: sum of quantity * unit_price."""
    return sum(line.quantity * line.unit_price for line in order.items.all())


@staff_required
def orders(request):
    status = request.GET.get("status", "")
    queryset = visible_orders(request.user).select_related("customer", "restaurant").prefetch_related("items")
    if status in STATUSES:
        queryset = queryset.filter(status=status)

    # newest first (a bigger id means a newer order)
    shown = [
        {
            "id": order.order_id,
            "customer": order.customer.name,
            "restaurant": order.restaurant.name,
            "total": order_total(order),
            "status": order.status,
            "badge": BADGES.get(order.status, "secondary"),
        }
        for order in queryset.order_by("-order_id")
    ]
    return render(request, "staff/orders.html", {
        "orders": shown,
        "statuses": STATUSES,
        "current_status": status,
    })


@staff_required
def order_detail(request, order_id):
    order = find_order(request.user, order_id)
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
        "id": order.order_id,
        "status": order.status,
        "customer": order.customer.name,
        "restaurant": order.restaurant.name,
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


@staff_required
@require_POST
def change_status(request, order_id):
    order = get_object_or_404(visible_orders(request.user), pk=order_id)
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


@staff_required
def menu(request):
    items = (FoodItem.objects.filter(restaurant__in=restaurants_for(request.user))
             .select_related("restaurant", "category").order_by("restaurant__name", "name"))
    return render(request, "staff/menu.html", {"items": items})


@staff_required
@require_POST
def toggle_availability(request, item_id):
    item = get_object_or_404(FoodItem.objects.filter(restaurant__in=restaurants_for(request.user)), pk=item_id)
    item.is_available = not item.is_available
    item.save(update_fields=["is_available"])
    messages.success(request, _("Availability changed."))
    return redirect("staff:menu")
