from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Customer, FoodOrder, OrderItem
from restaurants.models import FoodItem, Restaurant

from .permissions import STAFF_GROUP

PASSWORD = "test-pass-123"


def make_user(username, staff=False, **extra):
    user = get_user_model().objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, **extra)
    if staff:
        user.groups.add(Group.objects.get(name=STAFF_GROUP))
        user.staff_restaurants.add(*Restaurant.objects.filter(name="Test Kitchen"))
    return user


def make_test_data():
    """Orders and dishes in the database.

    Restaurant "Test Kitchen" (owner owner0): orders 101 Placed (2 pizzas + 1 burger = 6800),
    102 Preparing, 103 Delivered, 104 Cancelled. Dishes: 1 Pizza, 2 Burger, 3 Cola (not available).
    Restaurant "Other Place" (owner owner9): order 201, dish 9 Soup.
    Staff users made by make_user(staff=True) work in "Test Kitchen" only.
    """
    owner = make_user("owner0", role="owner")
    kitchen = Restaurant.objects.create(name="Test Kitchen", owner=owner, address="Almaty")
    other = Restaurant.objects.create(name="Other Place", owner=make_user("owner9", role="owner"), address="Almaty")
    pizza = FoodItem.objects.create(pk=1, restaurant=kitchen, name="Pizza", price=2500)
    burger = FoodItem.objects.create(pk=2, restaurant=kitchen, name="Burger", price=1800)
    cola = FoodItem.objects.create(pk=3, restaurant=kitchen, name="Cola", price=600, is_available=False)
    soup = FoodItem.objects.create(pk=9, restaurant=other, name="Soup", price=1000)
    orders = [
        (101, kitchen, "Aigerim", "Placed", [(pizza, 2), (burger, 1)]),
        (102, kitchen, "Aidos", "Preparing", [(burger, 1)]),
        (103, kitchen, "Dana", "Delivered", [(pizza, 1)]),
        (104, kitchen, "Marat", "Cancelled", [(cola, 2)]),
        (201, other, "Erlan", "Placed", [(soup, 1)]),
    ]
    for number, (order_id, restaurant, name, status, lines) in enumerate(orders, start=1):
        customer = Customer.objects.create(name=name, phone=f"+7700000000{number}", address="Almaty")
        order = FoodOrder.objects.create(pk=order_id, customer=customer, restaurant=restaurant, status=status)
        for food, quantity in lines:
            OrderItem.objects.create(order=order, food_item=food, quantity=quantity, unit_price=food.price)


def status_of(order_id):
    return FoodOrder.objects.get(pk=order_id).status


def is_available(item_id):
    return FoodItem.objects.get(pk=item_id).is_available


