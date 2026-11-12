from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255)
    class Meta: db_table = "customer"

    def __str__(self):
        return self.name

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)
    class Meta: db_table = "food_item"

    def __str__(self):
        return self.name

class FoodOrder(models.Model):
    class Status(models.TextChoices):
        PLACED = "Placed"; PREPARING = "Preparing"
        DELIVERED = "Delivered"; CANCELLED = "Cancelled"
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class Meta: db_table = "food_order"

class OrderItem(models.Model):
    order = models.ForeignKey(FoodOrder, on_delete=models.PROTECT, related_name="items")
    food_item = models.ForeignKey(FoodItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta:
        db_table = "order_item"
        constraints = [models.UniqueConstraint(fields=["order", "food_item"], name="uq_order_food")]