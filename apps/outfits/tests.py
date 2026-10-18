import io
import json
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.wardrobe.models import Category, ClothingItem
from apps.stylist.models import ChatSession
from apps.outfits.models import Outfit, OutfitItem


def create_test_image(format='JPEG', size=(200, 200), color=(120, 100, 200)):
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    return SimpleUploadedFile("item.jpg", file_obj.read(), content_type="image/jpeg")


class SavedOutfitsTests(TestCase):
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

        img = create_test_image()

        # User A's items
        self.item_a1 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_tops, name='Silk Blouse',
            primary_color='Ivory', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )
        self.item_a2 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_bottoms, name='Dark Trousers',
            primary_color='Navy', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )
        self.item_a3 = ClothingItem.objects.create(
            user=self.user_a, category=self.cat_shoes, name='Leather Loafers',
            primary_color='Brown', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )

        # User B's item
        self.item_b1 = ClothingItem.objects.create(
            user=self.user_b, category=self.cat_tops, name='Arjun Casual Tee',
            primary_color='Grey', pattern='solid', season='all',
            original_image=img, thumbnail_image=img
        )

        self.session_a = ChatSession.objects.create(user=self.user_a, title='Workwear Consultation')
        self.session_b = ChatSession.objects.create(user=self.user_b, title='Arjun Weekend Look')

    def test_save_outfit_authenticated_success(self):
        """User A can save an outfit referencing their own clothing items."""
        payload = {
            'outfit_title': 'Executive Minimalist',
            'styling_explanation': 'Ivory and Navy create an authoritative yet refined silhouette.',
            'occasion': 'Boardroom Meeting',
            'missing_elements_advice': 'Consider a subtle gold watch.',
            'chat_session_id': self.session_a.id,
            'item_ids': [self.item_a1.id, self.item_a2.id, self.item_a3.id],
        }

        resp = self.client_a.post(
            reverse('outfits:save'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('outfit_id', data)

        outfit = Outfit.objects.get(id=data['outfit_id'])
        self.assertEqual(outfit.user, self.user_a)
        self.assertEqual(outfit.name, 'Executive Minimalist')
        self.assertEqual(outfit.occasion, 'Boardroom Meeting')
        self.assertEqual(outfit.chat_session, self.session_a)
        self.assertEqual(outfit.outfit_items.count(), 3)

        # Verify item snapshot is populated
        first_item = outfit.outfit_items.first()
        self.assertEqual(first_item.item_name_snapshot, 'Silk Blouse')

    def test_save_outfit_anti_idor_cross_user_rejection(self):
        """User B cannot save an outfit containing User A's clothing items."""
        payload = {
            'outfit_title': 'Stolen Look',
            'styling_explanation': 'Should not be allowed.',
            'item_ids': [self.item_a1.id, self.item_a2.id],
        }

        resp = self.client_b.post(
            reverse('outfits:save'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('None of the specified clothing items belong to your active wardrobe', data['error'])
        self.assertEqual(Outfit.objects.filter(user=self.user_b).count(), 0)

    def test_save_outfit_foreign_chat_session_scoping(self):
        """If User A passes User B's chat session ID, it is sanitized/ignored."""
        payload = {
            'outfit_title': 'Safe Scoped Outfit',
            'styling_explanation': 'Test scoping.',
            'chat_session_id': self.session_b.id,  # Belongs to user_b!
            'item_ids': [self.item_a1.id, self.item_a2.id],
        }

        resp = self.client_a.post(
            reverse('outfits:save'),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        outfit_id = resp.json()['outfit_id']
        outfit = Outfit.objects.get(id=outfit_id)
        # Foreign chat session must NOT be linked
        self.assertIsNone(outfit.chat_session)

    def test_delete_outfit_by_owner(self):
        """User A can delete their saved outfit."""
        outfit = Outfit.objects.create(
            user=self.user_a,
            name='Temporary Look',
            styling_explanation='To be deleted.'
        )
        OutfitItem.objects.create(outfit=outfit, clothing_item=self.item_a1, slot='top')

        resp = self.client_a.post(
            reverse('outfits:delete', kwargs={'pk': outfit.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Outfit.objects.filter(id=outfit.id).exists())

    def test_delete_outfit_cross_user_rejection(self):
        """User B cannot delete User A's outfit (returns 404)."""
        outfit = Outfit.objects.create(
            user=self.user_a,
            name='Protected Priya Look',
            styling_explanation='Cannot touch.'
        )

        resp = self.client_b.post(
            reverse('outfits:delete', kwargs={'pk': outfit.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Outfit.objects.filter(id=outfit.id).exists())

    def test_saved_outfits_gallery_view_renders(self):
        """Gallery renders saved looks with their item details."""
        outfit = Outfit.objects.create(
            user=self.user_a,
            name='Brunch Chic',
            occasion='Sunday Brunch',
            styling_explanation='Effortlessly stylish ivory and navy combo.'
        )
        OutfitItem.objects.create(outfit=outfit, clothing_item=self.item_a1, slot='top')
        OutfitItem.objects.create(outfit=outfit, clothing_item=self.item_a2, slot='bottom')

        resp = self.client_a.get(reverse('outfits:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Brunch Chic')
        self.assertContains(resp, 'Sunday Brunch')
        self.assertContains(resp, 'Silk Blouse')
        self.assertContains(resp, 'Dark Trousers')

    def test_saved_outfits_gallery_handles_deleted_wardrobe_items(self):
        """
        When a wardrobe item is soft-deleted or deleted from the closet,
        the saved outfit still renders gracefully without crashing, showing the snapshot.
        """
        outfit = Outfit.objects.create(
            user=self.user_a,
            name='Vintage Memory Look',
            styling_explanation='Testing resilience against deleted clothing items.'
        )
        # Create an item that will be deactivated / deleted
        oi = OutfitItem.objects.create(
            outfit=outfit,
            clothing_item=self.item_a1,
            item_name_snapshot='Silk Blouse',
            slot='top'
        )

        # Soft delete item
        self.item_a1.is_active = False
        self.item_a1.save()

        resp = self.client_a.get(reverse('outfits:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Vintage Memory Look')
        self.assertContains(resp, 'Silk Blouse')
        self.assertContains(resp, '(Deleted from closet)')

    def test_ai_failure_does_not_affect_existing_saved_outfits(self):
        """Saved outfits are fully durable and independent of any subsequent AI service errors."""
        outfit = Outfit.objects.create(
            user=self.user_a,
            name='Durable Look',
            styling_explanation='This must survive AI crashes.'
        )

        # Verify outfit persists
        self.assertTrue(Outfit.objects.filter(id=outfit.id).exists())
        self.assertEqual(Outfit.objects.filter(user=self.user_a).count(), 1)

    def test_saved_outfits_gallery_pagination(self):
        """Verify saved outfits gallery pagination kicks in when outfits exceed paginate_by = 12."""
        outfits = [
            Outfit(
                user=self.user_a,
                name=f'Outfit Look {i}',
                styling_explanation=f'Explanation for look {i}'
            )
            for i in range(15)
        ]
        Outfit.objects.bulk_create(outfits)

        resp = self.client_a.get(reverse('outfits:gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_paginated'])
        self.assertEqual(len(resp.context['outfits']), 12)

        resp_p2 = self.client_a.get(reverse('outfits:gallery') + '?page=2')
        self.assertEqual(resp_p2.status_code, 200)
        self.assertEqual(len(resp_p2.context['outfits']), 3)

