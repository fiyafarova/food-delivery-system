
"""Data models of the order process (Task 9 design).

Merged version agreed by the team:
- fields, Payment and Delivery: Aksunkar (branch back-1)
- class names, table names and CHECK rules: Darya (branch database-sql, database/*.sql)
- dishes come from restaurants.FoodItem (Sayazhan); one order = one restaurant

Rules kept from Task 9:
- foreign keys use on_delete=PROTECT (ON DELETE RESTRICT in SQL)
- UNIQUE(order, food_item) on the order line
- order status: Placed / Preparing / Delivered / Cancelled

db_default = the same DEFAULT as in the SQL script, so plain SQL inserts also work.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.utils import timezone


class Promo(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "Percentage"
        FIXED = "Fixed"

    code = models.CharField(max_length=30, unique=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices
    )
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)


    class Meta:
        db_table = "promo"
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_value__gt=0),
                name="promo_discount_positive"
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(discount_type="Percentage")
                    | Q(discount_value__lte=100)
                ),
                name="promo_percentage_max_100"
            ),
        ]

    def __str__(self):
        return self.code


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer",
    )

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255)

    class Meta:
        db_table = "customer"

    def __str__(self):
        return self.name


class FoodOrder(models.Model):
    class Status(models.TextChoices):
        PLACED = "Placed"
        PREPARING = "Preparing"
        DELIVERED = "Delivered"
        CANCELLED = "Cancelled"

    order_id = models.AutoField(primary_key=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        db_column="customer_id",
        related_name="orders",
    )

    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        on_delete=models.PROTECT,
        db_column="restaurant_id",
        related_name="orders",
    )

    order_date = models.DateTimeField(
        default=timezone.now,
        db_default=Now(),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLACED,
        db_default=Status.PLACED,
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_default=0,
    )

    promo_code = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    class Meta:
        db_table = "food_order"
        indexes = [
            models.Index(
                fields=["order_date"],
                name="idx_food_order_order_date",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "Placed",
                        "Preparing",
                        "Delivered",
                        "Cancelled",
                    ]
                ),
                name="food_order_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="food_order_total_not_negative",
            ),
        ]

    def __str__(self):
        return f"Order #{self.order_id}"


class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)

    order = models.ForeignKey(
        FoodOrder,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="items",
    )

    food_item = models.ForeignKey(
        "restaurants.FoodItem",
        on_delete=models.PROTECT,
        db_column="food_item_id",
        related_name="order_items",
    )

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        db_table = "order_item"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "food_item"],
                name="uq_order_food",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="order_item_unit_price_not_negative",
            ),
        ]

    def clean(self):
        if self.food_item.restaurant_id != self.order.restaurant_id:
            raise ValidationError(
                "All dishes of an order must be from the order's restaurant."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.food_item.name} x {self.quantity}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "Cash"
        CARD = "Card"

    class Status(models.TextChoices):
        PENDING = "Pending"
        PAID = "Paid"
        FAILED = "Failed"
        REFUNDED = "Refunded"

    payment_id = models.AutoField(primary_key=True)

    order = models.OneToOneField(
        FoodOrder,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="payment",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="payment_amount_not_negative",
            ),
        ]

    def __str__(self):
        return f"Payment #{self.payment_id}"


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending"
        ASSIGNED = "Assigned"
        PICKED_UP = "Picked Up"
        DELIVERED = "Delivered"

    delivery_id = models.AutoField(primary_key=True)

    order = models.OneToOneField(
        FoodOrder,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="delivery",
    )

    # Courier account (User.role "courier") assigned by a manager; see core/delivery.py
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="courier_deliveries",
    )

    delivery_address = models.CharField(max_length=255)
    courier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    delivery_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)  # the courier pressed "Picked up"
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "delivery"

    def __str__(self):
        return f"Delivery #{self.delivery_id}"
