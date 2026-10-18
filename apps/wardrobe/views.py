from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Q

from .models import ClothingItem, Category
from .forms import ClothingItemForm


class WardrobeGalleryView(LoginRequiredMixin, ListView):
    """Filterable responsive clothing gallery scoped to the current user."""
    model = ClothingItem
    template_name = 'wardrobe/item_list.html'
    context_object_name = 'items'
    paginate_by = 24

    def get_queryset(self):
        qs = ClothingItem.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('category').order_by('-created_at')

        # Filter: Category (slug)
        category_slug = self.request.GET.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # Filter: Season
        season = self.request.GET.get('season')
        if season:
            qs = qs.filter(season=season)

        # Filter: Color
        color = self.request.GET.get('color')
        if color:
            qs = qs.filter(
                Q(primary_color__icontains=color) | Q(secondary_color__icontains=color)
            )

        # Search Query
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(notes__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all().order_by('display_order', 'name')
        context['total_user_items'] = ClothingItem.objects.filter(
            user=self.request.user,
            is_active=True
        ).count()
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_season'] = self.request.GET.get('season', '')
        context['selected_color'] = self.request.GET.get('color', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class ClothingItemCreateView(LoginRequiredMixin, CreateView):
    """Upload photo and catalog clothing metadata."""
    model = ClothingItem
    form_class = ClothingItemForm
    template_name = 'wardrobe/item_form.html'
    success_url = reverse_lazy('wardrobe:gallery')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Added '{form.instance.name}' to your digital wardrobe!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Add Clothing Item"
        context['is_create'] = True
        return context


class ClothingItemUpdateView(LoginRequiredMixin, UpdateView):
    """Edit clothing metadata and optionally update photo."""
    model = ClothingItem
    form_class = ClothingItemForm
    template_name = 'wardrobe/item_form.html'
    success_url = reverse_lazy('wardrobe:gallery')

    def get_queryset(self):
        # Strict user scoping & anti-IDOR
        return ClothingItem.objects.filter(user=self.request.user, is_active=True)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Updated '{form.instance.name}'.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit {self.object.name}"
        context['is_create'] = False
        return context


class ClothingItemDeleteView(LoginRequiredMixin, View):
    """Safely remove clothing item via soft delete."""

    def post(self, request, pk, *args, **kwargs):
        # Scoped strictly to request.user
        item = get_object_or_404(ClothingItem, pk=pk, user=request.user, is_active=True)
        item.is_active = False
        item.save()
        messages.info(request, f"'{item.name}' was removed from your wardrobe.")
        return redirect('wardrobe:gallery')


class ProtectedMediaView(LoginRequiredMixin, View):
    """
    Authenticated, user-scoped image delivery view.
    Ensures clothing images are never accessible via unprotected public URLs.
    """

    def get(self, request, pk, version='thumb', *args, **kwargs):
        # Strict ownership verification
        item = get_object_or_404(ClothingItem, pk=pk, user=request.user)

        target_file = item.thumbnail_image if version == 'thumb' and item.thumbnail_image else item.original_image
        if not target_file:
            raise Http404("Image not found.")

        try:
            response = FileResponse(target_file.open('rb'), content_type='image/jpeg')
            response['Cache-Control'] = 'private, max-age=86400'
            return response
        except FileNotFoundError:
            raise Http404("Image file missing on disk.")


class ClothingMetadataSuggestView(LoginRequiredMixin, View):
    """
    AJAX endpoint for vision-based clothing metadata auto-detection.
    Validates uploaded photo through ImageProcessingService first, then
    queries Gemini Flash via AIService to suggest category, colors, and pattern.
    """

    def post(self, request, *args, **kwargs):
        from services.security_service import RateLimiter
        if RateLimiter.is_rate_limited(identifier=str(request.user.id), action='suggest_metadata', max_requests=20, window_seconds=60):
            return JsonResponse({
                'success': False,
                'error': 'Too many upload analysis requests. Please wait a minute before analyzing more photos.'
            }, status=429)

        uploaded_image = request.FILES.get('image')
        if not uploaded_image:
            return JsonResponse({
                'success': False,
                'error': 'No image file was provided.'
            }, status=400)

        try:
            from services.image_service import ImageProcessingService
            from services.ai_service import AIService, AIServiceError
            from django.core.exceptions import ValidationError

            # 1. Validate image format, binary magic bytes, and size <= 10MB
            clean_original, thumb = ImageProcessingService.validate_and_process_upload(uploaded_image)

            # 2. Query Gemini Flash Vision using optimized thumbnail bytes
            thumb_bytes = thumb.read()
            suggestion = AIService.suggest_clothing_metadata(thumb_bytes, mime_type='image/jpeg')

            return JsonResponse({
                'success': True,
                'category_slug': suggestion.category_slug,
                'primary_color': suggestion.primary_color,
                'secondary_color': suggestion.secondary_color,
                'pattern': suggestion.pattern,
                'notes': suggestion.confidence_notes,
            })

        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e.message if hasattr(e, 'message') else e)
            }, status=400)
        except AIServiceError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=200)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'AI auto-detection is temporarily unavailable. Please enter details manually.'
            }, status=200)

