"""Customer-facing progress derived from the restaurant and delivery records."""
from django.utils.translation import gettext as _

from core.models import Delivery, FoodOrder


def tracking_state(order):
    delivery = getattr(order, "delivery", None)
    cancelled = order.status == FoodOrder.Status.CANCELLED
    delivered = order.status == FoodOrder.Status.DELIVERED or (
        delivery is not None and delivery.delivery_status == Delivery.Status.DELIVERED)
    stage = 0
    if order.status == FoodOrder.Status.PREPARING:
        stage = 1
    if delivery and delivery.delivery_status == Delivery.Status.ASSIGNED:
        stage = 2
    if delivery and delivery.delivery_status == Delivery.Status.PICKED_UP:
        stage = 3
    if delivered:
        stage = 4
    labels = [_("Order received"), _("Preparing"), _("Courier assigned"), _("On the way"), _("Delivered")]
    descriptions = [
        _("The restaurant has received your order."),
        _("Your meal is being prepared."),
        _("A courier has been assigned to your order."),
        _("The courier has picked up your order and is on the way."),
        _("Your order has been delivered."),
    ]
    return {
        "status": order.status,
        "can_cancel": order.status == FoodOrder.Status.PLACED,
        "label": _("Cancelled") if cancelled else labels[stage],
        "description": _("This order was cancelled.") if cancelled else descriptions[stage],
        "stage": stage,
        "cancelled": cancelled,
        "terminal": cancelled or delivered,
        "courier": delivery.courier_name or "" if delivery else "",
        "steps": [{"label": label, "done": not cancelled and index <= stage,
                   "current": not cancelled and index == stage}
                  for index, label in enumerate(labels)],
    }
