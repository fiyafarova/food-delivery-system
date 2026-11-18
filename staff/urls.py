from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name="staff/login.html",
        redirect_authenticated_user=True,
        next_page="staff:orders",  # used when there is no ?next=
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="staff:login"), name="logout"),  # POST only
    path("orders/", views.orders, name="orders"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/status/", views.change_status, name="change_status"),
    path("menu/", views.menu, name="menu"),
    path("menu/<int:item_id>/toggle/", views.toggle_availability, name="toggle_availability"),
]
