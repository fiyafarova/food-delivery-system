"""Demo data for the class demo (replaces core/fixtures/demo_data.json).

    python manage.py seed_demo

Darya's demo data (4 customers, 10 dishes, 4 orders) split into 3 restaurants,
so that every order is from one restaurant (the cart rule):

    Casa Pizza    order 1: 2 x Margherita Pizza + 2 x Cola        = 6200
    Dastarkhan    order 2: Beshbarmak + 2 x Black Tea             = 4000
                  order 4: Lagman (cancelled)                     = 2100
    Urban Burger  order 3: Cheeseburger + French Fries + Cola     = 3300

Restaurants belong to owner_demo. Demo employees (if they exist) get their restaurants:
staff_demo -> Casa Pizza, staff2_demo -> Urban Burger + Dastarkhan.
customer_demo / customer2_demo (if they exist) get the orders of Aigerim / Dias.
Safe to run again: existing rows are reused, nothing is duplicated.
"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Customer, FoodOrder, OrderItem
from restaurants.models import Category, FoodItem, Restaurant

ALMATY = ZoneInfo("Asia/Almaty")

RESTAURANTS = {
    "Casa Pizza": ("Pizza", "Almaty, Abay Ave 52", [
        ("Margherita Pizza", 2500, "Main course", True),
        ("Chicken Caesar Salad", 1900, "Salads", True),
        ("Tiramisu", 1500, "Desserts", False),
        ("Cola", 600, "Drinks", True),
    ]),
    "Urban Burger": ("Burgers", "Almaty, Satpayev St 30", [
        ("Cheeseburger", 1800, "Main course", True),
        ("French Fries", 900, "Sides", True),
        ("Cola", 600, "Drinks", True),
    ]),
    "Dastarkhan": ("Kazakh", "Almaty, Dostyk Ave 85", [
        ("Beshbarmak", 3200, "Main course", True),
        ("Lagman", 2100, "Main course", True),
        ("Samsa", 700, "Snacks", True),
        ("Black Tea", 400, "Drinks", True),
    ]),
}

CUSTOMERS = [
    ("Aigerim Sadykova", "+77010000001", "Almaty, Abay Ave 10, apt 12"),
    ("Dias Nurlanov", "+77010000002", "Almaty, Satpayev St 22, apt 5"),
    ("Madina Kenzhebayeva", "+77010000003", "Almaty, Dostyk Ave 90, apt 41"),
    ("Alikhan Bekov", "+77010000004", "Almaty, Tole Bi St 55, apt 8"),
]

ORDERS = [
    # customer phone, restaurant, status, date, [(dish, quantity)]
    ("+77010000001", "Casa Pizza", "Delivered", (2026, 11, 9, 13, 15), [("Margherita Pizza", 2), ("Cola", 2)]),
    ("+77010000002", "Dastarkhan", "Preparing", (2026, 11, 12, 12, 40), [("Beshbarmak", 1), ("Black Tea", 2)]),
    ("+77010000003", "Urban Burger", "Placed", (2026, 11, 12, 13, 5), [("Cheeseburger", 1), ("French Fries", 1), ("Cola", 1)]),
    ("+77010000001", "Dastarkhan", "Cancelled", (2026, 11, 10, 19, 30), [("Lagman", 1)]),
]


class Command(BaseCommand):
    help = "Create demo restaurants, dishes, customers and orders (safe to run again)."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        owner, created = User.objects.get_or_create(
            username="owner_demo", defaults={"email": "owner_demo@example.com", "role": "owner"})
        if created:
            owner.set_unusable_password()  # create_demo_users gives it a password
            owner.save()

        dishes = {}
        for name, (cuisine, address, menu) in RESTAURANTS.items():
            restaurant, _ = Restaurant.objects.get_or_create(
                name=name, defaults={"owner": owner, "cuisine": cuisine, "address": address, "city": "Almaty"})
            for dish_name, price, category_name, available in menu:
                category, _ = Category.objects.get_or_create(name=category_name)
                dish, _ = FoodItem.objects.get_or_create(
                    restaurant=restaurant, name=dish_name,
                    defaults={"price": price, "category": category, "is_available": available})
                dishes[name, dish_name] = dish

        customers = {}
        for name, phone, address in CUSTOMERS:
            customers[phone], _ = Customer.objects.get_or_create(
                phone=phone, defaults={"name": name, "address": address})

        from staff.management.commands.create_demo_users import link_demo_customer, link_demo_staff
        for demo_user in User.objects.filter(username__in=["customer_demo", "customer2_demo"]):
            link_demo_customer(demo_user)
        for demo_user in User.objects.filter(username__in=["staff_demo", "staff2_demo"]):
            link_demo_staff(demo_user)

        new_orders = 0
        for phone, restaurant_name, status, date, lines in ORDERS:
            order_date = datetime(*date, tzinfo=ALMATY)
            customer = customers[phone]
            if FoodOrder.objects.filter(customer=customer, order_date=order_date).exists():
                continue
            restaurant = Restaurant.objects.get(name=restaurant_name)
            order = FoodOrder.objects.create(
                customer=customer, restaurant=restaurant, status=status, order_date=order_date)
            total = Decimal("0")
            for dish_name, quantity in lines:
                dish = dishes[restaurant_name, dish_name]
                OrderItem.objects.create(order=order, food_item=dish, quantity=quantity, unit_price=dish.price)
                total += dish.price * quantity
            order.total_amount = total
            order.save(update_fields=["total_amount"])
            new_orders += 1

        from staff.management.commands.create_demo_users import link_demo_courier
        for demo_user in User.objects.filter(username="courier_demo"):
            link_demo_courier(demo_user)  # demo order #2 -> courier_demo (if the account already exists)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {Restaurant.objects.count()} restaurants, {FoodItem.objects.count()} dishes, "
            f"{Customer.objects.count()} customers, {new_orders} new orders."))
