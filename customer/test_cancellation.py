import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Customer, FoodOrder
from restaurants.models import Restaurant


class OrderCancellationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username="cancel-buyer", email="cancel@example.test")
        self.owner = User.objects.create_user(username="cancel-owner", email="cancel-owner@example.test", role="owner")
        restaurant = Restaurant.objects.create(name="Kitchen", owner=self.owner, address="Test")
        self.customer = Customer.objects.create(user=self.buyer, name="Buyer", phone="+77010008888", address="Test")
        self.order = FoodOrder.objects.create(customer=self.customer, restaurant=restaurant)
        self.url = reverse("customer:cancel_order", args=[self.order.pk])
        self.client.force_login(self.buyer)

    def test_confirmation_does_not_cancel_and_post_keeps_history(self):
        self.assertContains(self.client.get(self.url), 'type="submit"')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Placed")
        self.assertRedirects(self.client.post(self.url), reverse("customer:order_status", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Cancelled")
        self.assertContains(self.client.get(reverse("customer:profile") + "?tab=orders"), str(self.order.pk))
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("staff:orders")), "Cancelled")

    def test_preparing_and_final_orders_cannot_be_cancelled(self):
        for status in ["Preparing", "Delivered", "Cancelled"]:
            self.order.status = status
            self.order.save()
            self.client.post(self.url)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)

    def test_other_customer_and_guest(self):
        other = get_user_model().objects.create_user(username="cancel-other", email="cancel-other@example.test")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Placed")

    def test_csrf_required(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.buyer)
        self.assertEqual(browser.post(self.url).status_code, 403)

    def test_preparation_started_after_confirmation(self):
        self.client.get(self.url)
        self.order.status = "Preparing"
        self.order.save()
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Cancellation is no longer available")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Preparing")

    def test_status_change_during_cancel_request_is_not_overwritten(self):
        def start_preparation(*args, **kwargs):
            order = get_object_or_404(*args, **kwargs)
            FoodOrder.objects.filter(pk=order.pk).update(status="Preparing")
            return order
        with patch("customer.cancellation.get_object_or_404", side_effect=start_preparation):
            self.client.post(self.url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Preparing")

    def test_stale_staff_request_does_not_revive_cancelled_order(self):
        self.client.force_login(self.owner)
        def cancel_before_staff_write(*args, **kwargs):
            order = get_object_or_404(*args, **kwargs)
            FoodOrder.objects.filter(pk=order.pk).update(status="Cancelled")
            return order
        with patch("staff.views.get_object_or_404", side_effect=cancel_before_staff_write):
            self.client.post(reverse("staff:change_status", args=[self.order.pk]), {"status": "Preparing"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Cancelled")

    def test_api_cannot_reopen_cancelled_order(self):
        self.client.post(self.url)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("update_order_status", args=[self.order.pk]),
            json.dumps({"status": "Preparing"}), content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Cancelled")
