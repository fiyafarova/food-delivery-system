"""Registration of all roles, authorization and password hashing.

customer  -> signs up on /register/
employee  -> registered by a manager on /staff/team/
manager   -> registered by an admin on /staff/managers/
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CustomerProfile
from restaurants.models import Restaurant

from .models import TemporaryPassword
from .permissions import STAFF_GROUP

User = get_user_model()
GOOD_PASSWORD = "Sunny-Kitchen-42"


class CustomerSignUpTests(TestCase):
    def sign_up(self, **data):
        form = {"username": "anna", "email": "anna@example.com",
                "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD, **data}
        return self.client.post(reverse("customer:register"), form)

    def test_sign_up_creates_customer_logs_in_and_hashes_password(self):
        response = self.sign_up()
        self.assertRedirects(response, reverse("customer:profile"))
        user = User.objects.get(username="anna")
        self.assertEqual(user.role, "customer")
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())
        self.assertFalse(user.groups.exists())                      # no staff role
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))  # stored as a hash ...
        self.assertNotIn(GOOD_PASSWORD, user.password)              # ... never as text
        self.assertTrue(user.check_password(GOOD_PASSWORD))
        self.assertEqual(self.client.get(reverse("customer:profile")).status_code, 200)  # logged in

    def test_weak_password_is_rejected(self):
        response = self.sign_up(password1="12345678", password2="12345678")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="anna").exists())
        self.assertTrue(response.context["form"].errors["password1"])

    def test_passwords_must_match(self):
        response = self.sign_up(password2="Other-Password-99")
        self.assertIn("password2", response.context["form"].errors)

    def test_duplicate_username_and_email_are_rejected(self):
        User.objects.create_user(username="Anna", email="ANNA@example.com")
        errors = self.sign_up().context["form"].errors
        self.assertIn("username", errors)
        self.assertIn("email", errors)

    def test_sign_up_cannot_choose_a_role(self):
        self.sign_up(role="admin", is_superuser="on", is_staff="on")
        user = User.objects.get(username="anna")
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_superuser or user.is_staff)

    def test_next_to_another_site_is_ignored(self):
        response = self.sign_up(next="https://evil.example.com/")
        self.assertRedirects(response, reverse("customer:profile"))

    def test_customer_cannot_open_staff_pages(self):
        self.sign_up()
        self.assertEqual(self.client.get(reverse("staff:orders")).status_code, 403)
        self.assertEqual(self.client.get(reverse("staff:team")).status_code, 403)


class RegistrationByManagersTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", email="admin1@example.com", role="admin")
        self.owner = User.objects.create_user(username="owner1", email="owner1@example.com", role="owner")
        self.kitchen = Restaurant.objects.create(name="Test Kitchen", owner=self.owner, address="Almaty")
        other_owner = User.objects.create_user(username="owner2", email="owner2@example.com", role="owner")
        self.other = Restaurant.objects.create(name="Other Place", owner=other_owner, address="Almaty")
        self.owner_client, self.admin_client = Client(), Client()
        self.owner_client.force_login(self.owner)
        self.admin_client.force_login(self.admin)

    def register_employee(self, client, restaurant, username="cook1"):
        return client.post(reverse("staff:team"), {
            "restaurant": restaurant.pk, "username": username, "email": f"{username}@example.com",
            "first_name": "Aru", "password": GOOD_PASSWORD})

    # --- manager registers an employee

    def test_manager_registers_employee_for_own_restaurant(self):
        response = self.register_employee(self.owner_client, self.kitchen)
        self.assertRedirects(response, reverse("staff:team"))
        cook = User.objects.get(username="cook1")
        self.assertTrue(cook.groups.filter(name=STAFF_GROUP).exists())
        self.assertEqual(list(cook.staff_restaurants.all()), [self.kitchen])
        self.assertTrue(TemporaryPassword.objects.filter(user=cook, created_by=self.owner).exists())
        self.assertTrue(cook.password.startswith("pbkdf2_sha256$"))

    def test_manager_cannot_register_employee_for_other_restaurant(self):
        response = self.register_employee(self.owner_client, self.other)
        self.assertEqual(response.status_code, 200)  # form error: not a valid choice
        self.assertIn("restaurant", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="cook1").exists())

    def test_manager_removes_employee(self):
        self.register_employee(self.owner_client, self.kitchen)
        cook = User.objects.get(username="cook1")
        self.owner_client.post(reverse("staff:team_remove", args=[self.kitchen.pk, cook.pk]))
        self.assertFalse(cook.staff_restaurants.exists())
        self.assertFalse(cook.groups.filter(name=STAFF_GROUP).exists())
        self.assertTrue(User.objects.filter(pk=cook.pk).exists())  # account kept

    def test_manager_cannot_remove_other_restaurants_employee(self):
        cook = User.objects.create_user(username="cook9", email="cook9@example.com")
        self.other.staff.add(cook)
        response = self.owner_client.post(reverse("staff:team_remove", args=[self.other.pk, cook.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.other.staff.filter(pk=cook.pk).exists())

    def test_employee_cannot_open_team_or_managers(self):
        self.register_employee(self.owner_client, self.kitchen)
        cook = User.objects.get(username="cook1")
        TemporaryPassword.objects.filter(user=cook).delete()
        client = Client()
        client.force_login(cook)
        self.assertEqual(client.get(reverse("staff:team")).status_code, 403)
        self.assertEqual(client.get(reverse("staff:managers")).status_code, 403)

    # --- employee: first login with the temporary password

    def test_employee_must_change_temporary_password(self):
        self.register_employee(self.owner_client, self.kitchen)
        client = Client()
        response = client.post(reverse("staff:login"), {"username": "cook1", "password": GOOD_PASSWORD})
        self.assertRedirects(response, reverse("staff:orders"), fetch_redirect_response=False)

        response = client.get(reverse("staff:orders"))  # temporary password -> change it first
        self.assertRedirects(response, reverse("staff:password_change") + "?next=" + reverse("staff:orders"))

        new_password = "My-Own-Strong-77"
        response = client.post(reverse("staff:password_change"), {
            "old_password": GOOD_PASSWORD, "new_password1": new_password, "new_password2": new_password,
            "next": reverse("staff:orders")})
        self.assertRedirects(response, reverse("staff:orders"))
        self.assertFalse(TemporaryPassword.objects.filter(user__username="cook1").exists())
        self.assertEqual(client.get(reverse("staff:orders")).status_code, 200)  # still logged in
        self.assertTrue(User.objects.get(username="cook1").check_password(new_password))

    def test_wrong_old_password_is_rejected(self):
        self.register_employee(self.owner_client, self.kitchen)
        client = Client()
        client.force_login(User.objects.get(username="cook1"))
        response = client.post(reverse("staff:password_change"), {
            "old_password": "wrong", "new_password1": "My-Own-Strong-77", "new_password2": "My-Own-Strong-77"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_password", response.context["form"].errors)
        self.assertTrue(TemporaryPassword.objects.filter(user__username="cook1").exists())

    # --- admin registers a manager

    def test_admin_registers_manager_with_restaurant(self):
        response = self.admin_client.post(reverse("staff:managers"), {
            "username": "boss2", "email": "boss2@example.com", "password": GOOD_PASSWORD,
            "restaurant_name": "Nori Sushi", "address": "Abay 1", "city": "Almaty", "cuisine": "Sushi"})
        self.assertRedirects(response, reverse("staff:managers"))
        boss = User.objects.get(username="boss2")
        self.assertEqual(boss.role, "owner")
        self.assertEqual(Restaurant.objects.get(name="Nori Sushi").owner, boss)
        self.assertTrue(TemporaryPassword.objects.filter(user=boss).exists())

        # the new manager can then register employees for the new restaurant
        TemporaryPassword.objects.filter(user=boss).delete()
        boss_client = Client()
        boss_client.force_login(boss)
        self.register_employee(boss_client, Restaurant.objects.get(name="Nori Sushi"), username="sushi_cook")
        self.assertTrue(User.objects.get(username="sushi_cook").staff_restaurants.filter(name="Nori Sushi").exists())

    def test_manager_cannot_register_managers(self):
        self.assertEqual(self.owner_client.get(reverse("staff:managers")).status_code, 403)
        self.owner_client.post(reverse("staff:managers"), {
            "username": "x", "email": "x@example.com", "password": GOOD_PASSWORD,
            "restaurant_name": "X", "address": "X", "city": "Almaty"})
        self.assertFalse(User.objects.filter(username="x").exists())

    def test_guest_is_sent_to_login(self):
        for name in ["staff:team", "staff:managers"]:
            self.assertEqual(Client().get(reverse(name)).status_code, 302)

    def test_staff_group_exists_for_new_databases(self):
        self.assertTrue(Group.objects.filter(name=STAFF_GROUP).exists())
