from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView, PasswordChangeView as DjangoPasswordChangeView
from django.contrib import messages
from django.http import JsonResponse

from .forms import (
    SignUpForm,
    LoginForm,
    PersonalDetailsForm,
    StylePreferencesForm,
    ColorPreferencesForm,
    StyloraPasswordChangeForm,
)
from .models import UserProfile


class LandingPageView(View):
    """Public landing page; redirects authenticated users to their dashboard."""

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return render(request, 'accounts/landing.html')


class SignUpView(View):
    """User registration view with automatic session login on completion."""

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = SignUpForm()
        return render(request, 'accounts/signup.html', {'form': form})

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Initialize empty UserProfile
            UserProfile.objects.get_or_create(user=user)
            login(request, user)
            messages.success(request, f"Welcome to Stylora, {user.username}! Your digital closet is ready.")
            return redirect('accounts:dashboard')
        return render(request, 'accounts/signup.html', {'form': form})


class LoginView(DjangoLoginView):
    """Standard authentication view with tailored styling and redirect."""
    form_class = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return super().form_valid(form)


class LogoutView(View):
    """Secure POST-only logout view."""

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
            messages.info(request, "You have been logged out safely.")
        return redirect('accounts:landing')


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Protected fashion home dashboard showing wardrobe statistics,
    navigation shortcuts, recently saved looks, and an on-demand Today's Outfit section.
    Crucial: Does NOT call Gemini automatically on page load or refresh.
    """
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.wardrobe.models import ClothingItem
        from apps.outfits.models import Outfit

        user = self.request.user
        user_items_qs = ClothingItem.objects.filter(
            user=user,
            is_active=True
        ).select_related('category')

        wardrobe_count = user_items_qs.count()
        context['wardrobe_count'] = wardrobe_count

        # Category-level breakdown for actual user inventory
        context['tops_count'] = user_items_qs.filter(category__slug='tops').count()
        context['bottoms_count'] = user_items_qs.filter(category__slug='bottoms').count()
        context['shoes_count'] = user_items_qs.filter(category__slug='footwear').count()
        context['accessories_count'] = user_items_qs.filter(category__slug__in=['accessories', 'outerwear']).count()

        # Outfit collection counts and recently saved looks
        context['saved_outfits_count'] = Outfit.objects.filter(user=user).count()
        context['recent_outfits'] = Outfit.objects.filter(
            user=user
        ).prefetch_related('outfit_items__clothing_item__category')[:3]

        # User profile & readiness
        profile, _ = UserProfile.objects.get_or_create(user=user)
        context['profile'] = profile
        context['can_form_outfit'] = (wardrobe_count >= 3)
        return context


class TodayOutfitView(LoginRequiredMixin, View):
    """
    On-demand endpoint to generate a personalized Today's Outfit recommendation.
    Triggered exclusively via explicit POST request from the user.
    Never triggered automatically on page load or refresh.
    Uses exclusively active wardrobe items belonging to request.user.
    """

    def post(self, request, *args, **kwargs):
        from apps.wardrobe.models import ClothingItem
        from services.ai_service import AIService, AIServiceError

        user = request.user
        active_items_qs = ClothingItem.objects.filter(
            user=user,
            is_active=True
        ).select_related('category')

        item_count = active_items_qs.count()

        # Empty and incomplete wardrobe validation
        if item_count == 0:
            return JsonResponse({
                'success': False,
                'empty': True,
                'error': "Your closet is empty. Please add some clothes before generating Today's Outfit.",
            }, status=200)

        if item_count < 3:
            return JsonResponse({
                'success': False,
                'incomplete': True,
                'error': f"You currently have {item_count} item(s) logged. Please add at least 3 items (e.g. top, bottom, shoes) so Stylora can coordinate a complete look.",
            }, status=200)

        # Serialize active inventory
        inventory = [
            {
                'id': item.id,
                'name': item.name,
                'category': item.category.name,
                'category_slug': item.category.slug,
                'primary_color': item.primary_color,
                'secondary_color': item.secondary_color,
                'pattern': item.pattern,
                'season': item.season,
                'notes': item.notes,
            }
            for item in active_items_qs
        ]

        # Incorporate user profile styling preferences if present
        profile = getattr(user, 'profile', None)
        style_hints = []
        if profile:
            if profile.preferred_aesthetic:
                style_hints.append(f"Preferred aesthetic: {profile.get_preferred_aesthetic_display()}")
            if profile.fit_preference:
                style_hints.append(f"Fit silhouette: {profile.get_fit_preference_display()}")
            if profile.favorite_colors:
                style_hints.append(f"Favorite colors: {profile.favorite_colors}")
            if profile.color_analysis_consent and profile.color_season:
                style_hints.append(f"Color analysis season: {profile.get_color_season_display()}")

        custom_pref = f" User profile context: {', '.join(style_hints)}." if style_hints else ""
        prompt = f"Coordinate a fresh, stylish, and cohesive outfit for today using my wardrobe.{custom_pref}"

        try:
            raw_outfit = AIService.generate_wardrobe_outfit(
                user_prompt=prompt,
                inventory=inventory,
                mode='full',
            )
        except AIServiceError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=200)

        # Rule 8 Security Firewall: verify all returned item IDs belong to request.user
        returned_ids = [ref.item_id for ref in raw_outfit.items]
        verified_items = {item.id: item for item in active_items_qs.filter(id__in=returned_ids)}

        sanitized_items = []
        for ref in raw_outfit.items:
            if ref.item_id in verified_items:
                db_item = verified_items[ref.item_id]
                sanitized_items.append({
                    'id': db_item.id,
                    'name': db_item.name,
                    'category': db_item.category.name,
                    'slot': ref.slot,
                    'primary_color': db_item.primary_color,
                })

        if not sanitized_items:
            return JsonResponse({
                'success': False,
                'error': "Stylora could not coordinate a suitable combination from your current clothes. Try adding more variety to your closet.",
            }, status=200)

        return JsonResponse({
            'success': True,
            'outfit': {
                'outfit_title': raw_outfit.outfit_title,
                'styling_explanation': raw_outfit.styling_explanation,
                'missing_elements_advice': raw_outfit.missing_elements_advice,
                'items': sanitized_items,
            }
        })


class ProfileView(LoginRequiredMixin, View):
    """
    User Profile view allowing users to manage their personal details,
    style preferences, favorite colors, and color analysis consent.
    Strictly restricted to the authenticated user (anti-IDOR by architecture).
    """

    def get(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        personal_form = PersonalDetailsForm(instance=request.user, prefix='personal')
        style_form = StylePreferencesForm(instance=profile, prefix='style')
        color_form = ColorPreferencesForm(instance=profile, prefix='color')

        context = {
            'profile': profile,
            'personal_form': personal_form,
            'style_form': style_form,
            'color_form': color_form,
        }
        return render(request, 'accounts/profile.html', context)

    def post(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        action = request.POST.get('action')

        personal_form = PersonalDetailsForm(instance=request.user, prefix='personal')
        style_form = StylePreferencesForm(instance=profile, prefix='style')
        color_form = ColorPreferencesForm(instance=profile, prefix='color')

        if action == 'personal':
            personal_form = PersonalDetailsForm(request.POST, instance=request.user, prefix='personal')
            if personal_form.is_valid():
                personal_form.save()
                messages.success(request, "Personal details updated successfully.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the errors in your personal details.")

        elif action == 'style':
            style_form = StylePreferencesForm(request.POST, instance=profile, prefix='style')
            if style_form.is_valid():
                style_form.save()
                messages.success(request, "Style preferences updated successfully.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the errors in your style preferences.")

        elif action == 'color':
            color_form = ColorPreferencesForm(request.POST, instance=profile, prefix='color')
            if color_form.is_valid():
                color_form.save()
                messages.success(request, "Color analysis preferences updated successfully.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the errors in your color preferences.")

        context = {
            'profile': profile,
            'personal_form': personal_form,
            'style_form': style_form,
            'color_form': color_form,
        }
        return render(request, 'accounts/profile.html', context)


class StyloraPasswordChangeView(LoginRequiredMixin, DjangoPasswordChangeView):
    """Secure password change view styled to match Stylora's theme."""
    form_class = StyloraPasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, "Your password was changed successfully.")
        return super().form_valid(form)
