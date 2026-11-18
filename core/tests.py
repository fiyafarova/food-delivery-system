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

from staff.permissions import STAFF_GROUP

from .models import Customer, FoodItem, FoodOrder, OrderItem


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


class OrderMilestoneTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Aigerim", phone="+77010000001", address="Abay 1, Almaty")
        self.pizza = FoodItem.objects.create(name="Pizza", price=2500, category="Main")
        self.burger = FoodItem.objects.create(name="Burger", price=1800, category="Main")

    def place_order(self):
        post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.pizza.pk, "quantity": 2})
        post_json(self.client, reverse("add_to_cart"), {"food_item_id": self.burger.pk, "quantity": 1})
        return post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})

    def test_order_is_saved_with_total_6800(self):
        response = self.place_order()
        self.assertEqual(response.status_code, 201, response.content)
        order = FoodOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.total_amount, Decimal("6800.00"))
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

    def test_empty_cart_cannot_be_ordered(self):
        response = post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})
        self.assertEqual(response.status_code, 400)


class DatabaseRulesTests(TestCase):
    """CHECK / UNIQUE / RESTRICT rules from Task 9 are enforced by PostgreSQL itself."""

    def setUp(self):
        customer = Customer.objects.create(name="Dana", phone="+77010000003", address="Almaty")
        self.pizza = FoodItem.objects.create(name="Pizza", price=2500, category="Main")
        self.order = FoodOrder.objects.create(customer=customer)
        OrderItem.objects.create(order=self.order, food_item=self.pizza, quantity=1, unit_price=2500)

    def assert_rejected(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_price_must_be_positive(self):
        self.assert_rejected(lambda: FoodItem.objects.create(name="Free", price=0, category="X"))

    def test_unknown_status_is_rejected(self):
        self.assert_rejected(lambda: FoodOrder.objects.filter(pk=self.order.pk).update(status="Flying"))

    def test_same_dish_twice_in_one_order_is_rejected(self):
        self.assert_rejected(lambda: OrderItem.objects.create(
            order=self.order, food_item=self.pizza, quantity=2, unit_price=2500))

    def test_dish_used_in_an_order_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.pizza.delete()
