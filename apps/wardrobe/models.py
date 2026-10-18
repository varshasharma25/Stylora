from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class ClothingItem(models.Model):
    SEASON_CHOICES = [
        ('all', 'All-Season'),
        ('summer', 'Spring / Summer'),
        ('winter', 'Fall / Winter'),
    ]

    PATTERN_CHOICES = [
        ('solid', 'Solid / Plain'),
        ('striped', 'Striped'),
        ('check', 'Plaid / Checkered'),
        ('floral', 'Floral / Printed'),
        ('graphic', 'Graphic / Logo'),
        ('textured', 'Textured / Knit'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='clothing_items'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='items'
    )
    name = models.CharField(max_length=100)
    primary_color = models.CharField(max_length=40)
    secondary_color = models.CharField(max_length=40, blank=True)
    pattern = models.CharField(max_length=20, choices=PATTERN_CHOICES, default='solid')
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, default='all')

    original_image = models.ImageField(upload_to='wardrobe/originals/%Y/%m/')
    thumbnail_image = models.ImageField(upload_to='wardrobe/thumbnails/%Y/%m/', blank=True)

    notes = models.TextField(blank=True, max_length=500)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'category', 'is_active']),
            models.Index(fields=['user', 'is_active', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.primary_color} {self.category.name})"
