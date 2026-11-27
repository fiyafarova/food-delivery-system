"""Courier role: assign a courier, "picked up", "delivered", who sees what."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Delivery, FoodOrder
from staff.models import TemporaryPassword

from .tests import PASSWORD, make_test_data, make_user


def make_courier(username, **extra):
    return make_user(username, role="courier", **extra)


def status_of(order_id):
    return FoodOrder.objects.get(pk=order_id).status


class CourierFlowTests(TestCase):
    """Test Kitchen (owner0): 101 Placed, 102 Preparing, 103 Delivered, 104 Cancelled; Other Place: 201."""

    def setUp(self):
        make_test_data()
        self.courier = make_courier("arman", first_name="Arman")
        self.other_courier = make_courier("dana")
        self.client.force_login(self.courier)

    def assign(self, order_id, courier, as_user="owner0"):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.get(username=as_user))
        response = self.client.post(reverse("staff:assign_courier", args=[order_id]), {"courier": courier.pk})
        self.client.force_login(self.courier)
        return response

    def delivery(self, order_id):
        return Delivery.objects.get(order_id=order_id)

    def test_manager_assigns_courier_and_delivery_is_created(self):
        self.assign(102, self.courier)
        delivery = self.delivery(102)
        self.assertEqual(delivery.courier, self.courier)
        self.assertEqual(delivery.courier_name, "Arman")
        self.assertEqual(delivery.delivery_status, "Assigned")
        self.assertEqual(delivery.delivery_address, "Almaty")

    def test_full_path_assigned_picked_up_delivered(self):
        self.assign(102, self.courier)
        delivery = self.delivery(102)
        self.client.post(reverse("staff:courier_picked_up", args=[delivery.pk]))
        self.assertEqual(self.delivery(102).delivery_status, "Picked Up")
        self.assertIsNotNone(self.delivery(102).picked_up_at)
        self.client.post(reverse("staff:courier_delivered", args=[delivery.pk]))
        self.assertEqual(self.delivery(102).delivery_status, "Delivered")
        self.assertIsNotNone(self.delivery(102).delivered_at)
        self.assertEqual(status_of(102), "Delivered")  # the order is closed together with the delivery

    def test_courier_cannot_pick_up_before_the_kitchen_starts(self):
        self.assign(101, self.courier)  # order 101 is still "Placed"
        self.client.post(reverse("staff:courier_picked_up", args=[self.delivery(101).pk]))
        self.assertEqual(self.delivery(101).delivery_status, "Assigned")

    def test_cannot_deliver_without_picking_up(self):
        self.assign(102, self.courier)
        self.client.post(reverse("staff:courier_delivered", args=[self.delivery(102).pk]))
        self.assertEqual(self.delivery(102).delivery_status, "Assigned")
        self.assertEqual(status_of(102), "Preparing")

    def test_cancelled_order_cannot_be_picked_up(self):
        self.assign(102, self.courier)
        FoodOrder.objects.filter(pk=102).update(status="Cancelled")
        self.client.post(reverse("staff:courier_picked_up", args=[self.delivery(102).pk]))
        self.assertEqual(self.delivery(102).delivery_status, "Assigned")

    def test_final_orders_cannot_get_a_courier(self):
        for order_id in (103, 104):  # Delivered, Cancelled
            self.assign(order_id, self.courier)
            self.assertFalse(Delivery.objects.filter(order_id=order_id).exists())

    def test_courier_can_be_changed_until_pick_up(self):
        self.assign(102, self.courier)
        self.assign(102, self.other_courier)
        self.assertEqual(self.delivery(102).courier, self.other_courier)
        # the new courier picks it up -> it can no longer be given to someone else
        self.client.force_login(self.other_courier)
        self.client.post(reverse("staff:courier_picked_up", args=[self.delivery(102).pk]))
        self.assign(102, self.courier)
        self.assertEqual(self.delivery(102).courier, self.other_courier)

    def test_courier_sees_only_own_deliveries(self):
        self.assign(101, self.courier)
        self.assign(102, self.other_courier)
        response = self.client.get(reverse("staff:courier"))
        self.assertEqual([d.order_id for d in response.context["active"]], [101])

    def test_courier_cannot_change_someone_elses_delivery(self):
        self.assign(102, self.other_courier)
        response = self.client.post(reverse("staff:courier_picked_up", args=[self.delivery(102).pk]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.delivery(102).delivery_status, "Assigned")

    def test_employee_cannot_assign_courier(self):
        make_user("staff1", staff=True)
        self.assertEqual(self.assign(102, self.courier, as_user="staff1").status_code, 403)
        self.assertFalse(Delivery.objects.filter(order_id=102).exists())

    def test_manager_cannot_assign_courier_to_other_restaurants_order(self):
        self.assertEqual(self.assign(201, self.courier).status_code, 404)  # 201 belongs to owner9

    def test_only_couriers_can_be_assigned(self):
        customer = make_user("just_a_customer")
        self.assign(102, customer)
        self.assertFalse(Delivery.objects.filter(order_id=102).exists())

    def test_staff_closing_the_order_closes_the_delivery(self):
        self.assign(102, self.courier)
        self.client.force_login(make_user("staff1", staff=True))
        self.client.post(reverse("staff:change_status", args=[102]), {"status": "Delivered"})
        self.assertEqual(self.delivery(102).delivery_status, "Delivered")

    def test_order_page_shows_courier(self):
        self.assign(102, self.courier)
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.get(username="owner0"))
        response = self.client.get(reverse("staff:order_detail", args=[102]))
        self.assertContains(response, "Arman")
        self.assertTrue(response.context["may_assign"])


class CourierAccessTests(TestCase):
    def setUp(self):
        make_test_data()

    def test_guest_is_sent_to_staff_login(self):
        response = self.client.get(reverse("staff:courier"))
        self.assertRedirects(response, reverse("staff:login") + "?next=" + reverse("staff:courier"),
                             fetch_redirect_response=False)

    def test_customer_and_employee_get_403(self):
        for user in (make_user("cust"), make_user("staff1", staff=True)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("staff:courier")).status_code, 403)

    def test_courier_cannot_open_restaurant_pages(self):
        self.client.force_login(make_courier("arman"))
        self.assertEqual(self.client.get(reverse("staff:orders")).status_code, 403)

    def test_staff_login_sends_courier_to_deliveries(self):
        make_courier("arman")
        response = self.client.post(reverse("staff:login"), {"username": "arman", "password": PASSWORD})
        self.assertRedirects(response, reverse("staff:courier"))
        self.assertRedirects(self.client.get(reverse("staff:home")), reverse("staff:courier"))

    def test_admin_registers_courier_with_temporary_password(self):
        self.client.force_login(make_user("boss", role="admin", is_superuser=True))
        response = self.client.post(reverse("staff:couriers"), {
            "username": "newcourier", "email": "newcourier@example.com",
            "password": "Courier-temp-2026"})
        self.assertRedirects(response, reverse("staff:couriers"))
        from django.contrib.auth import get_user_model
        courier = get_user_model().objects.get(username="newcourier")
        self.assertEqual(courier.role, "courier")
        self.assertTrue(TemporaryPassword.objects.filter(user=courier).exists())
        self.assertNotIn("Courier-temp-2026", courier.password)  # stored as a hash

    def test_manager_cannot_register_couriers(self):
        self.client.force_login(make_user("owner_x", role="owner"))
        self.assertEqual(self.client.get(reverse("staff:couriers")).status_code, 403)

    def test_courier_with_temporary_password_must_change_it(self):
        courier = make_courier("arman")
        TemporaryPassword.objects.create(user=courier)
        self.client.force_login(courier)
        response = self.client.get(reverse("staff:courier"))
        self.assertTrue(response.url.startswith(reverse("staff:password_change")))


@override_settings(DEBUG=True)
class DemoCourierTests(TestCase):
    def test_demo_courier_gets_demo_order_2(self):
        call_command("seed_demo", stdout=StringIO())
        call_command("create_demo_users", stdout=StringIO())
        delivery = Delivery.objects.get(courier__username="courier_demo")
        self.assertEqual(delivery.order.restaurant.name, "Dastarkhan")
        self.assertEqual(delivery.order.status, "Preparing")
        self.assertFalse(Delivery.objects.filter(courier__username="courier2_demo").exists())
        call_command("create_demo_users", stdout=StringIO())  # running again keeps one delivery
        self.assertEqual(Delivery.objects.filter(courier__username="courier_demo").count(), 1)


class CourierApiTests(TestCase):
    """The JSON API (core/views.py) follows the same delivery rules as the courier pages."""

    def setUp(self):
        make_test_data()
        self.courier = make_courier("arman")
        from django.contrib.auth import get_user_model
        self.owner = get_user_model().objects.get(username="owner0")

    def post(self, user, url, data):
        self.client.force_login(user)
        return self.client.post(url, data, content_type="application/json")

    def api_assign(self, order_id):
        delivery = Delivery.objects.create(order_id=order_id, delivery_address="Almaty")
        response = self.post(self.owner, reverse("assign_courier", args=[delivery.pk]),
                             {"courier_id": self.courier.pk})
        return response, delivery

    def set_status(self, delivery, status):
        return self.post(self.courier, reverse("update_delivery_status", args=[delivery.pk]),
                         {"delivery_status": status})

    def test_api_full_path(self):
        response, delivery = self.api_assign(102)  # Preparing
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.set_status(delivery, "Picked Up").status_code, 200)
        self.assertEqual(self.set_status(delivery, "Delivered").status_code, 200)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.picked_up_at)
        self.assertEqual(status_of(102), "Delivered")

    def test_api_cannot_pick_up_before_preparing(self):
        _response, delivery = self.api_assign(101)  # Placed
        self.assertEqual(self.set_status(delivery, "Picked Up").status_code, 400)

    def test_api_cannot_deliver_without_pick_up(self):
        _response, delivery = self.api_assign(102)
        self.assertEqual(self.set_status(delivery, "Delivered").status_code, 400)
        self.assertEqual(status_of(102), "Preparing")

    def test_api_cannot_assign_to_final_order(self):
        response, delivery = self.api_assign(103)  # Delivered
        self.assertEqual(response.status_code, 400)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.courier)

    def test_api_my_deliveries_shows_picked_up_time(self):
        _response, delivery = self.api_assign(102)
        self.set_status(delivery, "Picked Up")
        self.client.force_login(self.courier)
        data = self.client.get(reverse("my_deliveries")).json()["deliveries"]
        self.assertEqual([d["order_id"] for d in data], [102])
        self.assertIsNotNone(data[0]["picked_up_at"])
