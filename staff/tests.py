from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from . import views
from .permissions import STAFF_GROUP

PASSWORD = "test-pass-123"


def make_user(username, staff=False, **extra):
    user = get_user_model().objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, **extra)
    if staff:
        user.groups.add(Group.objects.get(name=STAFF_GROUP))
    return user


class StaffTests(TestCase):
    """Orders in test data: 101 Placed (total 6800), 102 Preparing, 103 Delivered, 104 Cancelled."""

    def setUp(self):
        views.reset_test_data()  # every test starts from the same data
        self.client.force_login(make_user("staff1", staff=True))

    def change(self, order_id, status):
        return self.client.post(reverse("staff:change_status", args=[order_id]), {"status": status})

    def status_of(self, order_id):
        return views.find_order(order_id)["status"]

    def test_orders_list_shows_all_orders_newest_first(self):
        response = self.client.get(reverse("staff:orders"))
        self.assertEqual([o["id"] for o in response.context["orders"]], [104, 103, 102, 101])

    def test_orders_can_be_filtered_by_status(self):
        response = self.client.get(reverse("staff:orders"), {"status": "Placed"})
        self.assertEqual([o["id"] for o in response.context["orders"]], [101])

    def test_unknown_filter_shows_all_orders(self):
        response = self.client.get(reverse("staff:orders"), {"status": "Nonsense"})
        self.assertEqual(len(response.context["orders"]), 4)

    def test_order_total_is_calculated_from_lines(self):
        response = self.client.get(reverse("staff:order_detail", args=[101]))
        self.assertEqual(response.context["total"], 6800)

    def test_unknown_order_returns_404(self):
        response = self.client.get(reverse("staff:order_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_allowed_status_change_is_saved(self):
        self.change(101, "Preparing")
        self.assertEqual(self.status_of(101), "Preparing")
        response = self.client.get(reverse("staff:order_detail", args=[101]))
        self.assertEqual(response.context["order"]["status"], "Preparing")

    def test_skipping_a_status_is_rejected(self):
        self.change(101, "Delivered")  # Placed -> Delivered is not allowed
        self.assertEqual(self.status_of(101), "Placed")

    def test_final_status_cannot_be_changed(self):
        self.change(103, "Cancelled")  # Delivered is final
        self.assertEqual(self.status_of(103), "Delivered")

    def test_unknown_status_is_rejected(self):
        self.change(101, "Flying")
        self.assertEqual(self.status_of(101), "Placed")

    def test_status_change_requires_post(self):
        response = self.client.get(reverse("staff:change_status", args=[101]))
        self.assertEqual(response.status_code, 405)

    def test_toggle_availability_changes_the_dish(self):
        self.client.post(reverse("staff:toggle_availability", args=[3]))  # Cola was not available
        self.assertTrue(views.MENU[2]["is_available"])
        self.client.post(reverse("staff:toggle_availability", args=[3]))
        self.assertFalse(views.MENU[2]["is_available"])

    def test_toggle_unknown_dish_returns_404(self):
        response = self.client.post(reverse("staff:toggle_availability", args=[999]))
        self.assertEqual(response.status_code, 404)


class StaffAccessTests(TestCase):
    """Only users in the group "Restaurant staff" may open the /staff/ pages."""

    def setUp(self):
        views.reset_test_data()

    def test_group_is_created_by_migration(self):
        self.assertTrue(Group.objects.filter(name=STAFF_GROUP).exists())

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("staff:orders"))
        self.assertRedirects(response, reverse("staff:login") + "?next=" + reverse("staff:orders"))

    def test_anonymous_user_cannot_change_status(self):
        response = self.client.post(reverse("staff:change_status", args=[101]), {"status": "Preparing"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(views.find_order(101)["status"], "Placed")

    def test_staff_user_sees_orders_list(self):
        make_user("staff1", staff=True)
        self.client.login(username="staff1", password=PASSWORD)
        response = self.client.get(reverse("staff:orders"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["orders"]), 4)

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
        self.assertEqual(views.find_order(101)["status"], "Placed")
        response = self.client.post(reverse("staff:toggle_availability", args=[3]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(views.MENU[2]["is_available"])

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
