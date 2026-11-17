
from django.db import models


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255)

    class Meta:
        db_table = "customer"
        managed = False

    def __str__(self):
        return self.name


class FoodItem(models.Model):
    food_item_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "food_item"
        managed = False

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
        db_column="customer_id"
    )
    order_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLACED
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "food_order"
        managed = False

    def __str__(self):
        return f"{self.order_date} {self.customer}"


class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        FoodOrder,
        on_delete=models.PROTECT,
        related_name="items",
        db_column="order_id"
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.PROTECT,
        db_column="food_item_id"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_item"
        managed = False

    def __str__(self):
        return f"{self.order.customer} {self.food_item}"
