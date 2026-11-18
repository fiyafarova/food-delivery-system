from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import cart_views, views

app_name = "customer"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="customer:menu", permanent=False)),
    path("menu/", views.menu, name="menu"),
    path("cart/", cart_views.cart_page, name="cart"),
    path("cart/add/", cart_views.cart_add, name="cart_add"),
    path("cart/update/", cart_views.cart_update, name="cart_update"),
    path("cart/remove/", cart_views.cart_remove, name="cart_remove"),
    path("cart/clear/", cart_views.cart_clear, name="cart_clear"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/<int:order_id>/", views.order_status, name="order_status"),
    path("favorites/", views.favorites, name="favorites"),
    path("profile/", views.profile, name="profile"),
    path("login/", auth_views.LoginView.as_view(
        template_name="customer/login.html", redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="customer:menu"), name="logout"),  # POST only
]
