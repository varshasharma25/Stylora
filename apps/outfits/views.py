import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction
from django.contrib import messages
from django.urls import reverse

from .models import Outfit, OutfitItem
from apps.wardrobe.models import ClothingItem
from apps.stylist.models import ChatSession

logger = logging.getLogger('stylora.outfits')


class SaveOutfitView(LoginRequiredMixin, View):
    """
    Saves an outfit recommendation into the user's personal lookbook.
    Enforces strict server-side ownership verification of every clothing item ID (Rule 8).
    """

    def post(self, request, *args, **kwargs):
        # Support both JSON payload and standard form-encoded data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'success': False, 'error': 'Invalid JSON request format.'}, status=400)
        else:
            data = request.POST

        outfit_title = data.get('outfit_title', '').strip() or 'Curated Outfit'
        styling_explanation = data.get('styling_explanation', '').strip()
        occasion = data.get('occasion', '').strip()
        missing_elements_advice = data.get('missing_elements_advice', '').strip()
        chat_session_id = data.get('chat_session_id')

        # Parse item IDs
        raw_item_ids = data.get('item_ids', [])
        if isinstance(raw_item_ids, str):
            try:
                # Could be JSON string or comma-separated
                if raw_item_ids.startswith('['):
                    raw_item_ids = json.loads(raw_item_ids)
                else:
                    raw_item_ids = [int(i.strip()) for i in raw_item_ids.split(',') if i.strip()]
            except (ValueError, json.JSONDecodeError):
                return JsonResponse({'success': False, 'error': 'Invalid item IDs format.'}, status=400)

        try:
            item_ids = [int(i) for i in raw_item_ids]
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid item IDs.'}, status=400)

        if not item_ids:
            return JsonResponse({'success': False, 'error': 'An outfit must contain at least one item.'}, status=400)

        # STRICT ID OWNERSHIP VALIDATION FIREWALL (Anti-IDOR)
        verified_items = list(ClothingItem.objects.filter(
            id__in=item_ids,
            user=request.user,
            is_active=True
        ).select_related('category'))

        verified_map = {item.id: item for item in verified_items}

        if not verified_items:
            logger.warning(
                "Security Alert: User %s attempted to save outfit with invalid/foreign item IDs: %s",
                request.user.username, item_ids
            )
            return JsonResponse({
                'success': False,
                'error': 'None of the specified clothing items belong to your active wardrobe.'
            }, status=400)

        # Validate chat session if provided
        chat_session = None
        if chat_session_id:
            chat_session = ChatSession.objects.filter(id=chat_session_id, user=request.user).first()

        # Slot mapping helper based on category slug
        def resolve_slot(category_slug):
            mapping = {
                'tops': 'top',
                'bottoms': 'bottom',
                'footwear': 'shoes',
                'outerwear': 'outerwear',
                'accessories': 'accessory',
                'dresses': 'one_piece',
            }
            return mapping.get(category_slug, 'top')

        # Atomically save outfit and items
        with transaction.atomic():
            outfit = Outfit.objects.create(
                user=request.user,
                chat_session=chat_session,
                name=outfit_title,
                occasion=occasion,
                styling_explanation=styling_explanation,
                missing_elements_advice=missing_elements_advice,
            )

            seen_ids = set()
            for i_id in item_ids:
                if i_id in verified_map and i_id not in seen_ids:
                    seen_ids.add(i_id)
                    db_item = verified_map[i_id]
                    slot = resolve_slot(db_item.category.slug)
                    OutfitItem.objects.create(
                        outfit=outfit,
                        clothing_item=db_item,
                        item_name_snapshot=db_item.name,
                        slot=slot
                    )

        logger.info("User %s saved outfit #%d: '%s'", request.user.username, outfit.id, outfit.name)

        return JsonResponse({
            'success': True,
            'outfit_id': outfit.id,
            'message': 'Outfit saved to your lookbook!'
        })


class DeleteOutfitView(LoginRequiredMixin, View):
    """
    Deletes (unsaves) an outfit from the user's lookbook.
    Strictly isolated to user-owned outfits.
    """

    def post(self, request, pk, *args, **kwargs):
        outfit = get_object_or_404(Outfit, pk=pk, user=request.user)
        outfit_name = outfit.name
        outfit.delete()

        logger.info("User %s deleted outfit #%d: '%s'", request.user.username, pk, outfit_name)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message': f"'{outfit_name}' removed from your saved looks."
            })

        messages.success(request, f"'{outfit_name}' removed from your saved looks.")
        return redirect('outfits:gallery')


class SavedOutfitsListView(LoginRequiredMixin, ListView):
    """
    Renders the user's saved lookbook gallery.
    Gracefully handles deleted or inactive wardrobe items.
    """
    model = Outfit
    template_name = 'outfits/gallery.html'
    context_object_name = 'outfits'

    def get_queryset(self):
        return Outfit.objects.filter(
            user=self.request.user
        ).prefetch_related(
            'outfit_items',
            'outfit_items__clothing_item',
            'outfit_items__clothing_item__category'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_saved_count'] = self.get_queryset().count()
        return context
