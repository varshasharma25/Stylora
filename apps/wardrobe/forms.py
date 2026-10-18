from django import forms
from .models import ClothingItem, Category
from services.image_service import ImageProcessingService


class ClothingItemForm(forms.ModelForm):
    class Meta:
        model = ClothingItem
        fields = [
            'name',
            'category',
            'primary_color',
            'secondary_color',
            'pattern',
            'season',
            'notes',
            'original_image',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Vintage Denim Jacket',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
            }),
            'primary_color': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Navy Blue',
            }),
            'secondary_color': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional, e.g. White',
            }),
            'pattern': forms.Select(attrs={
                'class': 'form-control',
            }),
            'season': forms.Select(attrs={
                'class': 'form-control',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional styling or fit notes (e.g. slightly oversized, warm lining)',
            }),
            'original_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/webp',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Ensure categories are ordered nicely
        self.fields['category'].queryset = Category.objects.all().order_by('display_order', 'name')
        if not self.instance.pk:
            self.fields['original_image'].required = True
        else:
            self.fields['original_image'].required = False

    def clean_original_image(self):
        uploaded_image = self.cleaned_data.get('original_image')
        # If editing and no new image was uploaded, retain current
        if not uploaded_image and self.instance.pk:
            return self.instance.original_image
        
        if uploaded_image and hasattr(uploaded_image, 'size'):
            # Validate format and size via ImageProcessingService
            ImageProcessingService.validate_and_process_upload(uploaded_image)
        return uploaded_image

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.user = self.user

        raw_image = self.cleaned_data.get('original_image')
        # Process and generate thumbnail if a fresh file was uploaded
        if raw_image and hasattr(raw_image, 'size') and hasattr(raw_image, 'read'):
            clean_original, thumb = ImageProcessingService.validate_and_process_upload(raw_image)
            base_filename = raw_image.name.rsplit('.', 1)[0]
            instance.original_image.save(f"{base_filename}_clean.jpg", clean_original, save=False)
            instance.thumbnail_image.save(f"{base_filename}_thumb.jpg", thumb, save=False)

        if commit:
            instance.save()
        return instance
