from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from restaurants.models import Category, FoodItem, Restaurant


class BudgetMealTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="budget-owner", email="budget@example.test", role="owner")
        self.restaurant = Restaurant.objects.create(name="Test kitchen", owner=owner, address="Test")
        self.main = FoodItem.objects.create(restaurant=self.restaurant, name="Lunch", price=2000,
                                          category=Category.objects.create(name="Main course"))
        self.drink = FoodItem.objects.create(restaurant=self.restaurant, name="Tea", price=400,
                                           category=Category.objects.create(name="Drinks"))

    def search(self, budget="2900", parts=("main", "drink")):
        return self.client.get(reverse("customer:budget"), {"budget": budget, "part": list(parts)})

    def test_delivery_included_and_exact_budget(self):
        response = self.search()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["matches"]), 1)
        self.assertEqual(response.context["matches"][0]["total"], "2 900 ₸")
        self.assertFalse(self.search("2899").context["matches"])

    def test_parts_and_invalid_input(self):
        self.assertEqual(len(self.search("2500", ("main",)).context["matches"]), 1)
        self.assertTrue(self.search("NaN").context["error"])
        self.assertTrue(self.search(parts=()).context["error"])

    def test_no_closed_or_unavailable_dishes(self):
        self.drink.is_available = False
        self.drink.save()
        self.assertFalse(self.search().context["matches"])
        self.restaurant.is_open = False
        self.restaurant.save()
        self.assertFalse(self.search("2500", ("main",)).context["matches"])

    def test_add_set_and_recheck_price(self):
        token = self.search().context["matches"][0]["token"]
        response = self.client.post(reverse("customer:budget"), {"bundle": token})
        self.assertRedirects(response, reverse("customer:cart"))
        self.assertEqual(self.client.session["cart"]["items"], {str(self.main.pk): 1, str(self.drink.pk): 1})
        self.main.price = 3000
        self.main.save()
        response = self.client.post(reverse("customer:budget"), {"bundle": token, "replace": "1"})
        self.assertRedirects(response, reverse("customer:budget"))
        self.assertEqual(self.client.session["cart"]["items"][str(self.main.pk)], 1)

    def test_existing_cart_needs_confirmation(self):
        token = self.search().context["matches"][0]["token"]
        self.client.post(reverse("customer:budget"), {"bundle": token})
        response = self.client.post(reverse("customer:budget"), {"bundle": token})
        self.assertTemplateUsed(response, "customer/budget_confirm.html")
        self.assertRedirects(self.client.post(reverse("customer:budget"),
                                              {"bundle": token, "replace": "1"}),
                             reverse("customer:cart"))

    def test_unsigned_bundle_is_rejected(self):
        self.assertRedirects(self.client.post(reverse("customer:budget"), {"bundle": "invalid"}),
                             reverse("customer:budget"))
        self.assertNotIn("cart", self.client.session)

    def test_salads_and_sides_are_included(self):
        salad = FoodItem.objects.create(
            restaurant=self.restaurant, name="Chicken salad", price=1900,
            category=Category.objects.create(name="Salads"))
        fries = FoodItem.objects.create(
            restaurant=self.restaurant, name="French fries", price=900,
            category=Category.objects.create(name="Sides"))
        names = [dish["name"] for match in self.search().context["matches"] for dish in match["dishes"]]
        self.assertIn(salad.name, names)
        snack_names = [dish["name"] for match in self.search("3500", ("snack",)).context["matches"]
                       for dish in match["dishes"]]
        self.assertIn(fries.name, snack_names)
        self.assertFalse(self.search("3500", ("main", "drink", "snack")).context["matches"])
