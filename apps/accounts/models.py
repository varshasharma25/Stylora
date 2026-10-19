from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    """
    Stores styling preferences and optional colour analysis profile for a user.
    Separates user credentials/auth (on User) from domain styling preferences
    without duplicating personal identity data.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )

    # Personal Details extension
    bio = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Short styling bio or personal fashion note (optional)."
    )

    # Style Preferences
    STYLE_AESTHETIC_CHOICES = [
        ('', 'Select your preferred aesthetic'),
        ('casual', 'Casual & Everyday'),
        ('minimalist', 'Minimalist & Clean'),
        ('formal', 'Classic Formal / Business'),
        ('chic', 'Chic & Elegant'),
        ('streetwear', 'Streetwear & Urban'),
        ('ethnic', 'Ethnic & Traditional'),
        ('bohemian', 'Bohemian & Artsy'),
    ]
    preferred_aesthetic = models.CharField(
        max_length=50,
        blank=True,
        choices=STYLE_AESTHETIC_CHOICES,
        default='',
        help_text="Primary aesthetic you feel most comfortable in."
    )

    FIT_PREFERENCE_CHOICES = [
        ('', 'Select your preferred fit'),
        ('slim', 'Slim Fit'),
        ('regular', 'Regular / Standard Fit'),
        ('relaxed', 'Relaxed Fit'),
        ('oversized', 'Oversized Fit'),
    ]
    fit_preference = models.CharField(
        max_length=30,
        blank=True,
        choices=FIT_PREFERENCE_CHOICES,
        default='',
        help_text="Preferred silhouette for tops and bottoms."
    )

    DRESSING_GOAL_CHOICES = [
        ('', 'Select your primary dressing goal'),
        ('everyday_comfort', 'Everyday Comfort & Ease'),
        ('work_professional', 'Workplace & Professional Impact'),
        ('capsule_wardrobe', 'Versatile Capsule Wardrobe'),
        ('bold_creative', 'Bold & Creative Experimentation'),
        ('event_ready', 'Event & Occasion Ready'),
    ]
    dressing_goal = models.CharField(
        max_length=50,
        blank=True,
        choices=DRESSING_GOAL_CHOICES,
        default='',
        help_text="Primary wardrobe or dressing goal."
    )

    # Favourite Colours
    favorite_colors = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Comma-separated favorite shades (e.g. Navy, Olive, Cream, Pastel Pink)."
    )

    # Colour Analysis Fields (Compatible with future Find My Colour consent-based saving)
    COLOR_SEASON_CHOICES = [
        ('', 'Not Analyzed / None'),
        ('warm_spring', 'Warm Spring'),
        ('light_spring', 'Light Spring'),
        ('clear_spring', 'Clear Spring'),
        ('cool_summer', 'Cool Summer'),
        ('light_summer', 'Light Summer'),
        ('soft_summer', 'Soft Summer'),
        ('warm_autumn', 'Warm Autumn'),
        ('deep_autumn', 'Deep Autumn'),
        ('soft_autumn', 'Soft Autumn'),
        ('cool_winter', 'Cool Winter'),
        ('deep_winter', 'Deep Winter'),
        ('clear_winter', 'Clear Winter'),
    ]
    color_season = models.CharField(
        max_length=50,
        blank=True,
        choices=COLOR_SEASON_CHOICES,
        default='',
        help_text="Seasonal color palette identified for your undertone and contrast."
    )
    color_palette_notes = models.TextField(
        blank=True,
        default='',
        help_text="Flattering color shades, neutrals, and accents notes."
    )
    color_analysis_consent = models.BooleanField(
        default=False,
        help_text="Explicit user consent to store color analysis results and palette recommendations."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username}'s Profile"
