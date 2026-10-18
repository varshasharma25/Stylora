import io
import json
from unittest.mock import patch, MagicMock
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.wardrobe.models import Category, ClothingItem
from apps.stylist.models import ChatSession, ChatMessage
from apps.outfits.models import Outfit, OutfitItem
from services.ai_service import OutfitResponseSchema, RecommendedItemRef


def create_test_image(format='JPEG', size=(400, 400), color=(80, 120, 200)):
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    return SimpleUploadedFile("item.jpg", file_obj.read(), content_type="image/jpeg")


class StyloraFullJourneyIntegrationTests(TestCase):
    """
    End-to-End Integration Test covering the complete user journey across all apps:
    Accounts -> Wardrobe -> Stylist -> Outfits.
    """

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_complete_end_to_end_user_journey(self, mock_generate_outfit):
        client = Client()

        # 1. User Registration & Session Login
        signup_data = {
            'username': 'priya_journey',
            'email': 'priya_journey@example.com',
            'password1': 'StyloraSecurePass1!',
            'password2': 'StyloraSecurePass1!',
        }
        resp = client.post(reverse('accounts:signup'), data=signup_data)
        self.assertRedirects(resp, reverse('accounts:dashboard'))
        user = User.objects.get(username='priya_journey')

        # 2. View Dashboard (Empty Closet)
        resp = client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Your closet is empty')
        self.assertContains(resp, '0 Saved')

        # 3. Add 3 Wardrobe Items (Top, Bottom, Shoes)
        cat_tops = Category.objects.get(slug='tops')
        cat_bottoms = Category.objects.get(slug='bottoms')
        cat_shoes = Category.objects.get(slug='footwear')

        test_img = create_test_image()

        # Item 1: Top
        resp = client.post(reverse('wardrobe:item-create'), {
            'name': 'Crisp White Shirt',
            'category': cat_tops.id,
            'primary_color': 'White',
            'pattern': 'solid',
            'season': 'all',
            'original_image': create_test_image(),
        })
        self.assertRedirects(resp, reverse('wardrobe:gallery'))
        item_top = ClothingItem.objects.get(user=user, name='Crisp White Shirt')

        # Item 2: Bottom
        resp = client.post(reverse('wardrobe:item-create'), {
            'name': 'Navy Chinos',
            'category': cat_bottoms.id,
            'primary_color': 'Navy',
            'pattern': 'solid',
            'season': 'all',
            'original_image': create_test_image(),
        })
        self.assertRedirects(resp, reverse('wardrobe:gallery'))
        item_bottom = ClothingItem.objects.get(user=user, name='Navy Chinos')

        # Item 3: Shoes
        resp = client.post(reverse('wardrobe:item-create'), {
            'name': 'Tan Leather Loafers',
            'category': cat_shoes.id,
            'primary_color': 'Tan',
            'pattern': 'solid',
            'season': 'all',
            'original_image': create_test_image(),
        })
        self.assertRedirects(resp, reverse('wardrobe:gallery'))
        item_shoes = ClothingItem.objects.get(user=user, name='Tan Leather Loafers')

        # 4. View Wardrobe Gallery
        resp = client.get(reverse('wardrobe:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Crisp White Shirt')
        self.assertContains(resp, 'Navy Chinos')
        self.assertContains(resp, 'Tan Leather Loafers')

        # 5. Access Stylist Chat
        resp = client.get(reverse('stylist:chat'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '3 closet items')

        # 6. Request Initial Outfit from AI Stylist
        mock_generate_outfit.return_value = OutfitResponseSchema(
            outfit_title="Smart Casual Coffee Look",
            styling_explanation="Crisp white and navy create a timeless foundation with tan loafers.",
            missing_elements_advice="Add a brown belt to tie in the shoes.",
            items=[
                RecommendedItemRef(item_id=item_top.id, slot="top", item_name=item_top.name),
                RecommendedItemRef(item_id=item_bottom.id, slot="bottom", item_name=item_bottom.name),
                RecommendedItemRef(item_id=item_shoes.id, slot="shoes", item_name=item_shoes.name),
            ]
        )

        resp = client.post(reverse('stylist:send-message'), {'prompt': 'Coffee date outfit'})
        self.assertEqual(resp.status_code, 200)
        chat_data = resp.json()
        self.assertTrue(chat_data['success'])
        self.assertEqual(chat_data['outfit']['outfit_title'], 'Smart Casual Coffee Look')
        self.assertEqual(len(chat_data['outfit']['items']), 3)

        # 7. Conversational Follow-up: Refinement Request
        mock_generate_outfit.return_value = OutfitResponseSchema(
            outfit_title="Evening Dinner Elegance",
            styling_explanation="Refined for dinner with sharp lines and elevated accessories.",
            items=[
                RecommendedItemRef(item_id=item_top.id, slot="top", item_name=item_top.name),
                RecommendedItemRef(item_id=item_bottom.id, slot="bottom", item_name=item_bottom.name),
            ]
        )

        resp = client.post(reverse('stylist:send-message'), {'prompt': 'Make this more formal for evening dinner.'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        # 8. Save the Outfit to Lookbook
        save_payload = {
            'outfit_title': 'Smart Casual Coffee Look',
            'styling_explanation': 'Crisp white and navy create a timeless foundation.',
            'occasion': 'Coffee Date',
            'missing_elements_advice': 'Add a brown leather belt.',
            'item_ids': [item_top.id, item_bottom.id, item_shoes.id],
        }
        resp = client.post(
            reverse('outfits:save'),
            data=json.dumps(save_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        saved_id = resp.json()['outfit_id']
        self.assertTrue(Outfit.objects.filter(id=saved_id, user=user).exists())

        # 9. Verify Saved Looks Gallery
        resp = client.get(reverse('outfits:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Smart Casual Coffee Look')
        self.assertContains(resp, 'Coffee Date')
        self.assertContains(resp, 'Crisp White Shirt')

        # 10. Dashboard Reflects Saved Outfit Count
        resp = client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1 Saved')
        self.assertContains(resp, 'curated outfit(s) saved in your lookbook')

        # 11. Soft-Delete Wardrobe Item & Verify Lookbook Resilience
        item_top.is_active = False
        item_top.save()

        resp = client.get(reverse('outfits:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Smart Casual Coffee Look')
        self.assertContains(resp, '(Deleted from closet)')

        # 12. Delete Outfit from Lookbook
        resp = client.post(
            reverse('outfits:delete', kwargs={'pk': saved_id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Outfit.objects.filter(id=saved_id).exists())


class StyloraMultiTenantSecurityBoundaryTests(TestCase):
    """
    Security boundary tests ensuring strict tenant isolation across all endpoints.
    """

    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(username='alice', email='alice@test.com', password='Password123!')
        self.user_b = User.objects.create_user(username='bob', email='bob@test.com', password='Password123!')

        self.client_a.login(username='alice', password='Password123!')
        self.client_b.login(username='bob', password='Password123!')

        cat_tops = Category.objects.get(slug='tops')
        img = create_test_image()
        self.item_a = ClothingItem.objects.create(
            user=self.user_a, category=cat_tops, name="Alice's Silk Top",
            primary_color='Ivory', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )

        self.outfit_a = Outfit.objects.create(
            user=self.user_a,
            name="Alice's Private Outfit",
            styling_explanation="Confidential styling."
        )
        OutfitItem.objects.create(outfit=self.outfit_a, clothing_item=self.item_a, slot='top')

    def test_cross_user_protected_media_blocked(self):
        url = reverse('wardrobe:protected-media', kwargs={'pk': self.item_a.pk, 'version': 'thumb'})
        # Bob cannot access Alice's photo
        resp = self.client_b.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_cross_user_item_edit_blocked(self):
        url = reverse('wardrobe:item-edit', kwargs={'pk': self.item_a.pk})
        resp = self.client_b.post(url, {'name': 'Hacked Name'})
        self.assertEqual(resp.status_code, 404)
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.name, "Alice's Silk Top")

    def test_cross_user_outfit_save_blocked(self):
        # Bob tries to save an outfit referencing Alice's clothing item
        payload = {
            'outfit_title': "Bob's Attack Outfit",
            'styling_explanation': "Attempting to use Alice's item.",
            'item_ids': [self.item_a.id],
        }
        resp = self.client_b.post(
            reverse('outfits:save'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Outfit.objects.filter(user=self.user_b).exists())

    def test_cross_user_outfit_delete_blocked(self):
        # Bob tries to delete Alice's saved outfit
        url = reverse('outfits:delete', kwargs={'pk': self.outfit_a.pk})
        resp = self.client_b.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Outfit.objects.filter(id=self.outfit_a.id).exists())


class StyloraTemplateAccessibilityAndResponsivenessTests(TestCase):
    """
    Template and accessibility audit for WCAG AA compliance and responsive markup.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='a11y_user', email='a11y@test.com', password='Password123!')
        self.client.login(username='a11y_user', password='Password123!')

    def test_health_check_endpoint(self):
        resp = self.client.get(reverse('health-check'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['app'], 'Stylora')

    def test_all_pages_include_accessible_landmarks_and_responsive_nav(self):
        endpoints = [
            reverse('accounts:dashboard'),
            reverse('wardrobe:gallery'),
            reverse('wardrobe:item-create'),
            reverse('stylist:chat'),
            reverse('outfits:gallery'),
        ]

        for url in endpoints:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                # Verify landmark roles and navigation
                self.assertContains(resp, 'id="main-content"')
                self.assertContains(resp, 'aria-label="Primary Desktop Navigation"')
                self.assertContains(resp, 'class="mobile-bottom-nav"')
                self.assertContains(resp, 'aria-label="Mobile Bottom Navigation"')
                # Verify viewport meta tag for responsive scaling
                self.assertContains(resp, '<meta name="viewport" content="width=device-width, initial-scale=1.0">')


class StyloraSecurityHardeningTests(TestCase):
    """
    Security verification tests for abuse controls, path traversal prevention,
    and denial-of-service resilience.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username='sec_user', email='sec@test.com', password='Password123!')
        self.client.login(username='sec_user', password='Password123!')

    def test_rate_limiter_blocks_abusive_requests(self):
        """RateLimiter correctly throttles bursts exceeding max_requests threshold."""
        from services.security_service import RateLimiter
        # Simulate 20 allowed requests
        for _ in range(20):
            self.assertFalse(RateLimiter.is_rate_limited('test_user', 'test_action', max_requests=20, window_seconds=60))
        # 21st request must be rate-limited
        self.assertTrue(RateLimiter.is_rate_limited('test_user', 'test_action', max_requests=20, window_seconds=60))

    def test_uploaded_file_uses_uuid_and_prevents_path_traversal(self):
        """Malicious filenames like '../../hack.jpg' are strictly sanitized to UUIDs."""
        import re
        cat = Category.objects.get(slug='tops')
        malicious_file = create_test_image()
        malicious_file.name = "../../../etc/passwd_exploit.png"

        resp = self.client.post(reverse('wardrobe:item-create'), {
            'name': 'Path Traversal Test Item',
            'category': cat.id,
            'primary_color': 'Black',
            'pattern': 'solid',
            'season': 'all',
            'original_image': malicious_file,
        })
        self.assertEqual(resp.status_code, 302)

        item = ClothingItem.objects.get(name='Path Traversal Test Item')
        # Filename on disk must be a 32-character hex UUID followed by _clean.jpg
        orig_filename = item.original_image.name.rsplit('/', 1)[-1]
        self.assertNotIn('passwd', orig_filename)
        self.assertNotIn('..', orig_filename)
        self.assertTrue(re.match(r'^[0-9a-f]{32}_clean\.jpg$', orig_filename), f"Filename '{orig_filename}' is not a UUID")

    def test_decompression_bomb_rejected(self):
        """Images triggering DecompressionBombError are caught and rejected cleanly."""
        from services.image_service import ImageProcessingService
        from django.core.exceptions import ValidationError
        img_file = create_test_image()

        with patch('PIL.Image.open') as mock_open:
            mock_open.side_effect = Image.DecompressionBombError("Too many pixels")
            with self.assertRaises(ValidationError) as cm:
                ImageProcessingService.validate_and_process_upload(img_file)
            self.assertIn("decompression risk", str(cm.exception))

