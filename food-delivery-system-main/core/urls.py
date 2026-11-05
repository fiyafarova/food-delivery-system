from django.urls import path, include
from django.urls import path

from . import views

urlpatterns = [
    # Shopping cart
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/", views.update_cart, name="update_cart"),
    path("cart/remove/", views.remove_from_cart, name="remove_from_cart"),

    # Orders
    path("orders/create/", views.create_order, name="create_order"),
    path("orders/<int:order_id>/", views.order_details, name="order_details"),
    path(
        "orders/<int:order_id>/status/",
        views.update_order_status,
        name="update_order_status"
    ),
    path(
        "customers/<int:customer_id>/orders/",
        views.order_history,
        name="order_history"
    ),
]
# Payment
path(
    "orders/<int:order_id>/payment/",
    views.create_payment,
    name="create_payment"
),
path(
    "payments/<int:payment_id>/status/",
    views.update_payment_status,
    name="update_payment_status"
),
path(
    "orders/<int:order_id>/payment/details/",
    views.payment_details,
    name="payment_details"
),

# Delivery
path(
    "orders/<int:order_id>/delivery/",
    views.create_delivery,
    name="create_delivery"
),
path(
    "deliveries/<int:delivery_id>/status/",
    views.update_delivery_status,
    name="update_delivery_status"
),
path(
    "orders/<int:order_id>/delivery/details/",
    views.delivery_details,
    name="delivery_details"
),