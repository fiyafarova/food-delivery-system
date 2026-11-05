from django.test import TestCase
from django.urls import reverse

from . import views


class StaffTests(TestCase):
    """Orders in test data: 101 Placed (total 6800), 102 Preparing, 103 Delivered, 104 Cancelled."""

    def setUp(self):
        views.reset_test_data()  # every test starts from the same data

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