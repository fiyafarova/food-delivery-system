from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import Customer, Delivery, FoodOrder


class OrderTrackingTests(TestCase):
    def setUp(self):
        from restaurants.models import Restaurant
        User = get_user_model()
        self.buyer = User.objects.create_user(username="tracking-buyer", email="tracking-buyer@example.test")
        owner = User.objects.create_user(username="tracking-owner", email="tracking-owner@example.test", role="owner")
        self.restaurant = Restaurant.objects.create(name="Kitchen", owner=owner, address="Test")
        self.customer = Customer.objects.create(user=self.buyer, name="Buyer", phone="+77010009999", address="Test")
        self.order = FoodOrder.objects.create(customer=self.customer, restaurant=self.restaurant)
        self.client.force_login(self.buyer)

    def snapshot(self):
        return self.client.get(reverse("customer:order_status", args=[self.order.pk]), {"tracking": "1"})

    def test_active_order_link_and_progress(self):
        response = self.client.get(reverse("customer:menu"))
        self.assertContains(response, 'class="order-tracking-float"')
        self.assertEqual(response.context["active_order"], self.order)
        self.assertEqual(self.snapshot().json()["stage"], 0)
        self.order.status = "Preparing"
        self.order.save()
        self.assertEqual(self.snapshot().json()["stage"], 1)

    def test_courier_progress_and_completion(self):
        delivery = Delivery.objects.create(order=self.order, delivery_address="Test",
                                           courier_name="Courier", delivery_status="Assigned")
        self.assertEqual(self.snapshot().json()["stage"], 2)
        delivery.delivery_status = "Picked Up"
        delivery.save()
        state = self.snapshot().json()
        self.assertEqual(state["stage"], 3)
        self.assertEqual(state["courier"], "Courier")
        delivery.delivery_status = "Delivered"
        delivery.save()
        self.assertTrue(self.snapshot().json()["terminal"])
        self.assertNotContains(self.client.get(reverse("customer:menu")), 'class="order-tracking-float"')

    def test_cancelled_order_hides_button(self):
        self.order.status = "Cancelled"
        self.order.save()
        self.assertTrue(self.snapshot().json()["cancelled"])
        self.assertTrue(self.snapshot().json()["terminal"])
        self.assertNotContains(self.client.get(reverse("customer:menu")), 'class="order-tracking-float"')

    def test_other_customer_cannot_read_tracking(self):
        other = get_user_model().objects.create_user(username="tracking-other", email="tracking-other@example.test")
        self.client.force_login(other)
        self.assertEqual(self.snapshot().status_code, 404)
        self.assertNotContains(self.client.get(reverse("customer:menu")), 'class="order-tracking-float"')

    def test_guest_has_no_tracking_button(self):
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("customer:menu")), 'class="order-tracking-float"')
        self.assertEqual(self.snapshot().status_code, 302)

    def test_latest_active_order_selected(self):
        second = FoodOrder.objects.create(customer=self.customer, restaurant=self.restaurant)
        self.assertEqual(self.client.get(reverse("customer:menu")).context["active_order"], second)
