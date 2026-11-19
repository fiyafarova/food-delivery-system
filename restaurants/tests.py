from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Category, Restaurant, FoodItem


class FlowTests(APITestCase):
    password = 'Str0ng!Pass99'

    @classmethod
    def setUpTestData(cls):
        for username in ('owner1', 'owner2'):
            User.objects.create_user(
                username=username,
                email=f'{username}@example.test',
                password=cls.password,
                role=User.Role.OWNER,
            )

    def login(self, username):
        response = self.client.post('/api/auth/login/', {
            'username': username,
            'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['access']

    def auth(self, token):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

    def test_full_flow(self):
        owner = self.login('owner1')
        other = self.login('owner2')

        registration = self.client.post('/api/auth/register/', {
            'username': 'cust1',
            'email': 'cust1@example.test',
            'password': self.password,
            'role': User.Role.OWNER,
        }, format='json')

        self.assertEqual(registration.status_code, 201, registration.data)
        self.assertEqual(
            User.objects.get(username='cust1').role,
            User.Role.CUSTOMER
        )
        cust = self.login('cust1')

        # profile
        self.auth(cust)
        r = self.client.patch(
            '/api/profile/',
            {'phone': '123', 'city': 'Almaty'},
            format='json'
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.client.get('/api/profile/').data['city'],
            'Almaty'
        )

        # customer cannot create restaurant
        r = self.client.post(
            '/api/restaurants/',
            {'name': 'X', 'address': 'Y'},
            format='json'
        )
        self.assertEqual(r.status_code, 403)

        # owner creates restaurant
        self.auth(owner)
        r = self.client.post('/api/restaurants/', {
            'name': 'Pizza Palace',
            'address': '1 Main St',
            'cuisine': 'Italian',
            'city': 'Almaty',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data['id']

        # category: owner cannot create it through the API
        r = self.client.post(
            '/api/categories/',
            {'name': 'Pizza'},
            format='json'
        )
        self.assertEqual(r.status_code, 403)
        cat = Category.objects.create(name='Pizza')

        # owner adds food
        r = self.client.post('/api/foods/', {
            'restaurant': rid,
            'category': cat.id,
            'name': 'Margherita',
            'price': '9.50',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        fid = r.data['id']

        # other owner cannot touch it
        self.auth(other)
        self.assertEqual(
            self.client.delete(f'/api/foods/{fid}/').status_code,
            403
        )
        self.assertEqual(
            self.client.delete(f'/api/restaurants/{rid}/').status_code,
            403
        )
        r = self.client.post('/api/foods/', {
            'restaurant': rid,
            'name': 'Hack',
            'price': '1',
        }, format='json')
        self.assertEqual(r.status_code, 400)

        # public search
        self.client.credentials()
        r = self.client.get('/api/search/?q=pizza')
        self.assertEqual(len(r.data['restaurants']), 1)
        self.assertEqual(len(r.data['food_items']), 1)
        self.assertEqual(
            self.client.get(
                '/api/foods/?search=margh&max_price=10'
            ).data['count'],
            1
        )
        self.assertEqual(
            self.client.get(f'/api/restaurants/{rid}/menu/').status_code,
            200
        )

        # owner deletes own food
        self.auth(owner)
        self.assertEqual(
            self.client.delete(f'/api/foods/{fid}/').status_code,
            204
        )

    def test_owner_cannot_be_deleted_if_restaurant_exists(self):
        owner = User.objects.get(username='owner1')

        Restaurant.objects.create(
            owner=owner,
            name='Test Restaurant',
            address='Test Address',
        )

        with self.assertRaises(ProtectedError):
            owner.delete()

    def test_restaurant_cannot_be_deleted_if_food_exists(self):
        owner = User.objects.get(username='owner1')

        restaurant = Restaurant.objects.create(
            owner=owner,
            name='Test Restaurant',
            address='Test Address',
        )

        FoodItem.objects.create(
            restaurant=restaurant,
            name='Test Pizza',
            price='10.00',
        )

        with self.assertRaises(ProtectedError):
            restaurant.delete()

    def test_employee_can_be_added_to_restaurant_staff(self):
        owner = User.objects.get(username='owner1')

        employee = User.objects.create_user(
            username='employee1',
            email='employee1@example.test',
            password=self.password,
        )

        restaurant = Restaurant.objects.create(
            owner=owner,
            name='Test Restaurant',
            address='Test Address',
        )

        restaurant.staff.add(employee)

        self.assertIn(employee, restaurant.staff.all())
        self.assertIn(restaurant, employee.staff_restaurants.all())

    def test_food_item_price_must_be_positive(self):
        owner = User.objects.get(username='owner1')

        restaurant = Restaurant.objects.create(
            owner=owner,
            name='Test Restaurant',
            address='Test Address',
        )

        for price in ('0.00', '-1.00'):
            with self.subTest(price=price):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        FoodItem.objects.create(
                            restaurant=restaurant,
                            name='Invalid Food',
                            price=price,
                        )