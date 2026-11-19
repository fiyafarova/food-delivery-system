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
from django.test import Client, TestCase, override_settings
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


def make_staff(username, restaurant):
    staff = get_user_model().objects.create_user(username=username, email=f"{username}@example.com")
    staff.groups.add(Group.objects.get(name=STAFF_GROUP))
    restaurant.staff.add(staff)
    return staff


class OrderMilestoneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="aigerim", email="aigerim@example.com")
        self.customer = Customer.objects.create(
            user=self.user, name="Aigerim", phone="+77010000001", address="Abay 1, Almaty")
        self.client.force_login(self.user)  # orders are placed by a logged-in customer
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
        staff_client = Client()
        staff_client.force_login(make_staff("staff2", self.kitchen))  # delivery is created by the restaurant
        delivery = post_json(staff_client, reverse("create_delivery", args=[order_id]), {})
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
        response = post_json(self.client, reverse("create_order"), {})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["total_amount"], "2500.00")

    def test_empty_cart_cannot_be_ordered(self):
        response = post_json(self.client, reverse("create_order"), {"customer_id": self.customer.pk})
        self.assertEqual(response.status_code, 400)


class CustomerAccountTests(TestCase):
    """Customer is linked to the account: a customer sees only their own orders."""

    def setUp(self):
        User = get_user_model()
        self.kitchen = make_restaurant("Test Kitchen", "owner1")
        self.pizza = FoodItem.objects.create(restaurant=self.kitchen, name="Pizza", price=2500)
        self.anna = User.objects.create_user(username="anna", email="anna@example.com")
        self.ben = User.objects.create_user(username="ben", email="ben@example.com")
        self.anna_client, self.ben_client = Client(), Client()
        self.anna_client.force_login(self.anna)
        self.ben_client.force_login(self.ben)

    def order_as(self, client, **data):
        post_json(client, reverse("add_to_cart"), {"food_item_id": self.pizza.pk})
        return post_json(client, reverse("create_order"), data)

    def test_first_order_creates_customer_for_the_account(self):
        response = self.order_as(self.anna_client, phone="+77011112233", address="Abay 5")
        self.assertEqual(response.status_code, 201, response.content)
        order = FoodOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.customer.user, self.anna)
        self.order_as(self.anna_client)  # second order: same Customer, no phone needed
        self.assertEqual(Customer.objects.filter(user=self.anna).count(), 1)
        self.assertEqual(FoodOrder.objects.filter(customer__user=self.anna).count(), 2)

    def test_phone_and_address_from_profile(self):
        from accounts.models import CustomerProfile
        CustomerProfile.objects.create(user=self.anna, phone="+77019998877", address="Satpaev 1")
        self.assertEqual(self.order_as(self.anna_client).status_code, 201)
        self.assertEqual(Customer.objects.get(user=self.anna).phone, "+77019998877")

    def test_first_order_without_phone_is_rejected(self):
        response = self.order_as(self.anna_client)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Phone and address", response.json()["error"])

    def test_someone_elses_phone_is_not_linked(self):
        Customer.objects.create(name="Old", phone="+77010000001", address="x")  # e.g. demo customer
        response = self.order_as(self.anna_client, phone="+77010000001", address="Abay 5")
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Customer.objects.get(phone="+77010000001").user)

    def test_guest_cannot_order_or_see_orders(self):
        response = self.order_as(Client())
        self.assertEqual(response.status_code, 401)
        order_id = self.order_as(self.anna_client, phone="+77011112233", address="Abay 5").json()["order_id"]
        self.assertEqual(Client().get(reverse("order_details", args=[order_id])).status_code, 401)

    def test_other_customer_cannot_see_the_order(self):
        order_id = self.order_as(self.anna_client, phone="+77011112233", address="Abay 5").json()["order_id"]
        anna_customer = Customer.objects.get(user=self.anna)
        # API
        self.assertEqual(self.anna_client.get(reverse("order_details", args=[order_id])).status_code, 200)
        self.assertEqual(self.ben_client.get(reverse("order_details", args=[order_id])).status_code, 404)
        self.assertEqual(self.ben_client.get(reverse("order_history", args=[anna_customer.pk])).status_code, 404)
        self.assertEqual(self.ben_client.get(reverse("my_orders")).json()["orders"], [])
        self.assertEqual(len(self.anna_client.get(reverse("my_orders")).json()["orders"]), 1)
        # website
        self.assertEqual(self.anna_client.get(reverse("customer:order_status", args=[order_id])).status_code, 200)
        self.assertEqual(self.ben_client.get(reverse("customer:order_status", args=[order_id])).status_code, 404)
        profile = self.anna_client.get(reverse("customer:profile"), {"tab": "orders"})
        self.assertEqual([o.pk for o in profile.context["orders"]], [order_id])

    def test_customer_cannot_change_status(self):
        order_id = self.order_as(self.anna_client, phone="+77011112233", address="Abay 5").json()["order_id"]
        response = post_json(self.anna_client, reverse("update_order_status", args=[order_id]), {"status": "Delivered"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(FoodOrder.objects.get(pk=order_id).status, "Placed")

        staff_client = Client()
        staff_client.force_login(make_staff("cook", self.kitchen))
        response = post_json(staff_client, reverse("update_order_status", args=[order_id]), {"status": "Preparing"})
        self.assertEqual(response.status_code, 200)

    def test_customer_login_page_and_redirect(self):
        response = Client().get(reverse("customer:profile"))
        self.assertRedirects(response, reverse("customer:login") + "?next=" + reverse("customer:profile"))
        self.assertEqual(Client().get(reverse("customer:login")).status_code, 200)


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


@override_settings(DEBUG=True)  # create_demo_users runs only with DEBUG on
class SeedDemoTests(TestCase):
    def test_seed_demo_creates_darya_orders_and_can_run_twice(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        call_command("seed_demo", stdout=open("/dev/null", "w"))  # no duplicates
        self.assertEqual(Restaurant.objects.count(), 3)
        self.assertEqual(FoodOrder.objects.count(), 4)
        call_command("create_demo_users", "--password", "demo-pass-123", stdout=open("/dev/null", "w"))
        self.assertEqual(FoodOrder.objects.filter(customer__user__username="customer_demo").count(), 2)
        self.assertEqual(FoodOrder.objects.filter(customer__user__username="customer2_demo").count(), 1)
        totals = {o.restaurant.name + " " + o.status: o.total_amount for o in FoodOrder.objects.all()}
        self.assertEqual(totals, {
            "Casa Pizza Delivered": Decimal("6200.00"),
            "Dastarkhan Preparing": Decimal("4000.00"),
            "Urban Burger Placed": Decimal("3300.00"),
            "Dastarkhan Cancelled": Decimal("2100.00"),
        })

    def staff_view(self, username):
        client = Client()
        client.force_login(get_user_model().objects.get(username=username))
        orders = client.get(reverse("staff:orders")).context["orders"]
        return sorted(o["restaurant"] for o in orders)

    def test_each_demo_employee_sees_only_their_restaurants(self):
        call_command("create_demo_users", stdout=open("/dev/null", "w"))  # users first ...
        call_command("seed_demo", stdout=open("/dev/null", "w"))          # ... then data: order does not matter
        User = get_user_model()
        self.assertEqual({r.name for r in User.objects.get(username="staff_demo").staff_restaurants.all()},
                         {"Casa Pizza"})
        self.assertEqual({r.name for r in User.objects.get(username="staff2_demo").staff_restaurants.all()},
                         {"Urban Burger", "Dastarkhan"})
        self.assertEqual(self.staff_view("staff_demo"), ["Casa Pizza"])
        self.assertEqual(self.staff_view("staff2_demo"), ["Dastarkhan", "Dastarkhan", "Urban Burger"])
        self.assertEqual(len(self.staff_view("owner_demo")), 4)
        self.assertEqual(len(self.staff_view("admin_demo")), 4)
        self.assertTrue(User.objects.get(username="admin_demo").check_password("BiteBox-demo-2026"))

    def test_demo_users_refused_when_debug_is_off(self):
        from django.core.management.base import CommandError
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("create_demo_users", stdout=open("/dev/null", "w"))
