from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("orders/", views.orders, name="orders"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/status/", views.change_status, name="change_status"),
    path("menu/", views.menu, name="menu"),
    path("menu/<int:item_id>/toggle/", views.toggle_availability, name="toggle_availability"),
]