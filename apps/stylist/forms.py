import io
from PIL import Image, UnidentifiedImageError
from django import forms
from services.ai_service import SEASON_PALETTES


class ColorAnalysisQuestionnaireForm(forms.Form):
    """
    Questionnaire capturing undertone and personal aesthetic observations,
    with an optional selfie/wrist upload for multimodal AI color analysis.
    """
    VEIN_CHOICES = [
        ('blue_purple', 'Blue or purple (tends towards Cool undertones)'),
        ('green_olive', 'Green or olive (tends towards Warm undertones)'),
        ('blue_green', 'Blue-green or difficult to distinguish (tends towards Neutral)'),
    ]
    vein_color = forms.ChoiceField(
        choices=VEIN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        label="1. Look at the veins on the inside of your wrist in natural daylight:",
        initial='green_olive',
        required=False,
    )

    SUN_CHOICES = [
        ('burns_easily', 'Burns easily, rarely or slowly tans (Cool tendency)'),
        ('tans_easily', 'Tans quickly and easily, rarely burns (Warm tendency)'),
        ('burns_then_tans', 'Burns mildly first, then tans evenly (Neutral tendency)'),
    ]
    sun_reaction = forms.ChoiceField(
        choices=SUN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        label="2. How does your skin typically respond to prolonged sunlight?",
        initial='tans_easily',
        required=False,
    )

    JEWELRY_CHOICES = [
        ('silver', 'Silver brings out the clearest, most radiant glow'),
        ('gold', 'Yellow gold brings out the richest, most flattering warmth'),
        ('both', 'Both silver and gold look equally balanced'),
    ]
    jewelry = forms.ChoiceField(
        choices=JEWELRY_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        label="3. Which metal tone feels most harmonious against your skin?",
        initial='gold',
        required=False,
    )

    CONTRAST_CHOICES = [
        ('high', 'High Contrast (e.g. sharp difference between hair, eyes, and skin tone)'),
        ('medium', 'Medium Contrast (balanced features with moderate tonal depth)'),
        ('soft', 'Soft / Low Contrast (muted, delicate, tone-on-tone coloring)'),
    ]
    contrast = forms.ChoiceField(
        choices=CONTRAST_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        label="4. How would you describe the contrast between your hair, eyes, and skin?",
        initial='medium',
        required=False,
    )

    PALETTE_CHOICES = [
        ('earthy', 'Earthy & Warm (rust, mustard, olive green, terracotta, warm camel)'),
        ('pastels', 'Soft Pastels (powder blue, lavender, blush pink, soft sage)'),
        ('vibrant', 'Vibrant Brights (poppy red, electric royal, sunny yellow, emerald)'),
        ('jewel', 'Deep Jewels (burgundy wine, ruby, forest pine, royal navy)'),
        ('monochrome', 'High-Contrast Neutrals (stark black, crisp white, charcoal)'),
    ]
    preferred_palette = forms.ChoiceField(
        choices=PALETTE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio'}),
        label="5. Which color family makes you feel most confident when wearing it?",
        initial='earthy',
        required=False,
    )

    photo = forms.FileField(
        required=True,
        label="Daylight Photo (Face or Wrist in natural lighting)",
        help_text="Upload a clear JPEG, PNG, or WebP photo (max 10MB) in natural daylight.",
        error_messages={'required': 'Please upload a photo in natural daylight to analyze your colour palette.'},
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png,image/webp',
            'id': 'color-photo-input',
        })
    )

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return None

        # 1. Size Validation (10 MB limit)
        if photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Photo exceeds the 10MB size limit. Please upload a smaller file.")

        # 2. Format & Integrity Validation via Pillow
        try:
            image_data = photo.read()
            photo.seek(0)
            img = Image.open(io.BytesIO(image_data))
            img.verify()

            if img.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise forms.ValidationError(
                    f"Unsupported image format: {img.format}. Please upload a JPEG, PNG, or WebP image."
                )
        except forms.ValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise forms.ValidationError("The uploaded file could not be decoded as a valid image.") from e

        return photo


class SaveColorPaletteForm(forms.Form):
    """
    Form presented on the results screen allowing users to fine-tune the palette
    and provide explicit unselected consent before persisting to their profile.
    """
    SEASON_CHOICES = [(k, v['name']) for k, v in SEASON_PALETTES.items()]

    season = forms.ChoiceField(
        choices=SEASON_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Selected Season Palette"
    )
    best_colors = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Best Flattering Colors"
    )
    color_palette_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Personal Palette & Styling Notes"
    )
    consent = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'style': 'width: 1.25rem; height: 1.25rem; accent-color: var(--primary-600); cursor: pointer;',
        }),
        label="I consent to saving this color analysis result and palette to my profile to personalize future outfit recommendations."
    )
