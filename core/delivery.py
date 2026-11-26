"""Delivery rules: assign a courier, "picked up", "delivered".

Owner: Sofiya. Used by the staff pages (staff/views.py, staff/courier_views.py);
the JSON API in core/views.py can call the same functions.

Path of one order:

    order status:     Placed / Preparing ----------------------------> Delivered
    delivery status:  (none) -> Assigned -> Picked Up -> Delivered
                      manager    courier    courier (also sets the order to Delivered)

- A manager assigns a courier while the order is Placed or Preparing.
  The courier can be changed until they pick the order up.
- The courier picks the order up only when the kitchen is preparing it (order "Preparing").
- A cancelled order cannot be assigned, picked up or delivered.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Delivery, FoodOrder

ASSIGNABLE_ORDER_STATUSES = [FoodOrder.Status.PLACED, FoodOrder.Status.PREPARING]


class DeliveryError(Exception):
    """A delivery step that is not allowed right now; the message is shown to the user."""


def courier_display_name(user):
    return user.get_full_name() or user.username


def can_assign(order):
    delivery = getattr(order, "delivery", None)
    open_delivery = delivery is None or delivery.delivery_status in (
        Delivery.Status.PENDING, Delivery.Status.ASSIGNED)
    return order.status in ASSIGNABLE_ORDER_STATUSES and open_delivery


@transaction.atomic
def assign_courier(order, courier):
    """Create the delivery (if there is none yet) and give it to this courier."""
    if order.status not in ASSIGNABLE_ORDER_STATUSES:
        raise DeliveryError(_("A courier can be assigned only to a placed or preparing order."))
    delivery, _created = Delivery.objects.select_for_update().get_or_create(
        order=order, defaults={"delivery_address": order.customer.address})
    if delivery.delivery_status not in (Delivery.Status.PENDING, Delivery.Status.ASSIGNED):
        raise DeliveryError(_("The courier has already picked up this order."))
    delivery.courier = courier
    delivery.courier_name = courier_display_name(courier)
    delivery.delivery_status = Delivery.Status.ASSIGNED
    delivery.save(update_fields=["courier", "courier_name", "delivery_status"])
    return delivery


@transaction.atomic
def mark_picked_up(delivery):
    order = delivery.order
    if delivery.delivery_status != Delivery.Status.ASSIGNED:
        raise DeliveryError(_("This delivery cannot be picked up now."))
    if order.status != FoodOrder.Status.PREPARING:
        raise DeliveryError(_("The restaurant has not started preparing this order yet."))
    delivery.delivery_status = Delivery.Status.PICKED_UP
    delivery.picked_up_at = timezone.now()
    delivery.save(update_fields=["delivery_status", "picked_up_at"])
    return delivery


@transaction.atomic
def mark_delivered(delivery):
    order = delivery.order
    if delivery.delivery_status != Delivery.Status.PICKED_UP:
        raise DeliveryError(_("Pick the order up first."))
    if order.status == FoodOrder.Status.CANCELLED:
        raise DeliveryError(_("This order was cancelled."))
    finish(delivery)
    return delivery


def finish(delivery):
    """Delivery and order become Delivered (also used when staff close the order themselves)."""
    delivery.delivery_status = Delivery.Status.DELIVERED
    delivery.delivered_at = delivery.delivered_at or timezone.now()
    delivery.save(update_fields=["delivery_status", "delivered_at"])
    order = delivery.order
    if order.status != FoodOrder.Status.DELIVERED:
        order.status = FoodOrder.Status.DELIVERED
        order.save(update_fields=["status"])
