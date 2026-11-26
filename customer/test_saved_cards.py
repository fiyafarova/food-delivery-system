import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import SavedCard
from core.models import Customer, FoodOrder
from restaurants.models import FoodItem, Restaurant


class SavedCardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="card-buyer", email="card@example.test")
        self.other = User.objects.create_user(username="card-other", email="card-other@example.test", role="owner")
        self.restaurant = Restaurant.objects.create(owner=self.other, name="Kitchen", address="Test")
        self.dish = FoodItem.objects.create(restaurant=self.restaurant, name="Dish", price=1000)
        Customer.objects.create(user=self.user, name="Buyer", phone="+77010007777", address="Test")
        self.card = SavedCard.objects.create(user=self.user, nickname="Main", brand="visa", last4="1234")
        self.foreign = SavedCard.objects.create(user=self.other, nickname="Private", brand="mastercard", last4="5678")
        self.client.force_login(self.user)

    def test_profile_add_multiple_cards_and_reject_full_number(self):
        response = self.client.get(reverse("customer:profile"), {"tab": "cards"})
        self.assertContains(response, "Main")
        self.assertNotContains(response, "Private")
        self.client.post(reverse("customer:profile"), {
            "form_type": "card", "nickname": "Second", "brand": "visa", "last4": "0001"})
        self.assertEqual(self.user.saved_cards.count(), 2)
        response = self.client.post(reverse("customer:profile"), {
            "form_type": "card", "nickname": "Full number", "brand": "visa", "last4": "4111111111111111"})
        self.assertEqual(self.user.saved_cards.count(), 2)
        self.assertTrue(response.context["card_form"].errors)

    def test_selection_persists_and_foreign_selection_is_rejected(self):
        self.assertEqual(self.client.post(reverse("customer:select_card"),
                                          {"card_id": self.foreign.pk}).status_code, 404)
        response = self.client.post(reverse("customer:select_card"), {"card_id": self.card.pk})
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("customer:cart_add"), {"dish_id": self.dish.pk})
        page = self.client.get(reverse("customer:checkout"))
        self.assertEqual(page.context["selected_card"], self.card)
        self.assertContains(page, "1234")
        self.assertNotContains(page, "Private")

    def test_order_saves_card_selection_without_charging(self):
        self.client.post(reverse("customer:cart_add"), {"dish_id": self.dish.pk})
        response = self.client.post(reverse("create_order"), json.dumps({"card_id": self.card.pk}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        order = FoodOrder.objects.get(pk=response.json()["order_id"])
        self.assertEqual(order.payment_card, self.card)
        self.assertFalse(hasattr(order, "payment"))

    def test_order_rejects_another_users_card(self):
        self.client.post(reverse("customer:cart_add"), {"dish_id": self.dish.pk})
        response = self.client.post(reverse("create_order"), json.dumps({"card_id": self.foreign.pk}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(FoodOrder.objects.exists())
        self.assertTrue(self.client.session["cart"]["items"])

    def test_delete_owned_card_and_clear_selection(self):
        self.client.post(reverse("customer:select_card"), {"card_id": self.card.pk})
        self.client.post(reverse("customer:profile"), {"form_type": "delete_card", "card_id": self.card.pk})
        self.assertNotIn("checkout_card_id", self.client.session)
        self.assertFalse(SavedCard.objects.filter(pk=self.card.pk).exists())
        self.assertEqual(self.client.post(reverse("customer:profile"), {
            "form_type": "delete_card", "card_id": self.foreign.pk}).status_code, 404)
        self.assertTrue(SavedCard.objects.filter(pk=self.foreign.pk).exists())

    def test_guest_and_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post(reverse("customer:select_card"), {"card_id": self.card.pk}).status_code, 403)
        browser.force_login(self.user)
        self.assertEqual(browser.post(reverse("customer:select_card"), {"card_id": self.card.pk}).status_code, 403)
        browser.get(reverse("customer:checkout"))
        token = browser.cookies.get("csrftoken")
        # Profile renders a normal CSRF-protected card form.
        browser.get(reverse("customer:profile"), {"tab": "cards"})
        token = browser.cookies["csrftoken"].value
        self.assertEqual(browser.post(reverse("customer:select_card"), {"card_id": self.card.pk},
                                      HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_deleted_card_does_not_delete_order(self):
        order = FoodOrder.objects.create(customer=self.user.customer, restaurant=self.restaurant, payment_card=self.card)
        self.card.delete()
        order.refresh_from_db()
        self.assertIsNone(order.payment_card_id)
