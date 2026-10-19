import io
from PIL import Image
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.wardrobe.models import Category, ClothingItem
from apps.stylist.models import ChatSession, ChatMessage
from apps.accounts.models import UserProfile
from services.ai_service import (
    AIService,
    AIServiceError,
    OutfitResponseSchema,
    RecommendedItemRef,
    ColorAnalysisResult,
    SEASON_PALETTES,
)


def create_test_image(format='JPEG', size=(200, 200), color=(100, 100, 200)):
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    return SimpleUploadedFile("item.jpg", file_obj.read(), content_type="image/jpeg")


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

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_conversational_refinement_passes_context(self, mock_generate):
        """Follow-up requests pass recent chat history and current outfit context to the AI service."""
        # Setup active session with initial conversation
        session = ChatSession.objects.create(user=self.user_a, title='Initial Styling')
        ChatMessage.objects.create(session=session, sender='user', message_text='Casual brunch look')
        ChatMessage.objects.create(
            session=session,
            sender='assistant',
            message_text='Here is your brunch look.',
            raw_response={
                'outfit_title': 'Brunch Look',
                'styling_explanation': 'Casual and breezy.',
                'items': [{'id': self.item_a1.id, 'name': 'Pink Kurta', 'slot': 'Top'}]
            }
        )

        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Refined Formal Look",
            styling_explanation="Elevated formality with darker tones.",
            items=[
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Make this more formal.'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        # Verify AI service was called with chat_history and current_outfit
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs['user_prompt'], 'Make this more formal.')
        self.assertIsNotNone(kwargs['current_outfit'])
        self.assertEqual(kwargs['current_outfit']['outfit_title'], 'Brunch Look')
        self.assertGreaterEqual(len(kwargs['chat_history']), 2)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_replace_item_action(self, mock_generate):
        """Clicking Replace Item generates targeted prompt and adds item to excluded list."""
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Updated Combo",
            styling_explanation="Swapped the top for an alternative.",
            items=[
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {
            'action': 'replace_item',
            'replace_item_id': str(self.item_a1.id)
        })

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        self.assertIn('replace Pink Kurta', kwargs['user_prompt'])
        self.assertIn('Pink Kurta', kwargs['excluded_items'])

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_qa_prompt_casual_and_formal_occasions(self, mock_generate):
        """QA Test: 'Suggest a casual outfit for college' and 'Style something for a formal event'."""
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="College Casual Day",
            styling_explanation="Pink Kurta paired with slim blue jeans offers an effortless campus aesthetic.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Suggest a casual outfit for college.'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['outfit']['outfit_title'], "College Casual Day")
        self.assertIn("effortless campus aesthetic", data['outfit']['styling_explanation'])

        # Now test formal prompt
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Elevated Evening Event",
            styling_explanation="A refined monochrome palette suitable for formal evening dinners.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
            ]
        )
        resp_formal = self.client_a.post(self.send_url, {'prompt': 'Style something for a formal event.'})
        self.assertEqual(resp_formal.status_code, 200)
        self.assertTrue(resp_formal.json()['success'])
        self.assertEqual(resp_formal.json()['outfit']['outfit_title'], "Elevated Evening Event")

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_qa_prompt_required_items_and_exclusions(self, mock_generate):
        """QA Test: Anchoring around specific shoes and excluding jackets."""
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Pink Sneaker Focal Outfit",
            styling_explanation="Outfit centered on your pink sneakers with no jacket required.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ],
            missing_elements_advice="Since you excluded a jacket, consider rolling up sleeves for a casual look."
        )

        resp = self.client_a.post(self.send_url, {
            'prompt': 'Create an outfit around my pink sneakers. I do not have a suitable jacket.',
            'required': 'Pink Sneakers',
            'excluded': 'Jacket, Blazer',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        _, kwargs = mock_generate.call_args
        self.assertIn('Pink Sneakers', kwargs['required_items'])
        self.assertIn('Jacket', kwargs['excluded_items'])
        self.assertEqual(data['outfit']['outfit_title'], "Pink Sneaker Focal Outfit")

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_qa_conversational_followup_keep_shoes_change_top(self, mock_generate):
        """QA Test: 'Keep the shoes and change the top' preserves shoes while swapping top."""
        session = ChatSession.objects.create(user=self.user_a, title='Active QA Session')
        ChatMessage.objects.create(session=session, sender='user', message_text='Initial outfit')
        ChatMessage.objects.create(
            session=session,
            sender='assistant',
            message_text='Here is look 1',
            raw_response={
                'outfit_title': 'Initial Look',
                'items': [
                    {'id': self.item_a1.id, 'name': 'Pink Kurta', 'slot': 'top'},
                    {'id': self.item_a3.id, 'name': 'Pink Sneakers', 'slot': 'shoes'},
                ]
            }
        )

        # Create alternative top for User A
        alt_top = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Linen Tunic',
            primary_color='White', pattern='solid', season='all',
            original_image=create_test_image(), thumbnail_image=create_test_image()
        )

        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Refined Combo with Linen Tunic",
            styling_explanation="Keeping your pink sneakers while swapping to the linen tunic for a lighter silhouette.",
            items=[
                RecommendedItemRef(item_id=alt_top.id, slot="top", item_name="Linen Tunic"),
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Keep the shoes and change the top.'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        returned_ids = [item['id'] for item in data['outfit']['items']]
        self.assertIn(self.item_a3.id, returned_ids)  # Sneakers kept
        self.assertIn(alt_top.id, returned_ids)       # Top changed
        self.assertNotIn(self.item_a1.id, returned_ids) # Old top replaced

    def test_invalid_mode_rejected_with_400(self):
        resp = self.client_a.post(self.send_url, {'prompt': 'Style me', 'mode': 'outerspace'})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("Invalid styling mode", data['error'])

    def test_mode_selector_rendered_in_stylist_chat_view(self):
        resp = self.client_a.get(reverse('stylist:chat'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Styling Focus')
        self.assertContains(resp, 'Full Outfit')
        self.assertContains(resp, 'Tops Only')
        self.assertContains(resp, 'Bottoms Only')
        self.assertContains(resp, 'Shoes Only')
        self.assertContains(resp, 'Accessories Only')

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_tops_only_returns_strictly_tops(self, mock_generate):
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Floral Kurta Highlight",
            styling_explanation="A vibrant floral top perfect for a daytime outing.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Need a cute top', 'mode': 'tops'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        # Verify AIService called with mode='tops'
        self.assertEqual(mock_generate.call_args[1]['mode'], 'tops')

        # Verify returned item is strictly a top
        self.assertEqual(len(data['outfit']['items']), 1)
        self.assertEqual(data['outfit']['items'][0]['id'], self.item_a1.id)
        self.assertEqual(data['outfit']['items'][0]['category'], self.cat_tops.name)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_bottoms_only_returns_strictly_bottoms(self, mock_generate):
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Denim Focus",
            styling_explanation="Comfortable slim jeans for all-day wear.",
            items=[
                RecommendedItemRef(item_id=self.item_a2.id, slot="bottom", item_name="Blue Slim Jeans"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Suggest bottoms', 'mode': 'bottoms'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(mock_generate.call_args[1]['mode'], 'bottoms')
        self.assertEqual(len(data['outfit']['items']), 1)
        self.assertEqual(data['outfit']['items'][0]['id'], self.item_a2.id)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_shoes_only_returns_strictly_footwear(self, mock_generate):
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Sneaker Pick",
            styling_explanation="Casual pink sneakers to match a cheerful mood.",
            items=[
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Comfortable shoes', 'mode': 'shoes'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(mock_generate.call_args[1]['mode'], 'shoes')
        self.assertEqual(len(data['outfit']['items']), 1)
        self.assertEqual(data['outfit']['items'][0]['id'], self.item_a3.id)

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_empty_category_graceful_response_without_ai_call(self, mock_generate):
        # User A has 0 items in 'accessories'
        resp = self.client_a.post(self.send_url, {'prompt': 'Matching handbag', 'mode': 'accessories'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("accessories", data['error'].lower())

        # Crucial check: verify NO AI calls were wasted
        mock_generate.assert_not_called()

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_firewall_drops_disallowed_category_items(self, mock_generate):
        # User requested 'shoes', but AI erroneously returned both shoes AND a top
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Mixed Recommendation",
            styling_explanation="Here is a look.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),  # Top (should be dropped!)
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"), # Footwear (keep!)
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Style my shoes', 'mode': 'shoes'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        returned_ids = [item['id'] for item in data['outfit']['items']]
        self.assertIn(self.item_a3.id, returned_ids)
        self.assertNotIn(self.item_a1.id, returned_ids)  # Top dropped by firewall

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_mode_firewall_all_items_disallowed_returns_error(self, mock_generate):
        # User requested 'shoes', but AI returned only tops
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Wrong Category",
            styling_explanation="A shirt.",
            items=[
                RecommendedItemRef(item_id=self.item_a1.id, slot="top", item_name="Pink Kurta"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Show me shoes', 'mode': 'shoes'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn("couldn't find matching items from your shoes", data['error'].lower())

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_user_isolation_strictly_enforced_in_category_modes(self, mock_generate):
        # AI attempts to return User B's top (item_b1) to User A in 'tops' mode
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="Cross User Attempt",
            styling_explanation="Trying to recommend foreign item.",
            items=[
                RecommendedItemRef(item_id=self.item_b1.id, slot="top", item_name="Arjun Black Shirt"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Give me a top', 'mode': 'tops'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])  # Dropped by user ownership firewall

    @patch('services.ai_service.AIService.generate_wardrobe_outfit')
    def test_single_category_recommendation_can_be_saved_to_lookbook(self, mock_generate):
        # Generate a shoes-only recommendation
        mock_generate.return_value = OutfitResponseSchema(
            outfit_title="My Favorite Sneakers",
            styling_explanation="Great sneakers for casual events.",
            items=[
                RecommendedItemRef(item_id=self.item_a3.id, slot="shoes", item_name="Pink Sneakers"),
            ]
        )

        resp = self.client_a.post(self.send_url, {'prompt': 'Pick shoes', 'mode': 'shoes'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        # Now save this look to lookbook via outfits:save
        save_resp = self.client_a.post(
            reverse('outfits:save'),
            data={
                'outfit_title': data['outfit']['outfit_title'],
                'styling_explanation': data['outfit']['styling_explanation'],
                'item_ids': [self.item_a3.id],
            }
        )
        self.assertEqual(save_resp.status_code, 200)
        save_data = save_resp.json()
        self.assertTrue(save_data['success'])


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
class FindMyColourTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(
            username='ananya',
            email='ananya@example.com',
            password='Password123!'
        )
        self.user_b = User.objects.create_user(
            username='rohit',
            email='rohit@example.com',
            password='Password123!'
        )
        self.profile_a = UserProfile.objects.create(user=self.user_a)
        self.profile_b = UserProfile.objects.create(user=self.user_b)

        self.client_a.login(username='ananya', password='Password123!')
        self.client_b.login(username='rohit', password='Password123!')

        self.analysis_url = reverse('stylist:color-analysis')
        self.save_url = reverse('stylist:color-analysis-save')

        self.valid_q_data = {
            'vein_color': 'green_olive',
            'sun_reaction': 'tans_easily',
            'jewelry': 'gold',
            'contrast': 'medium',
            'preferred_palette': 'earthy',
        }

    def test_find_my_colour_requires_authentication(self):
        anon_client = Client()
        resp = anon_client.get(self.analysis_url)
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={self.analysis_url}")

        resp_save = anon_client.post(self.save_url, {})
        self.assertRedirects(resp_save, f"{reverse('accounts:login')}?next={self.save_url}")

    def test_find_my_colour_get_renders_photo_upload(self):
        resp = self.client_a.get(self.analysis_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Find My Colour")
        self.assertContains(resp, "Upload Daylight Photo")
        self.assertNotContains(resp, "Look at the veins")
        self.assertNotContains(resp, "Privacy Assurance &amp; Ephemeral Processing")

    def test_photo_upload_rule_based_analysis_success(self):
        # Submitting photo without Gemini API key configured falls back gracefully to rule-based palette
        photo = create_test_image(format='JPEG')
        with patch.object(AIService, 'get_api_key', return_value=''):
            resp = self.client_a.post(self.analysis_url, data={'photo': photo})
            self.assertEqual(resp.status_code, 200)

        self.assertContains(resp, "Warm Autumn")
        self.assertContains(resp, "Core Harmony Swatches")
        self.assertContains(resp, "Advisory Notice &amp; Uncertainty Context")
        self.assertContains(resp, "Most Flattering Shades")

    @patch('google.genai.Client')
    def test_questionnaire_with_photo_calls_gemini_vision(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        mock_response = MagicMock()
        mock_response.text = ColorAnalysisResult(
            season='deep_autumn',
            season_name='Deep Autumn',
            undertone='Warm & Deep',
            contrast_level='High',
            best_colors=['Burnt Sienna', 'Dark Olive', 'Burgundy Wine'],
            colors_to_avoid=['Pale Icy Grey', 'Pastel Pink'],
            hex_palette=['#9A3412', '#365314', '#881337', '#451A03', '#115E59', '#D97706'],
            explanation='Your warm rich undertones harmonize with Deep Autumn.'
        ).model_dump_json()
        mock_instance.models.generate_content.return_value = mock_response

        with patch.object(AIService, 'get_api_key', return_value='fake-api-key'):
            test_photo = create_test_image(format='JPEG')
            post_data = dict(self.valid_q_data)
            post_data['photo'] = test_photo

            resp = self.client_a.post(self.analysis_url, data=post_data)
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Deep Autumn")
            self.assertContains(resp, "Burnt Sienna")
            mock_instance.models.generate_content.assert_called_once()

    def test_invalid_photo_format_rejected_with_form_error(self):
        fake_file = SimpleUploadedFile("bad.txt", b"plain text is not an image", content_type="text/plain")
        post_data = dict(self.valid_q_data)
        post_data['photo'] = fake_file

        resp = self.client_a.post(self.analysis_url, data=post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "The uploaded file could not be decoded as a valid image.")

    def test_oversized_photo_rejected(self):
        big_file = SimpleUploadedFile("big.jpg", b"0" * (11 * 1024 * 1024), content_type="image/jpeg")
        post_data = dict(self.valid_q_data)
        post_data['photo'] = big_file

        resp = self.client_a.post(self.analysis_url, data=post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Photo exceeds the 10MB size limit.")

    @patch('google.genai.Client')
    def test_ai_failure_falls_back_gracefully_to_rule_engine(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.models.generate_content.side_effect = Exception("Gemini timeout / 503")

        with patch.object(AIService, 'get_api_key', return_value='fake-api-key'):
            test_photo = create_test_image(format='JPEG')
            post_data = dict(self.valid_q_data)
            post_data['photo'] = test_photo

            resp = self.client_a.post(self.analysis_url, data=post_data)
            # Must succeed with 200 via fallback to rule engine
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Warm Autumn")

    def test_save_palette_without_consent_does_not_persist_to_profile(self):
        post_data = {
            'season': 'warm_autumn',
            'best_colors': 'Rust, Olive, Terracotta',
            'color_palette_notes': 'Warm autumn notes.',
            # consent is omitted / False
        }
        resp = self.client_a.post(self.save_url, data=post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "consent was not granted")

        profile = self.user_a.profile
        profile.refresh_from_db()
        self.assertEqual(profile.color_season, '')
        self.assertFalse(profile.color_analysis_consent)

    def test_save_palette_with_explicit_consent_persists_to_profile(self):
        post_data = {
            'season': 'cool_summer',
            'best_colors': 'Powder Blue, Lavender, Slate',
            'color_palette_notes': 'Powdery cool tones.',
            'consent': 'on',
        }
        resp = self.client_a.post(self.save_url, data=post_data)
        self.assertRedirects(resp, reverse('accounts:profile'))

        profile = self.user_a.profile
        profile.refresh_from_db()
        self.assertEqual(profile.color_season, 'cool_summer')
        self.assertEqual(profile.color_palette_notes, 'Powdery cool tones.')
        self.assertEqual(profile.favorite_colors, 'Powder Blue, Lavender, Slate')
        self.assertTrue(profile.color_analysis_consent)

    def test_results_contain_uncertainty_language(self):
        with patch.object(AIService, 'get_api_key', return_value=''):
            photo = create_test_image(format='JPEG')
            resp = self.client_a.post(self.analysis_url, data={'photo': photo})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "advisory styling guideline")
            self.assertContains(resp, "not an exact or rigid clinical diagnosis")

    def test_find_my_colour_user_isolation(self):
        # User A saves their palette with consent
        self.client_a.post(self.save_url, data={
            'season': 'deep_winter',
            'best_colors': 'Crimson, Black',
            'color_palette_notes': 'Bold high contrast.',
            'consent': 'on',
        })

        # User B's profile must be untouched
        profile_b = self.user_b.profile
        profile_b.refresh_from_db()
        self.assertEqual(profile_b.color_season, '')
        self.assertFalse(profile_b.color_analysis_consent)




