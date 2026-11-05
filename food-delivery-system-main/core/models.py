
from django.db import models


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255)

    class Meta:
        db_table = "Customer"

    def __str__(self):
        return self.name


class Food_Item(models.Model):
    food_item_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "Food_Item"

    def __str__(self):
        return self.name


class Food_Order(models.Model):
    STATUS_CHOICES = [
        ("Placed", "Placed"),
        ("Preparing", "Preparing"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    ]

    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        db_column="customer_id",
        related_name="orders"
    )
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Placed"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    class Meta:
        db_table = "Food_Order"

    def __str__(self):
        return f"Order #{self.order_id}"


class Order_Item(models.Model):
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Food_Order,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="items"
    )
    food_item = models.ForeignKey(
        Food_Item,
        on_delete=models.PROTECT,
        db_column="food_item_id",
        related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "Order_Item"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "food_item"],
                name="unique_food_item_per_order"
            )
        ]

    def __str__(self):
        return f"{self.food_item.name} x {self.quantity}"


class Payment(models.Model):
    PAYMENT_METHODS = [
        ("Cash", "Cash"),
        ("Card", "Card"),
    ]

    PAYMENT_STATUSES = [
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
        ("Refunded", "Refunded"),
    ]

    payment_id = models.AutoField(primary_key=True)
    order = models.OneToOneField(
        Food_Order,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="payment"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default="Cash"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUSES,
        default="Pending"
    )
    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Payment"

    def __str__(self):
        return f"Payment #{self.payment_id}"


class Delivery(models.Model):
    DELIVERY_STATUSES = [
        ("Pending", "Pending"),
        ("Assigned", "Assigned"),
        ("Picked Up", "Picked Up"),
        ("Delivered", "Delivered"),
    ]

    delivery_id = models.AutoField(primary_key=True)
    order = models.OneToOneField(
        Food_Order,
        on_delete=models.PROTECT,
        db_column="order_id",
        related_name="delivery"
    )
    delivery_address = models.CharField(max_length=255)
    courier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUSES,
        default="Pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = "Delivery"

    def __str__(self):
        return f"Delivery #{self.delivery_id}"
