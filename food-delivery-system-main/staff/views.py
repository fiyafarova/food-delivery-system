"""Restaurant staff pages: orders, order details, status change, menu availability.

Owner: Sofiya.

Until the models are ready, data comes from staff/test_data.py and is kept in
memory (it resets when the server restarts).
TODO: staff login and role check (Group "Restaurant staff").
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .test_data import make_menu, make_orders

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

ORDERS = make_orders()
MENU = make_menu()


def reset_test_data():
    """Restore the original test data (used by the tests)."""
    ORDERS[:] = make_orders()
    MENU[:] = make_menu()


def find_order(order_id):
    for order in ORDERS:
        if order["id"] == order_id:
            return order
    raise Http404("Order not found")


def order_total(order):
    """The total is calculated from the order lines: sum of quantity * unit_price."""
    return sum(line["quantity"] * line["unit_price"] for line in order["items"])


def orders(request):
    status = request.GET.get("status", "")
    shown = []
    for order in ORDERS:
        if status in STATUSES and order["status"] != status:
            continue
        shown.append({**order, "total": order_total(order), "badge": BADGES[order["status"]]})
    # newest first (a bigger id means a newer order)
    shown.sort(key=lambda o: o["id"], reverse=True)
    return render(request, "staff/orders.html", {
        "orders": shown,
        "statuses": STATUSES,
        "current_status": status,
    })


def order_detail(request, order_id):
    order = find_order(order_id)
    lines = [{**line, "line_total": line["quantity"] * line["unit_price"]} for line in order["items"]]
    return render(request, "staff/order_detail.html", {
        "order": order,
        "lines": lines,
        "total": order_total(order),
        "badge": BADGES[order["status"]],
        "next_statuses": TRANSITIONS[order["status"]],
    })


@require_POST
def change_status(request, order_id):
    order = find_order(order_id)
    new_status = request.POST.get("status", "")

    if new_status not in STATUSES:
        messages.warning(request, _("Unknown status."))
    elif new_status not in TRANSITIONS[order["status"]]:
        messages.warning(request, _("This status change is not allowed."))
    else:
        order["status"] = new_status
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