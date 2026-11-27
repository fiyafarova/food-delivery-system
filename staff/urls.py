from django.contrib.auth import views as auth_views
from django.urls import path

from . import account_views, courier_views, views

app_name = "staff"

urlpatterns = [
    path("login/", courier_views.StaffLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="staff:login"), name="logout"),  # POST only
    path("password/", account_views.ChangePasswordView.as_view(), name="password_change"),
    path("team/", account_views.team, name="team"),
    path("team/<int:restaurant_id>/remove/<int:user_id>/", account_views.team_remove, name="team_remove"),
    path("managers/", account_views.managers, name="managers"),
    path("", courier_views.home, name="home"),
    path("couriers/", courier_views.couriers, name="couriers"),
    path("courier/", courier_views.deliveries, name="courier"),
    path("courier/<int:delivery_id>/picked-up/", courier_views.picked_up, name="courier_picked_up"),
    path("courier/<int:delivery_id>/delivered/", courier_views.delivered, name="courier_delivered"),
    path("orders/", views.orders, name="orders"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/status/", views.change_status, name="change_status"),
    path("orders/<int:order_id>/courier/", views.assign_courier, name="assign_courier"),
    path("menu/", views.menu, name="menu"),
    path("menu/<int:item_id>/toggle/", views.toggle_availability, name="toggle_availability"),
]
