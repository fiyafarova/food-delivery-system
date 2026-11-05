from rest_framework.test import APITestCase
from accounts.models import User
from .models import Category


class FlowTests(APITestCase):
    def register_login(self, username, role):
        r = self.client.post('/api/auth/register/', {
            'username': username, 'email': f'{username}@x.com',
            'password': 'Str0ng!Pass99', 'role': role}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        t = self.client.post('/api/auth/login/', {
            'username': username, 'password': 'Str0ng!Pass99'}, format='json')
        self.assertEqual(t.status_code, 200)
        return t.data['access']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_full_flow(self):
        owner = self.register_login('owner1', 'owner')
        other = self.register_login('owner2', 'owner')
        cust = self.register_login('cust1', 'customer')

        # profile
        self.auth(cust)
        r = self.client.patch('/api/profile/', {'phone': '123', 'city': 'Almaty'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/api/profile/').data['city'], 'Almaty')

        # customer cannot create restaurant
        r = self.client.post('/api/restaurants/', {'name': 'X', 'address': 'Y'}, format='json')
        self.assertEqual(r.status_code, 403)

        # owner creates restaurant
        self.auth(owner)
        r = self.client.post('/api/restaurants/', {
            'name': 'Pizza Palace', 'address': '1 Main St', 'cuisine': 'Italian',
            'city': 'Almaty'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data['id']

        # category: owner cannot, admin can
        r = self.client.post('/api/categories/', {'name': 'Pizza'}, format='json')
        self.assertEqual(r.status_code, 403)
        cat = Category.objects.create(name='Pizza')

        # owner adds food
        r = self.client.post('/api/foods/', {
            'restaurant': rid, 'category': cat.id, 'name': 'Margherita',
            'price': '9.50'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        fid = r.data['id']

        # other owner cannot touch it
        self.auth(other)
        self.assertEqual(self.client.delete(f'/api/foods/{fid}/').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/restaurants/{rid}/').status_code, 403)
        r = self.client.post('/api/foods/', {'restaurant': rid, 'name': 'Hack', 'price': '1'}, format='json')
        self.assertEqual(r.status_code, 400)

        # public search
        self.client.credentials()
        r = self.client.get('/api/search/?q=pizza')
        self.assertEqual(len(r.data['restaurants']), 1)
        self.assertEqual(len(r.data['food_items']), 1)
        self.assertEqual(self.client.get('/api/foods/?search=margh&max_price=10').data['count'], 1)
        self.assertEqual(self.client.get(f'/api/restaurants/{rid}/menu/').status_code, 200)

        # owner deletes own food
        self.auth(owner)
        self.assertEqual(self.client.delete(f'/api/foods/{fid}/').status_code, 204)
