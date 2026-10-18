from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class AccountsAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = 'priyasharma'
        self.email = 'priya@example.com'
        self.password = 'ComplexPass123!'
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )

    def test_landing_page_accessible_for_anonymous_user(self):
        response = self.client.get(reverse('accounts:landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stop staring at your closet.')
        self.assertContains(response, 'Get Started Free')

    def test_landing_page_redirects_authenticated_user_to_dashboard(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('accounts:landing'))
        self.assertRedirects(response, reverse('accounts:dashboard'))

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse('accounts:dashboard'))
        expected_url = f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}"
        self.assertRedirects(response, expected_url)

    def test_dashboard_accessible_when_authenticated(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Hello, {self.username}!")
        self.assertContains(response, "Your closet is empty")

    def test_user_registration_success(self):
        signup_data = {
            'username': 'arjunmehta',
            'email': 'arjun@example.com',
            'password1': 'Pass987654#',
            'password2': 'Pass987654#',
        }
        response = self.client.post(reverse('accounts:signup'), data=signup_data)
        self.assertRedirects(response, reverse('accounts:dashboard'))
        self.assertTrue(User.objects.filter(username='arjunmehta').exists())
        # Check automatic session login
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='arjunmehta').id)

    def test_user_registration_duplicate_email_fails(self):
        signup_data = {
            'username': 'anotheruser',
            'email': self.email,  # duplicate email
            'password1': 'Pass987654#',
            'password2': 'Pass987654#',
        }
        response = self.client.post(reverse('accounts:signup'), data=signup_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 'An account with this email address already exists.')

    def test_user_registration_mismatched_passwords_fails(self):
        signup_data = {
            'username': 'anotheruser',
            'email': 'unique@example.com',
            'password1': 'Pass987654#',
            'password2': 'DifferentPass#',
        }
        response = self.client.post(reverse('accounts:signup'), data=signup_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='anotheruser').exists())

    def test_user_login_success(self):
        response = self.client.post(reverse('accounts:login'), data={
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response, reverse('accounts:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

    def test_user_login_invalid_credentials_fails(self):
        response = self.client.post(reverse('accounts:login'), data={
            'username': self.username,
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_user_logout(self):
        self.client.login(username=self.username, password=self.password)
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:landing'))
        self.assertNotIn('_auth_user_id', self.client.session)
