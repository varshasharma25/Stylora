import io
from PIL import Image
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.wardrobe.models import Category, ClothingItem
from apps.stylist.models import ChatSession, ChatMessage
from services.ai_service import AIService, AIServiceError, OutfitResponseSchema, RecommendedItemRef


def create_test_image(format='JPEG', size=(200, 200), color=(100, 100, 200)):
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    return SimpleUploadedFile("item.jpg", file_obj.read(), content_type="image/jpeg")


class StylistRecommendationAndValidationTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(username='priya', email='priya@test.com', password='Password123!')
        self.user_b = User.objects.create_user(username='arjun', email='arjun@test.com', password='Password123!')

        self.client_a.login(username='priya', password='Password123!')
        self.client_b.login(username='arjun', password='Password123!')

        self.cat_tops = Category.objects.get(slug='tops')
        self.cat_bottoms = Category.objects.get(slug='bottoms')
        self.cat_shoes = Category.objects.get(slug='footwear')

        # User A's wardrobe items (3 items)
        img = create_test_image()
        self.item_a1 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Pink Kurta',
            primary_color='Pink', pattern='floral', season='all',
            original_image=img, thumbnail_image=img
        )
        self.item_a2 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_bottoms, name='Blue Slim Jeans',
            primary_color='Blue', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )
        self.item_a3 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_shoes, name='Pink Sneakers',
            primary_color='Pink', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )

        # User B's wardrobe item (1 item)
        self.item_b1 = ClothingItem.objects.create(
            user=self.user_b, category=self.cat_tops, name='Arjun Black Shirt',
            primary_color='Black', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )

        self.send_url = reverse('stylist:send-message')

    def test_stylist_chat_view_renders_cleanly(self):
        resp = self.client_a.get(reverse('stylist:chat'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'AI Personal Stylist')
        self.assertContains(resp, '3 closet items')

    def test_unauthenticated_request_redirects_to_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('stylist:chat'))
        self.assertEqual(resp.status_code, 302)

        resp_post = anon_client.post(self.send_url, {'prompt': 'Style me'})
        self.assertEqual(resp_post.status_code, 302)

    def test_empty_wardrobe_returns_helpful_feedback(self):
        # User without any clothes
        empty_user = User.objects.create_user(username='emptyuser', password='Password123!')
        client = Client()
        client.login(username='emptyuser', password='Password123!')

        resp = client.post(self.send_url, {'prompt': 'College presentation outfit'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("wardrobe is empty", data['error'])

    def test_small_wardrobe_less_than_three_items_returns_notice(self):
        # User with only 1 item
        resp = self.client_b.post(self.send_url, {'prompt': 'College presentation outfit'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("at least a top, bottom, and shoes", data['error'])

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_valid_recommendation_flow_success(self, mock_generate):
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Festive Casual Pink Pop",
            styling_explanation="The pink sneakers echo the vibrant color in your kurta while jeans ground the look.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ],
            missing_elements_advice="A subtle silver watch would complement this nicely."
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Outfit for college fest with my pink sneakers'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['outfit']['outfit_title'], "Festive Casual Pink Pop")
        self.assertEqual(len(data['outfit']['items']), 3)

        # Verify chat messages were stored in database
        self.assertTrue(ChatMessage.objects.filter(session__user=self.user_a, sender='user').exists())
        self.assertTrue(ChatMessage.objects.filter(session__user=self.user_a, sender='assistant').exists())

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_hallucinated_fabricated_id_is_strictly_rejected(self, mock_generate):
        # AI returns valid items + a fabricated ID 99999
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Look with Hallucinated ID",
            styling_explanation="Great style combination.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=99999, slot="bottom", item_name="Imaginary Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'College look'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        # Fabricated ID must be stripped; only 2 verified items remain
        item_ids = [item['id'] for item in data['outfit']['items']]
        self.assertIn(self.item_a1.id, item_ids)
        self.assertIn(self.item_a3.id, item_ids)
        self.assertNotIn(99999, item_ids)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_foreign_user_id_is_strictly_rejected_cross_user_boundary(self, mock_generate):
        # CRITICAL SECURITY TEST: AI model attempts to recommend User B's item to User A
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Cross User Attack Attempt",
            styling_explanation="Stylish attempt.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_b1.id, slot="top", item_name="Arjun Black Shirt"), # Foreign!
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Style me'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        # User B's item ID MUST NOT appear in User A's response
        item_ids = [item['id'] for item in data['outfit']['items']]
        self.assertIn(self.item_a1.id, item_ids)
        self.assertIn(self.item_a2.id, item_ids)
        self.assertNotIn(self.item_b1.id, item_ids)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_duplicate_item_ids_deduplicated(self, mock_generate):
        # AI returns the same item ID twice
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Duplicate ID Look",
            styling_explanation="Explanation.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_a1.id, slot="layer", item_name="Pink Kurta Again"),
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Style me'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        item_ids = [item['id'] for item in data['outfit']['items']]
        self.assertEqual(len(item_ids), 2)
        self.assertEqual(item_ids.count(self.item_a1.id), 1)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_ai_service_failure_returns_graceful_message(self, mock_generate):
        mock_generate.side_effect = AIServiceError("Stylora is experiencing heavy demand.")
        resp = self.client_a.post(self.send_url, {'prompt': 'Party outfit'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("heavy demand", data['error'])
