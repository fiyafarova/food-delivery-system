"""End-to-end test of the team milestone (weekly report, "Next team milestone"):

the customer orders 2 pizzas (2500) and a burger (1800), the order total 6800 is
saved in PostgreSQL, staff opens exactly this order and changes its status,
and the customer sees the new status.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from django.core.exceptions import ValidationError
from django.core.management import call_command

from restaurants.models import FoodItem, Restaurant
from staff.permissions import STAFF_GROUP

from .models import Customer, FoodOrder, OrderItem


def make_restaurant(name, owner_name):
    owner = get_user_model().objects.create_user(
        username=owner_name, email=f"{owner_name}@example.com", role="owner")
    return Restaurant.objects.create(name=name, owner=owner, address="Almaty")


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


class OrderMilestoneTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Aigerim", phone="+77010000001", address="Abay 1, Almaty")
        self.kitchen = make_restaurant("Test Kitchen", "owner1")
        self.pizza = FoodItem.objects.create(restaurant=self.kitchen, name="Pizza", price=2500)
        self.burger = FoodItem.objects.create(restaurant=self.kitchen, name="Burger", price=1800)
        self.sushi = FoodItem.objects.create(
            restaurant=make_restaurant("Nori Sushi", "owner2"), name="Sushi set", price=6900)

    def place_order(self):
        post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.pizza.pk, "quantity": 2})
        post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.burger.pk, "quantity": 1})
        return post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})

    def test_order_is_saved_with_total_6800(self):
        response = self.place_order()
        self.assertEqual(response.status_code, 201, response.content)
        order = FoodOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.total_amount, Decimal("6800.00"))
        self.assertEqual(order.restaurant, self.kitchen)
        self.assertEqual(order.status, "Placed")
        self.assertEqual(order.items.count(), 2)

        details = self.client.get(reverse("order_details", args=[order.pk])).json()
        self.assertEqual(details["total_amount"], "6800.00")

    def test_staff_sees_the_order_and_customer_sees_new_status(self):
        order_id = self.place_order().json()["order_id"]

        staff_client = Client()
        staff = get_user_model().objects.create_user(
            username="staff1", email="staff1@example.com", password="test-pass-123")
        staff.groups.add(Group.objects.get(name=STAFF_GROUP))
        self.kitchen.staff.add(staff)
        staff_client.force_login(staff)

        page = staff_client.get(reverse("staff:order_detail", args=[order_id]))
        self.assertEqual(page.context["total"], Decimal("6800.00"))
        staff_client.post(reverse("staff:change_status", args=[order_id]), {"status": "Preparing"})

        details = self.client.get(reverse("order_details", args=[order_id])).json()
        self.assertEqual(details["status"], "Preparing")

    def test_payment_and_delivery_for_the_order(self):
        order_id = self.place_order().json()["order_id"]
        payment = post_json(self.client, reverse("create_payment", args=[order_id]), {"payment_method": "Card"})
        self.assertEqual(payment.status_code, 201, payment.content)
        self.assertEqual(payment.json()["amount"], "6800.00")
        delivery = post_json(self.client, reverse("create_delivery", args=[order_id]), {})
        self.assertEqual(delivery.status_code, 201, delivery.content)
        self.assertEqual(delivery.json()["delivery_address"], "Abay 1, Almaty")

    def test_cart_accepts_dishes_from_one_restaurant_only(self):
        post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.pizza.pk})
        response = post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.sushi.pk})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["current_restaurant"], "Test Kitchen")
        self.assertEqual([i["name"] for i in self.client.get(reverse("view_cart")).json()["items"]], ["Pizza"])

        # "replace": true empties the cart and starts it with the new restaurant
        response = post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.sushi.pk, "replace": True})
        self.assertEqual(response.status_code, 200)
        cart = self.client.get(reverse("view_cart")).json()
        self.assertEqual([i["name"] for i in cart["items"]], ["Sushi set"])

    def test_customer_site_cart_and_api_cart_are_the_same(self):
        self.client.post(reverse("customer:cart_add"), {"dish_id": self.pizza.pk})  # Dilnaz's page
        cart = self.client.get(reverse("view_cart")).json()                          # Aksunkar's API
        self.assertEqual([(i["name"], i["quantity"]) for i in cart["items"]], [("Pizza", 1)])
        response = post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["total_amount"], "2500.00")

    def test_empty_cart_cannot_be_ordered(self):
        response = post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})
        self.assertEqual(response.status_code, 400)


class DatabaseRulesTests(TestCase):
    """CHECK / UNIQUE / RESTRICT rules from Task 9 are enforced by PostgreSQL itself."""

    def setUp(self):
        customer = Customer.objects.create(name="Dana", phone="+77010000003", address="Almaty")
        self.kitchen = make_restaurant("Test Kitchen", "owner1")
        self.pizza = FoodItem.objects.create(restaurant=self.kitchen, name="Pizza", price=2500)
        self.order = FoodOrder.objects.create(customer=customer, restaurant=self.kitchen)
        OrderItem.objects.create(order=self.order, food_item=self.pizza, quantity=1, unit_price=2500)

    def assert_rejected(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_price_must_be_positive(self):
        self.assert_rejected(lambda: FoodItem.objects.create(restaurant=self.kitchen, name="Free", price=0))

    def test_unknown_status_is_rejected(self):
        self.assert_rejected(lambda: FoodOrder.objects.filter(pk=self.order.pk).update(status="Flying"))

    def test_same_dish_twice_in_one_order_is_rejected(self):
        self.assert_rejected(lambda: OrderItem.objects.create(
            order=self.order, food_item=self.pizza, quantity=2, unit_price=2500))

    def test_order_line_must_be_from_the_order_restaurant(self):
        sushi = FoodItem.objects.create(restaurant=make_restaurant("Nori Sushi", "owner2"), name="Sushi", price=3000)
        with self.assertRaises(ValidationError):
            OrderItem.objects.create(order=self.order, food_item=sushi, quantity=1, unit_price=3000)

    def test_restaurant_with_dishes_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.kitchen.delete()

    def test_dish_used_in_an_order_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.pizza.delete()


class SeedDemoTests(TestCase):
    def test_seed_demo_creates_darya_orders_and_can_run_twice(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        call_command("seed_demo", stdout=open("/dev/null", "w"))  # no duplicates
        self.assertEqual(Restaurant.objects.count(), 3)
        self.assertEqual(FoodOrder.objects.count(), 4)
        totals = {o.restaurant.name + " " + o.status: o.total_amount for o in FoodOrder.objects.all()}
        self.assertEqual(totals, {
            "Casa Pizza Delivered": Decimal("6200.00"),
            "Dastarkhan Preparing": Decimal("4000.00"),
            "Urban Burger Placed": Decimal("3300.00"),
            "Dastarkhan Cancelled": Decimal("2100.00"),
        })
