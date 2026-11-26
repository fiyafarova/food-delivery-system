import json
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from core.models import FoodOrder
from core.promotions import PROMOTIONS, calculate_discount
from . import test_saved_cards


class PromotionTests(TestCase):
    setUp = test_saved_cards.SavedCardTests.setUp

    def test_each_code_changes_persisted_total_and_keeps_item_price(self):
        for code, percent in PROMOTIONS.items():
            with self.subTest(code=code):
                self.client.post(reverse('customer:cart_add'), {'dish_id': self.dish.pk})
                response = self.client.post(reverse('create_order'), json.dumps({
                    'promo_code': ' ' + code.lower() + ' ', 'total_amount': '1', 'discount_amount': '999'}), content_type='application/json')
                self.assertEqual(response.status_code, 201, response.content)
                order = FoodOrder.objects.get(pk=response.json()['order_id'])
                self.assertEqual(order.promo_code, code)
                self.assertEqual(order.discount_amount, Decimal(1000 * percent) / 100)
                self.assertEqual(order.total_amount, Decimal(1000) - order.discount_amount)
                self.assertEqual(order.items.first().unit_price, Decimal(1000))

    def test_unknown_code_does_not_create_order_or_empty_cart(self):
        self.client.post(reverse('customer:cart_add'), {'dish_id': self.dish.pk})
        for code in ['FAKE', ['BITE10'], 123]:
            response = self.client.post(reverse('create_order'), json.dumps({'promo_code': code}), content_type='application/json')
            self.assertEqual(response.status_code, 400)
        self.assertFalse(FoodOrder.objects.exists())
        self.assertTrue(self.client.session['cart']['items'])

    def test_rounding_and_no_code(self):
        self.assertEqual(calculate_discount(Decimal('99.95'), 'BITE10')[1], Decimal('10.00'))
        self.assertEqual(calculate_discount(Decimal('1000'), '')[1], Decimal('0.00'))

    def test_checkout_has_shared_codes_without_unavailable_notice(self):
        self.client.post(reverse('customer:cart_add'), {'dish_id': self.dish.pk})
        response = self.client.get(reverse('customer:checkout'))
        self.assertEqual(response.context['promotions'], PROMOTIONS)
        self.assertContains(response, 'checkout-promotions')
        self.assertNotContains(response, 'Promo codes are not available yet.')
