from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import FileResponse, Http404
from django.db.models import Q

from .models import ClothingItem, Category
from .forms import ClothingItemForm


class WardrobeGalleryView(LoginRequiredMixin, ListView):
    """Filterable responsive clothing gallery scoped to the current user."""
    model = ClothingItem
    template_name = 'wardrobe/item_list.html'
    context_object_name = 'items'

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
            return FileResponse(target_file.open('rb'), content_type='image/jpeg')
        except FileNotFoundError:
            raise Http404("Image file missing on disk.")
