
from rest_framework.test import APITestCase
from accounts.models import User, CustomerProfile


class AccountsTests(APITestCase):
    password = 'Old!StrongPass2026'

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password=self.password
        )

    def test_user_registration(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'T3st!SecurePass2026',
            'first_name': 'Test',
            'last_name': 'User'
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_registration_creates_customer_profile(self):
        self.client.post('/api/auth/register/', {
            'username': 'profileuser',
            'email': 'profile@example.com',
            'password': 'T3st!SecurePass2026'
        }, format='json')

        user = User.objects.get(username='profileuser')
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_password_is_hashed(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'hashuser',
            'email': 'hash@example.com',
            'password': 'T3st!SecurePass2026'
        }, format='json')

        user = User.objects.get(username='hashuser')
        self.assertNotEqual(user.password, 'T3st!SecurePass2026')
        self.assertTrue(user.check_password('T3st!SecurePass2026'))

    def test_duplicate_email_registration_is_rejected(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'anotheruser',
            'email': 'test@example.com',
            'password': 'T3st!SecurePass2026'
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_profile_requires_authentication(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 401)

    def test_user_can_view_and_update_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch('/api/profile/', {
            'phone': '123456789',
            'city': 'Almaty',
            'address': 'Abay Street'
        }, format='json')

        self.assertEqual(response.status_code, 200)

        profile = CustomerProfile.objects.get(user=self.user)
        self.assertEqual(profile.city, 'Almaty')
        self.assertEqual(profile.phone, '123456789')

    def test_duplicate_email_in_profile_is_rejected(self):
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password=self.password
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.patch('/api/profile/', {
            'email': 'other@example.com'
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_wrong_old_password_is_rejected(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post('/api/auth/change-password/', {
            'old_password': 'WrongPassword123!',
            'new_password': 'BrandNew!Pass2026'
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_user_can_change_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post('/api/auth/change-password/', {
            'old_password': self.password,
            'new_password': 'BrandNew!Pass2026'
        }, format='json')

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNew!Pass2026'))
