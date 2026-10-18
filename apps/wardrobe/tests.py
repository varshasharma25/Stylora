import io
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from apps.wardrobe.models import Category, ClothingItem
from services.image_service import ImageProcessingService


def create_test_image(format='JPEG', size=(600, 600), color=(255, 0, 0)):
    """Helper to generate in-memory valid image files for tests."""
    file_obj = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_obj, format=format)
    file_obj.seek(0)
    ext = 'jpg' if format == 'JPEG' else format.lower()
    return SimpleUploadedFile(f"test_image.{ext}", file_obj.read(), content_type=f"image/{ext}")


class ImageProcessingServiceTests(TestCase):
    def test_valid_image_processing_and_thumbnail_generation(self):
        upload = create_test_image(format='JPEG', size=(800, 600))
        clean_orig, thumb = ImageProcessingService.validate_and_process_upload(upload)
        
        self.assertIsNotNone(clean_orig)
        self.assertIsNotNone(thumb)

        # Inspect thumbnail dimensions (must be <= 400x400)
        thumb_img = Image.open(io.BytesIO(thumb.read()))
        self.assertLessEqual(thumb_img.width, 400)
        self.assertLessEqual(thumb_img.height, 400)

    def test_corrupt_file_raises_validation_error(self):
        fake_file = SimpleUploadedFile("fake.jpg", b"not a real image payload", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            ImageProcessingService.validate_and_process_upload(fake_file)

    def test_oversized_file_raises_validation_error(self):
        # 11 MB dummy file
        huge_bytes = b"x" * (11 * 1024 * 1024)
        oversized = SimpleUploadedFile("big.jpg", huge_bytes, content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            ImageProcessingService.validate_and_process_upload(oversized)


class WardrobeCRUDAndAccessControlTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        self.user_a = User.objects.create_user(username='priya', email='priya@test.com', password='Password123!')
        self.user_b = User.objects.create_user(username='arjun', email='arjun@test.com', password='Password123!')

        self.client_a.login(username='priya', password='Password123!')
        self.client_b.login(username='arjun', password='Password123!')

        self.category_tops = Category.objects.get(slug='tops')
        self.category_shoes = Category.objects.get(slug='footwear')

        # Create sample item for User A
        test_img = create_test_image()
        self.item_a = ClothingItem.objects.create(
            user=self.user_a,
            category=self.category_tops,
            name='Pink Kurta',
            primary_color='Pink',
            secondary_color='White',
            pattern='floral',
            season='all',
            notes='Festive cotton kurta',
            original_image=test_img,
            thumbnail_image=test_img,
        )

    def test_gallery_displays_only_current_user_items(self):
        # User A views gallery -> sees Pink Kurta
        resp_a = self.client_a.get(reverse('wardrobe:gallery'))
        self.assertEqual(resp_a.status_code, 200)
        self.assertContains(resp_a, 'Pink Kurta')

        # User B views gallery -> sees empty state, never sees User A's item
        resp_b = self.client_b.get(reverse('wardrobe:gallery'))
        self.assertEqual(resp_b.status_code, 200)
        self.assertNotContains(resp_b, 'Pink Kurta')
        self.assertContains(resp_b, 'Your wardrobe is waiting')

    def test_clothing_item_creation_flow(self):
        upload = create_test_image(format='PNG', size=(500, 500), color=(0, 255, 0))
        post_data = {
            'name': 'Blue Slim Jeans',
            'category': Category.objects.get(slug='bottoms').id,
            'primary_color': 'Blue',
            'secondary_color': '',
            'pattern': 'solid',
            'season': 'all',
            'notes': 'Everyday stretch denim',
            'original_image': upload,
        }
        resp = self.client_a.post(reverse('wardrobe:item-create'), data=post_data)
        self.assertRedirects(resp, reverse('wardrobe:gallery'))

        # Verify database record
        item = ClothingItem.objects.get(name='Blue Slim Jeans')
        self.assertEqual(item.user, self.user_a)
        self.assertTrue(item.thumbnail_image.name.endswith('.jpg'))

    def test_clothing_item_edit_flow(self):
        edit_data = {
            'name': 'Updated Pink Kurta',
            'category': self.category_tops.id,
            'primary_color': 'Rose Pink',
            'secondary_color': 'Silver',
            'pattern': 'floral',
            'season': 'summer',
            'notes': 'Updated notes',
        }
        resp = self.client_a.post(reverse('wardrobe:item-edit', kwargs={'pk': self.item_a.pk}), data=edit_data)
        self.assertRedirects(resp, reverse('wardrobe:gallery'))

        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.name, 'Updated Pink Kurta')
        self.assertEqual(self.item_a.primary_color, 'Rose Pink')

    def test_clothing_item_soft_delete(self):
        resp = self.client_a.post(reverse('wardrobe:item-delete', kwargs={'pk': self.item_a.pk}))
        self.assertRedirects(resp, reverse('wardrobe:gallery'))

        self.item_a.refresh_from_db()
        self.assertFalse(self.item_a.is_active)

        # Inactive item no longer displayed in gallery
        gallery_resp = self.client_a.get(reverse('wardrobe:gallery'))
        self.assertNotContains(gallery_resp, 'Pink Kurta')

    def test_cross_user_edit_rejected_with_404(self):
        # User B attempts to edit User A's item -> must return 404
        resp = self.client_b.post(reverse('wardrobe:item-edit', kwargs={'pk': self.item_a.pk}), data={
            'name': 'Hacked Kurta',
            'category': self.category_tops.id,
            'primary_color': 'Red',
            'pattern': 'solid',
            'season': 'all',
        })
        self.assertEqual(resp.status_code, 404)
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.name, 'Pink Kurta')

    def test_cross_user_delete_rejected_with_404(self):
        # User B attempts to delete User A's item -> must return 404
        resp = self.client_b.post(reverse('wardrobe:item-delete', kwargs={'pk': self.item_a.pk}))
        self.assertEqual(resp.status_code, 404)
        self.item_a.refresh_from_db()
        self.assertTrue(self.item_a.is_active)

    def test_protected_media_access_control(self):
        media_url = reverse('wardrobe:protected-media', kwargs={'pk': self.item_a.pk, 'version': 'thumb'})

        # 1. Owner (User A) can view media
        resp_a = self.client_a.get(media_url)
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a['Content-Type'], 'image/jpeg')

        # 2. Non-owner (User B) receives 404
        resp_b = self.client_b.get(media_url)
        self.assertEqual(resp_b.status_code, 404)

        # 3. Anonymous user redirected to login
        anon_client = Client()
        resp_anon = anon_client.get(media_url)
        self.assertEqual(resp_anon.status_code, 302)

    def test_wardrobe_filtering(self):
        # Create second item for User A in Shoes category
        test_img = create_test_image()
        ClothingItem.objects.create(
            user=self.user_a,
            category=self.category_shoes,
            name='White Loafers',
            primary_color='White',
            pattern='solid',
            season='summer',
            original_image=test_img,
            thumbnail_image=test_img,
        )

        # Filter by category: tops
        resp_tops = self.client_a.get(reverse('wardrobe:gallery') + '?category=tops')
        self.assertContains(resp_tops, 'Pink Kurta')
        self.assertNotContains(resp_tops, 'White Loafers')

        # Filter by category: footwear
        resp_shoes = self.client_a.get(reverse('wardrobe:gallery') + '?category=footwear')
        self.assertContains(resp_shoes, 'White Loafers')
        self.assertNotContains(resp_shoes, 'Pink Kurta')

        # Filter by season: summer
        resp_summer = self.client_a.get(reverse('wardrobe:gallery') + '?season=summer')
        self.assertContains(resp_summer, 'White Loafers')
        self.assertNotContains(resp_summer, 'Pink Kurta')

        # Search query: "Kurta"
        resp_search = self.client_a.get(reverse('wardrobe:gallery') + '?q=Kurta')
        self.assertContains(resp_search, 'Pink Kurta')
        self.assertNotContains(resp_search, 'White Loafers')
