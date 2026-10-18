from django.db import models
from django.contrib.auth.models import User
from apps.wardrobe.models import ClothingItem
from apps.stylist.models import ChatSession


class Outfit(models.Model):
    """
    Curated and saved outfit collections belonging to a user.
    Can be created from an AI styling recommendation or user curation.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='outfits'
    )
    chat_session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='saved_outfits'
    )
    name = models.CharField(max_length=120)
    occasion = models.CharField(max_length=100, blank=True)
    styling_explanation = models.TextField()
    missing_elements_advice = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def items_count(self):
        return self.outfit_items.count()

    @property
    def active_items(self):
        """Returns OutfitItems whose clothing_item exists and is_active."""
        return [
            oi for oi in self.outfit_items.select_related('clothing_item', 'clothing_item__category').all()
            if oi.clothing_item and oi.clothing_item.is_active
        ]


class OutfitItem(models.Model):
    """
    Through-table linking an Outfit to specific ClothingItems with slot/role.
    If the clothing item is deleted, clothing_item is set to NULL while the
    outfit and snapshot metadata are preserved.
    """
    SLOT_CHOICES = [
        ('top', 'Top'),
        ('bottom', 'Bottom'),
        ('shoes', 'Footwear'),
        ('outerwear', 'Outerwear / Layer'),
        ('accessory', 'Accessory'),
        ('one_piece', 'Dress / Jumpsuit'),
    ]

    outfit = models.ForeignKey(
        Outfit,
        on_delete=models.CASCADE,
        related_name='outfit_items'
    )
    clothing_item = models.ForeignKey(
        ClothingItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outfit_usages'
    )
    item_name_snapshot = models.CharField(max_length=100, blank=True)
    slot = models.CharField(max_length=30, choices=SLOT_CHOICES, default='top')

    class Meta:
        ordering = ['id']

    def __str__(self):
        name = self.clothing_item.name if self.clothing_item else (self.item_name_snapshot or "[Deleted Item]")
        return f"{self.slot}: {name} for {self.outfit.name}"

    def save(self, *args, **kwargs):
        if self.clothing_item and not self.item_name_snapshot:
            self.item_name_snapshot = self.clothing_item.name
        super().save(*args, **kwargs)
