from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CustomerPageTests(TestCase):

    def test_menu_opens(self):
        response = self.client.get(reverse("customer:menu"))

        self.assertEqual(response.status_code, 200)

    def test_profile_requires_login_and_opens_for_customer(self):
        url = reverse("customer:profile")
        self.assertEqual(self.client.get(url).status_code, 302)

        user = get_user_model().objects.create_user(
            username="profile-customer", email="profile@example.test"
        )
        self.client.force_login(user)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/profile.html")

    def test_favorites_opens(self):
        response = self.client.get(reverse("customer:favorites"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/favorites.html")

    def test_unknown_page_returns_404(self):
        response = self.client.get("/this-page-does-not-exist/")

        self.assertEqual(response.status_code, 404)


class CheckoutIntegrationTests(TestCase):
    def setUp(self):
        from restaurants.models import Restaurant, FoodItem
        self.user = get_user_model().objects.create_user(username="checkout-buyer", email="buyer@example.test")
        owner = get_user_model().objects.create_user(username="checkout-owner", email="owner@example.test", role="owner")
        self.restaurant = Restaurant.objects.create(name="Checkout kitchen", owner=owner, address="Abay 1")
        self.dish = FoodItem.objects.create(restaurant=self.restaurant, name="Pizza", price=2500)

    def test_checkout_requires_login(self):
        self.assertRedirects(
            self.client.get(reverse("customer:checkout")),
            reverse("customer:login") + "?next=" + reverse("customer:checkout"),
        )

    def test_customer_cart_creates_order_with_csrf_and_order_page(self):
        import json
        from django.test import Client
        from core.models import FoodOrder
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        browser.get(reverse("customer:menu"))
        token = browser.cookies["csrftoken"].value
        added = browser.post(reverse("customer:cart_add"),
                             {"dish_id": self.dish.pk}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(added.status_code, 302)
        page = browser.get(reverse("customer:checkout"))
        self.assertContains(page, 'id="place-order"')
        self.assertContains(page, 'id="checkout-payable"')
        response = browser.post(
            reverse("create_order"),
            json.dumps({"phone": "+77012345678", "address": "Abay 2"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201, response.content)
        order = FoodOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.customer.user, self.user)
        self.assertEqual(order.restaurant, self.restaurant)
        self.assertEqual(order.total_amount, 2500)
        self.assertEqual(browser.get(reverse("customer:order_status", args=[order.pk])).status_code, 200)
        self.assertFalse(browser.session["cart"]["items"])

    def test_russian_order_labels(self):
        from django.utils.translation import override, gettext
        with override("ru"):
            self.assertEqual(gettext("Order"), "Заказ")
            self.assertEqual(gettext("Date"), "Дата")
            self.assertEqual(gettext("Status"), "Статус")
            self.assertEqual(gettext("Total"), "Итого")
