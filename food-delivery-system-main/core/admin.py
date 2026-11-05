

from django.contrib import admin
from .models import (
    Customer,
    Food_Item,
    Food_Order,
    Order_Item,
    Payment,
    Delivery,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "name", "phone", "address")
    search_fields = ("name", "phone")


@admin.register(Food_Item)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "food_item_id",
        "name",
        "price",
        "category",
        "is_available",
    )
    list_filter = ("category", "is_available")
    search_fields = ("name",)


@admin.register(Food_Order)
class FoodOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "customer",
        "order_date",
        "status",
        "total_amount",
    )
    list_filter = ("status",)
    search_fields = ("order_id", "customer__name")


@admin.register(Order_Item)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order_item_id",
        "order",
        "food_item",
        "quantity",
        "unit_price",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_id",
        "order",
        "amount",
        "payment_method",
        "payment_status",
        "payment_date",
    )
    list_filter = ("payment_method", "payment_status")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_id",
        "order",
        "courier_name",
        "delivery_status",
        "created_at",
    )
    list_filter = ("delivery_status",)
    search_fields = ("courier_name", "delivery_address")
