from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from .models import UserProfile


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@example.com',
            'autocomplete': 'email',
        }),
        help_text='Required. We use your email exclusively for login and account security.'
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autocomplete': 'username',
        })
        if 'password' in self.fields:
            self.fields['password'].widget.attrs.update({
                'class': 'form-control',
            })
        for field in self.fields.values():
            field.help_text = ''  # Keep UI clean, errors will provide specific guidance if needed

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your username',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        })
    )


class PersonalDetailsForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your first name',
            'autocomplete': 'given-name',
        }),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your last name',
            'autocomplete': 'family-name',
        }),
        label="Last Name"
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@example.com',
            'autocomplete': 'email',
        }),
        label="Email Address",
        help_text="Used for account security and sign in."
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        existing = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This email address is already in use by another account.")
        return email


class StylePreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            'bio',
            'preferred_aesthetic',
            'fit_preference',
            'dressing_goal',
            'favorite_colors',
        )
        labels = {
            'bio': 'Personal Style Note',
            'preferred_aesthetic': 'Preferred Aesthetic',
            'fit_preference': 'Fit Silhouette',
            'dressing_goal': 'Primary Dressing Goal',
            'favorite_colors': 'Favorite Colors',
        }
        widgets = {
            'bio': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Minimalist lover who enjoys experimenting with pastel neutrals',
            }),
            'preferred_aesthetic': forms.Select(attrs={
                'class': 'form-control',
            }),
            'fit_preference': forms.Select(attrs={
                'class': 'form-control',
            }),
            'dressing_goal': forms.Select(attrs={
                'class': 'form-control',
            }),
            'favorite_colors': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Navy Blue, Sage Green, Cream, Terracotta',
            }),
        }


class ColorPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            'color_season',
            'color_palette_notes',
            'color_analysis_consent',
        )
        labels = {
            'color_season': 'Color Season Palette',
            'color_palette_notes': 'Color Palette Notes',
            'color_analysis_consent': 'Save and use my color analysis results for styling',
        }
        widgets = {
            'color_season': forms.Select(attrs={
                'class': 'form-control',
            }),
            'color_palette_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes on best tones, neutrals to wear, or shades to avoid...',
            }),
            'color_analysis_consent': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'style': 'width: 1.25rem; height: 1.25rem; accent-color: var(--primary-600); cursor: pointer;',
            }),
        }


class StyloraPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
