from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from restaurants.models import FoodItem, Restaurant


class FavoritesCartTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="fav-owner", email="fav-owner@example.test", role="owner")
        self.restaurant = Restaurant.objects.create(name="Favorites kitchen", owner=owner, address="Test")
        self.dish = FoodItem.objects.create(restaurant=self.restaurant, name="Dish", price=1000)

    def test_favorites_supplies_csrf_and_current_cart_items(self):
        browser = Client(enforce_csrf_checks=True)
        page = browser.get(reverse("customer:favorites"))
        self.assertContains(page, 'id="favorites-cart-ids"')
        self.assertContains(page, 'js/cart.js')
        token = browser.cookies["csrftoken"].value
        response = browser.post(reverse("customer:cart_add"),
                                {"dish_id": self.dish.pk},
                                HTTP_X_CSRFTOKEN=token, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lines"][str(self.dish.pk)]["quantity"], 1)
        page = browser.get(reverse("customer:favorites"))
        self.assertEqual(page.context["cart_dish_ids"], [str(self.dish.pk)])

    def test_unavailable_and_deleted_dishes_are_rejected(self):
        self.dish.is_available = False
        self.dish.save()
        response = self.client.post(reverse("customer:cart_add"),
                                    {"dish_id": self.dish.pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.dish.delete()
        response = self.client.post(reverse("customer:cart_add"),
                                    {"dish_id": self.dish.pk or 999999}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 404)
