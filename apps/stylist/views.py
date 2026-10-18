import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse

from .models import ChatSession, ChatMessage
from apps.wardrobe.models import ClothingItem
from services.ai_service import AIService, AIServiceError

logger = logging.getLogger('stylora.ai')


class StylistChatView(LoginRequiredMixin, TemplateView):
    """
    Main conversational stylist workspace.
    Loads or creates an active styling session and renders previous messages.
    """
    template_name = 'stylist/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get or create active session
        session, _ = ChatSession.objects.get_or_create(
            user=user,
            defaults={'title': 'Current Styling Session'}
        )
        context['session'] = session

        # Check wardrobe readiness
        active_items_count = ClothingItem.objects.filter(user=user, is_active=True).count()
        context['wardrobe_count'] = active_items_count
        context['needs_more_items'] = active_items_count < 3

        # Load session messages (cap to latest 50 to maintain fast page render times)
        messages_qs = session.messages.all().order_by('-created_at')[:50]
        context['messages_history'] = list(reversed(messages_qs))
        return context


class SendMessageView(LoginRequiredMixin, View):
    """
    Processes styling prompts, retrieves user inventory, invokes AIService,
    and executes strict server-side ID ownership and completeness verification.
    """

    def post(self, request, *args, **kwargs):
        from services.security_service import RateLimiter
        if RateLimiter.is_rate_limited(identifier=str(request.user.id), action='stylist_message', max_requests=20, window_seconds=60):
            return JsonResponse({
                'success': False,
                'error': 'You are sending styling requests too quickly. Please wait a minute before requesting another outfit.'
            }, status=429)

        action = request.POST.get('action', '').strip()
        replace_item_id = request.POST.get('replace_item_id')
        prompt = request.POST.get('prompt', '').strip()

        # 1. Fetch authenticated user's active clothing inventory
        user_items = ClothingItem.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('category')

        item_count = user_items.count()
        if item_count == 0:
            return JsonResponse({
                'success': False,
                'error': 'Your wardrobe is empty. Please upload some clothes before requesting styling advice.'
            }, status=200)

        if item_count < 3:
            return JsonResponse({
                'success': False,
                'error': f'You only have {item_count} item(s) logged. Please add at least a top, bottom, and shoes for complete outfits.'
            }, status=200)

        # 2. Get active chat session and extract recent conversation and current outfit context
        session, _ = ChatSession.objects.get_or_create(
            user=request.user,
            defaults={'title': 'Current Styling Session'}
        )

        last_assistant_msg = session.messages.filter(sender='assistant').order_by('-created_at').first()
        current_outfit = last_assistant_msg.raw_response if last_assistant_msg else None

        recent_messages = list(session.messages.all().order_by('-created_at')[:4])
        recent_messages.reverse()
        chat_history = [
            {'sender': msg.sender, 'text': msg.message_text}
            for msg in recent_messages
        ]

        # 3. Optional filters/constraints
        required_items = [r.strip() for r in request.POST.get('required', '').split(',') if r.strip()]
        excluded_items = [e.strip() for e in request.POST.get('excluded', '').split(',') if e.strip()]

        # Handle specific item replacement action
        if action == 'replace_item' and replace_item_id:
            try:
                replace_item = user_items.get(id=int(replace_item_id))
                prompt = (
                    f"Please keep the rest of the current outfit, but replace {replace_item.name} "
                    f"({replace_item.category.name}) with an alternative {replace_item.category.name} from my wardrobe."
                )
                excluded_items.append(replace_item.name)
            except (ValueError, ClothingItem.DoesNotExist):
                return JsonResponse({'success': False, 'error': 'Selected item to replace was not found.'}, status=400)

        if not prompt:
            return JsonResponse({'success': False, 'error': 'Please enter a styling request.'}, status=400)

        # 4. Serialize inventory compactly for AI grounding
        serialized_inventory = [
            {
                'id': item.id,
                'name': item.name,
                'category': item.category.name,
                'primary_color': item.primary_color,
                'secondary_color': item.secondary_color,
                'pattern': item.pattern,
                'season': item.season,
                'notes': item.notes,
            }
            for item in user_items
        ]

        # 5. Invoke AI Service with context
        try:
            raw_outfit = AIService.generate_wardrobe_outfit(
                user_prompt=prompt,
                inventory=serialized_inventory,
                required_items=required_items,
                excluded_items=excluded_items,
                chat_history=chat_history,
                current_outfit=current_outfit,
            )
        except AIServiceError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=200)

        # 5. CRITICAL SERVER-SIDE VALIDATION FIREWALL (Rule 8)
        # Verify that EVERY returned item_id actually belongs to request.user
        returned_ids = [item_ref.item_id for item_ref in raw_outfit.items]
        
        verified_items_qs = ClothingItem.objects.filter(
            id__in=returned_ids,
            user=request.user,
            is_active=True
        ).select_related('category')

        verified_map = {item.id: item for item in verified_items_qs}

        # Filter out hallucinated IDs, foreign user IDs, or duplicates
        seen_ids = set()
        sanitized_items_data = []

        for ref in raw_outfit.items:
            # Check ownership and existence
            if ref.item_id in verified_map and ref.item_id not in seen_ids:
                seen_ids.add(ref.item_id)
                db_item = verified_map[ref.item_id]
                sanitized_items_data.append({
                    'id': db_item.id,
                    'name': db_item.name,
                    'category': db_item.category.name,
                    'slot': ref.slot.capitalize(),
                    'primary_color': db_item.primary_color,
                    'thumbnail_url': reverse('wardrobe:protected-media', kwargs={'pk': db_item.pk, 'version': 'thumb'}),
                })
            elif ref.item_id not in verified_map:
                logger.warning(
                    "Security Drop: AI returned unverified or foreign item ID %s for user %s",
                    ref.item_id, request.user.username
                )

        if not sanitized_items_data:
            return JsonResponse({
                'success': False,
                'error': "Stylora couldn't match suitable items from your wardrobe for this occasion. Try broadening your request."
            }, status=200)

        # 6. Save messages to chat session
        ChatMessage.objects.create(
            session=session,
            sender='user',
            message_text=prompt
        )

        # Save AI assistant message with sanitized response JSON
        outfit_payload = {
            'outfit_title': raw_outfit.outfit_title,
            'styling_explanation': raw_outfit.styling_explanation,
            'missing_elements_advice': raw_outfit.missing_elements_advice,
            'items': sanitized_items_data,
            'session_id': session.id,
        }
        
        ChatMessage.objects.create(
            session=session,
            sender='assistant',
            message_text=raw_outfit.styling_explanation,
            raw_response=outfit_payload
        )

        return JsonResponse({
            'success': True,
            'outfit': outfit_payload,
        })