class StaffTests(TestCase):
    """Staff pages work with orders and dishes from the database (see make_test_data)."""

    def setUp(self):
        make_test_data()  # every test starts from the same data
        self.client.force_login(make_user("staff1", staff=True))

    def change(self, order_id, status):
        return self.client.post(reverse("staff:change_status", args=[order_id]), {"status": status})

    def test_orders_list_shows_all_orders_newest_first(self):
        response = self.client.get(reverse("staff:orders"))
        self.assertEqual([o["id"] for o in response.context["orders"]], [104, 103, 102, 101])

    def test_orders_can_be_filtered_by_status(self):
        response = self.client.get(reverse("staff:orders"), {"status": "Placed"})
        self.assertEqual([o["id"] for o in response.context["orders"]], [101])

    def test_unknown_filter_shows_all_orders(self):
        response = self.client.get(reverse("staff:orders"), {"status": "Nonsense"})
        self.assertEqual(len(response.context["orders"]), 4)  # only Test Kitchen orders

    def test_order_total_is_calculated_from_lines(self):
        response = self.client.get(reverse("staff:order_detail", args=[101]))
        self.assertEqual(response.context["total"], 6800)

    def test_unknown_order_returns_404(self):
        response = self.client.get(reverse("staff:order_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_allowed_status_change_is_saved(self):
        self.change(101, "Preparing")
        self.assertEqual(status_of(101), "Preparing")
        response = self.client.get(reverse("staff:order_detail", args=[101]))
        self.assertEqual(response.context["order"]["status"], "Preparing")

    def test_skipping_a_status_is_rejected(self):
        self.change(101, "Delivered")  # Placed -> Delivered is not allowed
        self.assertEqual(status_of(101), "Placed")

    def test_final_status_cannot_be_changed(self):
        self.change(103, "Cancelled")  # Delivered is final
        self.assertEqual(status_of(103), "Delivered")

    def test_unknown_status_is_rejected(self):
        self.change(101, "Flying")
        self.assertEqual(status_of(101), "Placed")

    def test_status_change_requires_post(self):
        response = self.client.get(reverse("staff:change_status", args=[101]))
        self.assertEqual(response.status_code, 405)

    def test_toggle_availability_changes_the_dish(self):
        self.client.post(reverse("staff:toggle_availability", args=[3]))  # Cola was not available
        self.assertTrue(is_available(3))
        self.client.post(reverse("staff:toggle_availability", args=[3]))
        self.assertFalse(is_available(3))

    def test_toggle_unknown_dish_returns_404(self):
        response = self.client.post(reverse("staff:toggle_availability", args=[999]))
        self.assertEqual(response.status_code, 404)


class StaffAccessTests(TestCase):
    """Only users in the group "Restaurant staff" may open the /staff/ pages."""

    def setUp(self):
        make_test_data()

    def test_group_is_created_by_migration(self):
        self.assertTrue(Group.objects.filter(name=STAFF_GROUP).exists())

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("staff:orders"))
        self.assertRedirects(response, reverse("staff:login") + "?next=" + reverse("staff:orders"))

    def test_anonymous_user_cannot_change_status(self):
        response = self.client.post(reverse("staff:change_status", args=[101]), {"status": "Preparing"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(status_of(101), "Placed")

    def test_staff_user_sees_only_own_restaurant_orders(self):
        make_user("staff1", staff=True)
        self.client.login(username="staff1", password=PASSWORD)
        response = self.client.get(reverse("staff:orders"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([o["id"] for o in response.context["orders"]], [104, 103, 102, 101])

    def test_staff_cannot_open_or_change_other_restaurant(self):
        self.client.force_login(make_user("staff1", staff=True))
        self.assertEqual(self.client.get(reverse("staff:order_detail", args=[201])).status_code, 404)
        self.client.post(reverse("staff:change_status", args=[201]), {"status": "Preparing"})
        self.assertEqual(status_of(201), "Placed")
        self.assertEqual(self.client.post(reverse("staff:toggle_availability", args=[9])).status_code, 404)
        menu = self.client.get(reverse("staff:menu"))
        self.assertEqual({item.name for item in menu.context["items"]}, {"Pizza", "Burger", "Cola"})

    def test_staff_without_restaurant_sees_nothing(self):
        user = make_user("new_staff", staff=True)
        user.staff_restaurants.clear()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("staff:orders")).context["orders"], [])

    def test_owner_sees_own_restaurant_admin_sees_all(self):
        self.client.force_login(get_user_model().objects.get(username="owner9"))
        self.assertEqual([o["id"] for o in self.client.get(reverse("staff:orders")).context["orders"]], [201])
        self.client.force_login(make_user("boss", role="admin"))
        self.assertEqual(len(self.client.get(reverse("staff:orders")).context["orders"]), 5)

    def test_normal_user_is_denied(self):
        make_user("customer1")
        self.client.login(username="customer1", password=PASSWORD)
        for url in [reverse("staff:orders"), reverse("staff:order_detail", args=[101]), reverse("staff:menu")]:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_normal_user_cannot_change_status_or_menu(self):
        make_user("customer1")
        self.client.force_login(get_user_model().objects.get(username="customer1"))
        response = self.client.post(reverse("staff:change_status", args=[101]), {"status": "Preparing"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(status_of(101), "Placed")
        response = self.client.post(reverse("staff:toggle_availability", args=[3]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(is_available(3))

    def test_owner_and_admin_roles_can_open_staff_pages(self):
        for username, role in [("owner1", "owner"), ("manager1", "admin")]:
            self.client.force_login(make_user(username, role=role))
            self.assertEqual(self.client.get(reverse("staff:orders")).status_code, 200, role)

    def test_superuser_can_open_staff_pages(self):
        self.client.force_login(make_user("admin1", is_superuser=True))
        self.assertEqual(self.client.get(reverse("staff:orders")).status_code, 200)

    def test_login_form_logs_staff_in_and_returns_to_next_page(self):
        make_user("staff1", staff=True)
        response = self.client.post(reverse("staff:login"), {
            "username": "staff1", "password": PASSWORD, "next": reverse("staff:menu")})
        self.assertRedirects(response, reverse("staff:menu"))

    def test_wrong_password_shows_error(self):
        make_user("staff1", staff=True)
        response = self.client.post(reverse("staff:login"), {"username": "staff1", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wrong username or password.")

    def test_logout_ends_access(self):
        self.client.force_login(make_user("staff1", staff=True))
        self.client.post(reverse("staff:logout"))
        self.assertEqual(self.client.get(reverse("staff:orders")).status_code, 302)

    def test_login_without_next_opens_orders(self):
        make_user("staff1", staff=True)
        response = self.client.post(reverse("staff:login"), {"username": "staff1", "password": PASSWORD})
        self.assertRedirects(response, reverse("staff:orders"))


@override_settings(DEBUG=True)  # create_demo_users runs only with DEBUG on
class DemoUsersCommandTests(TestCase):
    def test_command_creates_staff_and_normal_user(self):
        from django.core.management import call_command
        call_command("create_demo_users", "--password", PASSWORD, stdout=open("/dev/null", "w"))
        User = get_user_model()
        self.assertTrue(User.objects.get(username="staff_demo").groups.filter(name=STAFF_GROUP).exists())
        self.assertFalse(User.objects.get(username="customer_demo").groups.exists())
        self.assertEqual(User.objects.get(username="owner_demo").role, "owner")
        admin = User.objects.get(username="admin_demo")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        # passwords are hashed, never stored as plain text
        self.assertTrue(admin.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(admin.check_password(PASSWORD))
