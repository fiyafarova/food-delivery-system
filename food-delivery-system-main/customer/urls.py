from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "customer"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="customer:menu", permanent=False)),
    path("menu/", views.menu, name="menu"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/<int:order_id>/", views.order_status, name="order_status"),
]
