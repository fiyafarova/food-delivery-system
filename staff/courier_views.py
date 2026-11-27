"""Courier pages and courier management.

Owner: Sofiya.

- courier  -> /staff/courier/: my deliveries, buttons "Picked up" and "Delivered"
- manager  -> assigns a courier on the staff order page (staff/views.py: assign_courier)
- admin    -> /staff/couriers/: register couriers (temporary password, like employees)

The rules of every step are in core/delivery.py.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.delivery import DeliveryError, mark_delivered, mark_picked_up
from core.models import Delivery

from .account_views import NewAccountForm
from .permissions import admin_required, courier_required, is_courier

User = get_user_model()

ACTIVE = [Delivery.Status.ASSIGNED, Delivery.Status.PICKED_UP]


def start_page(user):
    """Couriers start on their deliveries, everyone else on the orders page."""
    return reverse("staff:courier") if is_courier(user) else reverse("staff:orders")


class StaffLoginView(LoginView):
    template_name = "staff/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):  # used when there is no ?next=
        return start_page(self.request.user)


def home(request):
    """/staff/ (the "Staff" link in the menu)."""
    return redirect(start_page(request.user))


def couriers_queryset():
    return User.objects.filter(role=User.Role.COURIER, is_active=True).order_by("username")


@courier_required
def deliveries(request):
    mine = (Delivery.objects.filter(courier=request.user)
            .select_related("order__customer", "order__restaurant"))
    return render(request, "staff/courier.html", {
        "active": mine.filter(delivery_status__in=ACTIVE).order_by("created_at"),
        "done": mine.filter(delivery_status=Delivery.Status.DELIVERED).order_by("-delivered_at")[:20],
    })


def _step(request, delivery_id, action, success):
    delivery = get_object_or_404(
        Delivery.objects.select_related("order"), pk=delivery_id, courier=request.user)  # only my deliveries
    try:
        action(delivery)
    except DeliveryError as error:
        messages.warning(request, str(error))
    else:
        messages.success(request, success)
    return redirect("staff:courier")


@courier_required
@require_POST
def picked_up(request, delivery_id):
    return _step(request, delivery_id, mark_picked_up, _("Order picked up. Have a good ride!"))


@courier_required
@require_POST
def delivered(request, delivery_id):
    return _step(request, delivery_id, mark_delivered, _("Order delivered."))


@admin_required
def couriers(request):
    """Admin's page: couriers + register a new courier."""
    form = NewAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        courier = form.create_user(role=User.Role.COURIER, created_by=request.user)
        messages.success(request, _("Courier %(name)s registered. Give them the temporary password; "
                                    "they will have to change it at first login.") % {"name": courier.username})
        return redirect("staff:couriers")

    people = couriers_queryset().annotate(
        active_count=Count("courier_deliveries", filter=Q(courier_deliveries__delivery_status__in=ACTIVE)),
        done_count=Count("courier_deliveries",
                         filter=Q(courier_deliveries__delivery_status=Delivery.Status.DELIVERED)),
    )
    return render(request, "staff/couriers.html", {"form": form, "couriers": people})


class AssignCourierForm(forms.Form):
    courier = forms.ModelChoiceField(queryset=User.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courier"].queryset = couriers_queryset()
