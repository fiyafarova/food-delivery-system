from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from core.models import FoodOrder


@login_required
@require_http_methods(["GET", "POST"])
def cancel_order(request, order_id):
    order = get_object_or_404(
        FoodOrder.objects.select_related("restaurant"),
        pk=order_id, customer__user=request.user,
    )
    if request.method == "POST":
        # The status condition is checked by PostgreSQL in the same write.
        changed = FoodOrder.objects.filter(
            pk=order.pk, customer__user=request.user, status=FoodOrder.Status.PLACED,
        ).update(status=FoodOrder.Status.CANCELLED)
        if not changed:
            order.refresh_from_db(fields=["status"])
            if order.status != FoodOrder.Status.CANCELLED:
                messages.warning(request, _("The restaurant has already started your order. Cancellation is no longer available."))
        return redirect("customer:order_status", order_id=order.pk)

    return render(request, "customer/cancel_order.html", {
        "order": order, "can_cancel": order.status == FoodOrder.Status.PLACED,
    })
