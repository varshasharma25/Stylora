import io
from PIL import Image
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import UserProfile
from apps.wardrobe.models import Category, ClothingItem
from apps.outfits.models import Outfit, OutfitItem
from services.ai_service import (
    AIService,
    AIServiceError,
    OutfitResponseSchema,
    RecommendedItemRef,
)


def create_test_image(format='JPEG', size=(200, 200), color=(120, 140, 200)):
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    return SimpleUploadedFile("item.jpg", file_obj.read(), content_type="image/jpeg")


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
        self.assertContains(response, 'Digital Wardrobe')

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

    def test_footer_renders_privacy_safe_contact_links_and_no_personal_email(self):
        response = self.client.get(reverse('accounts:landing'))
        self.assertEqual(response.status_code, 200)
        # Ensure hardcoded personal email is never rendered publicly
        self.assertNotContains(response, 'varsharma2710@gmail.com')
        # Ensure public professional links are present and valid
        self.assertContains(response, 'Contact: Varsha Sharma')
        self.assertContains(response, 'https://github.com/varshasharma25')
        self.assertContains(response, 'https://linkedin.com/in/varsha-sharma-72b652366/')


class UserProfileAndPreferencesTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(
            username='priya',
            email='priya@example.com',
            first_name='Priya',
            last_name='Sharma',
            password='Password123!'
        )
        self.user_b = User.objects.create_user(
            username='arjun',
            email='arjun@example.com',
            first_name='Arjun',
            last_name='Mehta',
            password='Password123!'
        )

        self.client_a.login(username='priya', password='Password123!')
        self.client_b.login(username='arjun', password='Password123!')
        self.profile_url = reverse('accounts:profile')
        self.password_url = reverse('accounts:password-change')

    def test_profile_requires_authentication(self):
        anon_client = Client()
        response = anon_client.get(self.profile_url)
        expected_redirect = f"{reverse('accounts:login')}?next={self.profile_url}"
        self.assertRedirects(response, expected_redirect)

    def test_profile_renders_user_data_and_existing_preferences(self):
        profile_a = UserProfile.objects.create(
            user=self.user_a,
            preferred_aesthetic='minimalist',
            fit_preference='regular',
            dressing_goal='capsule_wardrobe',
            favorite_colors='Navy Blue, White, Beige',
            color_season='cool_summer',
            color_analysis_consent=True
        )

        response = self.client_a.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Priya's Profile")
        self.assertContains(response, "priya@example.com")
        self.assertContains(response, "Navy Blue, White, Beige")
        self.assertContains(response, "Cool Summer")

    def test_profile_update_personal_details_success(self):
        data = {
            'action': 'personal',
            'personal-first_name': 'Priyanka',
            'personal-last_name': 'Kapoor',
            'personal-email': 'priyanka.k@example.com',
        }
        response = self.client_a.post(self.profile_url, data=data)
        self.assertRedirects(response, self.profile_url)

        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.first_name, 'Priyanka')
        self.assertEqual(self.user_a.last_name, 'Kapoor')
        self.assertEqual(self.user_a.email, 'priyanka.k@example.com')

    def test_profile_update_personal_details_duplicate_email_fails(self):
        # Attempt to steal User B's email
        data = {
            'action': 'personal',
            'personal-first_name': 'Priya',
            'personal-last_name': 'Sharma',
            'personal-email': 'arjun@example.com',  # User B's email
        }
        response = self.client_a.post(self.profile_url, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email address is already in use by another account.")

        # Ensure database was not changed
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.email, 'priya@example.com')

    def test_profile_update_style_preferences_success(self):
        data = {
            'action': 'style',
            'style-bio': 'Loves effortless chic combinations for daily wear.',
            'style-preferred_aesthetic': 'chic',
            'style-fit_preference': 'relaxed',
            'style-dressing_goal': 'everyday_comfort',
            'style-favorite_colors': 'Terracotta, Olive, Cream',
        }
        response = self.client_a.post(self.profile_url, data=data)
        self.assertRedirects(response, self.profile_url)

        profile = self.user_a.profile
        profile.refresh_from_db()
        self.assertEqual(profile.preferred_aesthetic, 'chic')
        self.assertEqual(profile.fit_preference, 'relaxed')
        self.assertEqual(profile.dressing_goal, 'everyday_comfort')
        self.assertEqual(profile.favorite_colors, 'Terracotta, Olive, Cream')
        self.assertEqual(profile.bio, 'Loves effortless chic combinations for daily wear.')

    def test_profile_update_color_preferences_with_consent(self):
        data = {
            'action': 'color',
            'color-color_season': 'warm_autumn',
            'color-color_palette_notes': 'Rich warm earthy tones like rust, mustard, and moss.',
            'color-color_analysis_consent': 'on',
        }
        response = self.client_a.post(self.profile_url, data=data)
        self.assertRedirects(response, self.profile_url)

        profile = self.user_a.profile
        profile.refresh_from_db()
        self.assertEqual(profile.color_season, 'warm_autumn')
        self.assertEqual(profile.color_palette_notes, 'Rich warm earthy tones like rust, mustard, and moss.')
        self.assertTrue(profile.color_analysis_consent)

    def test_profile_user_isolation(self):
        # User A sets preferences
        self.client_a.post(self.profile_url, data={
            'action': 'style',
            'style-preferred_aesthetic': 'streetwear',
            'style-fit_preference': 'oversized',
            'style-dressing_goal': 'bold_creative',
            'style-favorite_colors': 'Black, Neon Orange',
        })

        # User B views profile -> User B's profile must be clean and unpolluted
        response_b = self.client_b.get(self.profile_url)
        self.assertEqual(response_b.status_code, 200)
        self.assertContains(response_b, "Arjun's Profile")
        self.assertNotContains(response_b, "Neon Orange")

        profile_b = UserProfile.objects.get(user=self.user_b)
        self.assertEqual(profile_b.preferred_aesthetic, '')
        self.assertEqual(profile_b.favorite_colors, '')

    def test_password_change_requires_authentication(self):
        anon_client = Client()
        response = anon_client.get(self.password_url)
        expected_redirect = f"{reverse('accounts:login')}?next={self.password_url}"
        self.assertRedirects(response, expected_redirect)

    def test_password_change_success(self):
        response = self.client_a.get(self.password_url)
        self.assertEqual(response.status_code, 200)

        post_data = {
            'old_password': 'Password123!',
            'new_password1': 'BrandNewPassword999!',
            'new_password2': 'BrandNewPassword999!',
        }
        resp = self.client_a.post(self.password_url, data=post_data)
        self.assertRedirects(resp, self.profile_url)

        # Verify new password authenticates successfully
        login_success = self.client_a.login(username='priya', password='BrandNewPassword999!')
        self.assertTrue(login_success)

    def test_password_change_invalid_old_password_fails(self):
        post_data = {
            'old_password': 'WrongOldPassword!',
            'new_password1': 'BrandNewPassword999!',
            'new_password2': 'BrandNewPassword999!',
        }
        resp = self.client_a.post(self.password_url, data=post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your old password was entered incorrectly.")


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }
)
class FashionDashboardAndTodayOutfitTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(
            username='kavya', email='kavya@example.com', password='Password123!'
        )
        self.user_b = User.objects.create_user(
            username='dev', email='dev@example.com', password='Password123!'
        )

        self.client_a.login(username='kavya', password='Password123!')
        self.client_b.login(username='dev', password='Password123!')

        self.dashboard_url = reverse('accounts:dashboard')
        self.today_url = reverse('accounts:today-outfit')

        self.cat_tops = Category.objects.get(slug='tops')
        self.cat_bottoms = Category.objects.get(slug='bottoms')
        self.cat_shoes = Category.objects.get(slug='footwear')
        self.cat_acc = Category.objects.get(slug='accessories')

    def test_dashboard_requires_authentication(self):
        anon = Client()
        resp = anon.get(self.dashboard_url)
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={self.dashboard_url}")

    def test_today_outfit_requires_authentication(self):
        anon = Client()
        resp = anon.post(self.today_url, {})
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={self.today_url}")

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_dashboard_page_load_and_refresh_never_calls_ai_automatically(self, mock_ai):
        # 1. First GET load
        resp = self.client_a.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
        mock_ai.assert_not_called()

        # 2. Page refresh
        resp2 = self.client_a.get(self.dashboard_url)
        self.assertEqual(resp2.status_code, 200)
        mock_ai.assert_not_called()

    def test_dashboard_renders_accurate_wardrobe_statistics_and_shortcuts(self):
        img = create_test_image()
        # Create items for user A: 2 tops, 1 bottom, 1 footwear, 1 accessory
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Cotton Shirt',
            primary_color='White', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Linen Kurta',
            primary_color='Navy', pattern='solid', season='summer', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_bottoms, name='Beige Chinos',
            primary_color='Beige', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_shoes, name='White Loafers',
            primary_color='White', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_acc, name='Leather Belt',
            primary_color='Brown', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        resp = self.client_a.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
        # Check counts
        self.assertEqual(resp.context['wardrobe_count'], 5)
        self.assertEqual(resp.context['tops_count'], 2)
        self.assertEqual(resp.context['bottoms_count'], 1)
        self.assertEqual(resp.context['shoes_count'], 1)
        self.assertEqual(resp.context['accessories_count'], 1)

        # Check navigation shortcuts
        self.assertContains(resp, "My Closet")
        self.assertContains(resp, "AI Stylist")
        self.assertContains(resp, "Find My Colour")
        self.assertContains(resp, "Saved Looks")

    def test_dashboard_user_isolation(self):
        img = create_test_image()
        # User A has 3 items
        for i in range(3):
            ClothingItem.objects.create(
                user=self.user_a, category=self.cat_tops, name=f'Top {i}',
                primary_color='Blue', pattern='solid', season='all', original_image=img, thumbnail_image=img
            )

        # User B has 1 item
        ClothingItem.objects.create(
            user=self.user_b, category=self.cat_bottoms, name='User B Jeans',
            primary_color='Black', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        # User A's dashboard
        resp_a = self.client_a.get(self.dashboard_url)
        self.assertEqual(resp_a.context['wardrobe_count'], 3)

        # User B's dashboard
        resp_b = self.client_b.get(self.dashboard_url)
        self.assertEqual(resp_b.context['wardrobe_count'], 1)
        self.assertNotContains(resp_b, "Top 0")

    def test_today_outfit_empty_wardrobe_response(self):
        # User with 0 items requests Today's Outfit
        with patch('services.ai_service.AIService.generate_wardrobe_outfit') as mock_ai:
            resp = self.client_a.post(self.today_url)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertFalse(data['success'])
            self.assertTrue(data.get('empty'))
            self.assertIn("closet is empty", data['error'])
            mock_ai.assert_not_called()

    def test_today_outfit_incomplete_wardrobe_response(self):
        img = create_test_image()
        # User has only 1 item
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Solo Shirt',
            primary_color='White', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        with patch('services.ai_service.AIService.generate_wardrobe_outfit') as mock_ai:
            resp = self.client_a.post(self.today_url)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertFalse(data['success'])
            self.assertTrue(data.get('incomplete'))
            self.assertIn("at least 3 items", data['error'])
            mock_ai.assert_not_called()

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_today_outfit_on_demand_generation_success(self, mock_ai):
        img = create_test_image()
        item1 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Floral Top',
            primary_color='Pink', pattern='floral', season='all', original_image=img, thumbnail_image=img
        )
        item2 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_bottoms, name='Blue Jeans',
            primary_color='Blue', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        item3 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_shoes, name='White Sneakers',
            primary_color='White', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        mock_ai.return_value = OutfitResponseSchema(
            outfit_title="Fresh Daily Chic",
            styling_explanation="Balanced casual chic look for daytime.",
            items=[
                RecommendedItemRef(item_id=item1.id, slot="top", item_name=item1.name),
                RecommendedItemRef(item_id=item2.id, slot="bottom", item_name=item2.name),
                RecommendedItemRef(item_id=item3.id, slot="shoes", item_name=item3.name),
            ]
        )

        resp = self.client_a.post(self.today_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['outfit']['outfit_title'], "Fresh Daily Chic")
        self.assertEqual(len(data['outfit']['items']), 3)
        mock_ai.assert_called_once()

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_today_outfit_rule_8_firewall_filters_foreign_items(self, mock_ai):
        img = create_test_image()
        # Items belonging to User A
        item_a = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='User A Top',
            primary_color='Pink', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_bottoms, name='User A Bottom',
            primary_color='Blue', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )
        ClothingItem.objects.create(
            user=self.user_a, category=self.cat_shoes, name='User A Shoes',
            primary_color='White', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        # Item belonging to User B
        item_b = ClothingItem.objects.create(
            user=self.user_b, category=self.cat_tops, name='User B Forbidden Top',
            primary_color='Red', pattern='solid', season='all', original_image=img, thumbnail_image=img
        )

        # AI maliciously or accidentally returns User B's item ID and a nonexistent ID
        mock_ai.return_value = OutfitResponseSchema(
            outfit_title="Mixed Outfit",
            styling_explanation="Explanation.",
            items=[
                RecommendedItemRef(item_id=item_a.id, slot="top", item_name=item_a.name),
                RecommendedItemRef(item_id=item_b.id, slot="bottom", item_name=item_b.name),
                RecommendedItemRef(item_id=99999, slot="shoes", item_name="Ghost Item"),
            ]
        )

        resp = self.client_a.post(self.today_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        # Only User A's item remains in sanitized items!
        returned_ids = [i['id'] for i in data['outfit']['items']]
        self.assertIn(item_a.id, returned_ids)
        self.assertNotIn(item_b.id, returned_ids)
        self.assertNotIn(99999, returned_ids)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_today_outfit_ai_error_handling(self, mock_ai):
        img = create_test_image()
        for i in range(3):
            ClothingItem.objects.create(
                user=self.user_a, category=self.cat_tops, name=f'Top {i}',
                primary_color='Blue', pattern='solid', season='all', original_image=img, thumbnail_image=img
            )

        mock_ai.side_effect = AIServiceError("Gemini service connection timeout")

        resp = self.client_a.post(self.today_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("connection timeout", data['error'])



