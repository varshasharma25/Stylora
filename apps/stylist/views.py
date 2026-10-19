import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse

from .models import ChatSession, ChatMessage
from .forms import ColorAnalysisQuestionnaireForm, SaveColorPaletteForm
from apps.wardrobe.models import ClothingItem
from apps.accounts.models import UserProfile
from services.ai_service import AIService, AIServiceError, SEASON_PALETTES

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
        context['is_empty_wardrobe'] = active_items_count == 0
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
        mode = request.POST.get('mode', 'full').strip().lower()

        VALID_MODES = {'full', 'tops', 'bottoms', 'shoes', 'accessories'}
        if mode not in VALID_MODES:
            return JsonResponse({
                'success': False,
                'error': f"Invalid styling mode '{mode}'. Choose from full, tops, bottoms, shoes, or accessories."
            }, status=400)

        MODE_CATEGORY_CONFIG = {
            'tops': {
                'slugs': ['tops'],
                'label': 'Tops',
                'empty_msg': "You don't have any tops or shirts in your wardrobe yet. Please add a top to style this category."
            },
            'bottoms': {
                'slugs': ['bottoms'],
                'label': 'Bottoms',
                'empty_msg': "You don't have any bottoms or trousers in your wardrobe yet. Please add bottoms to style this category."
            },
            'shoes': {
                'slugs': ['footwear'],
                'label': 'Shoes',
                'empty_msg': "You don't have any shoes or footwear in your wardrobe yet. Please add shoes to style this category."
            },
            'accessories': {
                'slugs': ['accessories'],
                'label': 'Accessories',
                'empty_msg': "You don't have any accessories or bags in your wardrobe yet. Please add accessories to style this category."
            },
        }

        # 1. Fetch authenticated user's active clothing inventory
        user_items_qs = ClothingItem.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('category')

        total_active_count = user_items_qs.count()
        if total_active_count == 0:
            return JsonResponse({
                'success': False,
                'error': 'Your wardrobe is empty. Please upload some clothes before requesting styling advice.'
            }, status=200)

        # 2. Optional filters/constraints
        required_items = [r.strip() for r in request.POST.get('required', '').split(',') if r.strip()]
        excluded_items = [e.strip() for e in request.POST.get('excluded', '').split(',') if e.strip()]

        # Handle specific item replacement action
        if action == 'replace_item' and replace_item_id:
            try:
                replace_item = user_items_qs.get(id=int(replace_item_id))
                prompt = (
                    f"Please keep the rest of the current outfit, but replace {replace_item.name} "
                    f"({replace_item.category.name}) with an alternative {replace_item.category.name} from my wardrobe."
                )
                excluded_items.append(replace_item.name)
                candidate_items = user_items_qs
                mode = 'full'
            except (ValueError, ClothingItem.DoesNotExist):
                return JsonResponse({'success': False, 'error': 'Selected item to replace was not found.'}, status=400)
        elif mode == 'full':
            if total_active_count < 3:
                return JsonResponse({
                    'success': False,
                    'error': f'You only have {total_active_count} item(s) logged. Please add at least a top, bottom, and shoes for complete outfits.'
                }, status=200)
            candidate_items = user_items_qs
        else:
            cat_cfg = MODE_CATEGORY_CONFIG[mode]
            candidate_items = user_items_qs.filter(category__slug__in=cat_cfg['slugs'])
            category_item_count = candidate_items.count()
            if category_item_count == 0:
                return JsonResponse({
                    'success': False,
                    'error': cat_cfg['empty_msg']
                }, status=200)

        # 3. Get active chat session and extract recent conversation and current outfit context
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

        if not prompt:
            return JsonResponse({'success': False, 'error': 'Please enter a styling request.'}, status=400)

        # 4. Serialize inventory compactly for AI grounding
        serialized_inventory = [
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
            for item in candidate_items
        ]

        # 5. Invoke AI Service with context
        try:
            raw_outfit = AIService.generate_wardrobe_outfit(
                user_prompt=prompt,
                inventory=serialized_inventory,
                mode=mode,
                required_items=required_items,
                excluded_items=excluded_items,
                chat_history=chat_history,
                current_outfit=current_outfit,
            )
        except AIServiceError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=200)

        # 6. CRITICAL SERVER-SIDE VALIDATION FIREWALL (Rule 8)
        # Verify that EVERY returned item_id actually belongs to request.user and matches category filter
        returned_ids = [item_ref.item_id for item_ref in raw_outfit.items]
        
        verified_items_qs = ClothingItem.objects.filter(
            id__in=returned_ids,
            user=request.user,
            is_active=True
        ).select_related('category')

        verified_map = {item.id: item for item in verified_items_qs}

        # Filter out hallucinated IDs, foreign user IDs, duplicates, or wrong-category items
        seen_ids = set()
        sanitized_items_data = []
        allowed_slugs = MODE_CATEGORY_CONFIG[mode]['slugs'] if mode in MODE_CATEGORY_CONFIG else None

        for ref in raw_outfit.items:
            # Check ownership and existence
            if ref.item_id in verified_map and ref.item_id not in seen_ids:
                db_item = verified_map[ref.item_id]

                # Strict category enforcement in single-category mode
                if allowed_slugs and db_item.category.slug not in allowed_slugs:
                    logger.warning(
                        "Category Filter Drop: AI returned item '%s' (slug '%s') in '%s' mode for user %s",
                        db_item.name, db_item.category.slug, mode, request.user.username
                    )
                    continue

                seen_ids.add(ref.item_id)
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
            if mode in MODE_CATEGORY_CONFIG:
                error_msg = f"Stylora couldn't find matching items from your {MODE_CATEGORY_CONFIG[mode]['label']} for this request. Try broadening your prompt."
            else:
                error_msg = "Stylora couldn't match suitable items from your wardrobe for this occasion. Try broadening your request."
            return JsonResponse({
                'success': False,
                'error': error_msg
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


class FindMyColourView(LoginRequiredMixin, View):
    """
    Find My Colour analysis workflow.
    Presents an undertone and aesthetic questionnaire with optional daylight photo upload.
    Generates personal seasonal color recommendations via Gemini multimodal AI or deterministic rules.
    """
    def get(self, request, *args, **kwargs):
        form = ColorAnalysisQuestionnaireForm()
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return render(request, 'stylist/find_my_colour.html', {
            'form': form,
            'current_season': profile.color_season,
            'has_consent': profile.color_analysis_consent,
        })

    def post(self, request, *args, **kwargs):
        form = ColorAnalysisQuestionnaireForm(request.POST, request.FILES)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if not form.is_valid():
            return render(request, 'stylist/find_my_colour.html', {
                'form': form,
                'current_season': profile.color_season,
                'has_consent': profile.color_analysis_consent,
            })

        q_data = {
            'vein_color': form.cleaned_data.get('vein_color', ''),
            'sun_reaction': form.cleaned_data.get('sun_reaction', ''),
            'jewelry': form.cleaned_data.get('jewelry', ''),
            'contrast': form.cleaned_data.get('contrast', ''),
            'preferred_palette': form.cleaned_data.get('preferred_palette', ''),
        }

        uploaded_photo = form.cleaned_data.get('photo')
        image_bytes = None
        mime_type = 'image/jpeg'
        used_photo = False

        if uploaded_photo:
            if hasattr(uploaded_photo, 'seek'):
                uploaded_photo.seek(0)
            image_bytes = uploaded_photo.read()
            mime_type = getattr(uploaded_photo, 'content_type', 'image/jpeg')
            used_photo = True

        try:
            # Perform analysis (handles AI timeouts & falls back seamlessly)
            analysis_result = AIService.analyze_personal_color(
                questionnaire_data=q_data,
                image_bytes=image_bytes,
                mime_type=mime_type
            )
        except Exception as e:
            logger.error("Unexpected error during personal color analysis: %s", str(e), exc_info=True)
            analysis_result = (
                AIService.derive_image_based_season(image_bytes, q_data)
                if image_bytes else AIService.derive_rule_based_season(q_data)
            )

        # Prepare editable save form with suggested defaults and explicit False consent
        save_form = SaveColorPaletteForm(initial={
            'season': analysis_result.season,
            'best_colors': ", ".join(analysis_result.best_colors or []),
            'color_palette_notes': analysis_result.explanation or '',
            'consent': False,
        })

        return render(request, 'stylist/find_my_colour_results.html', {
            'result': analysis_result,
            'save_form': save_form,
            'palette_details': SEASON_PALETTES.get(analysis_result.season, {}),
            'used_photo': used_photo,
        })


class SaveColourAnalysisView(LoginRequiredMixin, View):
    """
    Saves the user's customized seasonal color palette to their profile,
    strictly requiring explicit unselected-by-default user consent.
    """
    def post(self, request, *args, **kwargs):
        form = SaveColorPaletteForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid color palette parameters.")
            return redirect('stylist:color-analysis')

        consent = form.cleaned_data.get('consent', False)
        season_key = form.cleaned_data['season']
        best_colors = form.cleaned_data.get('best_colors', '')
        notes = form.cleaned_data.get('color_palette_notes', '')

        if not consent:
            messages.warning(
                request,
                "Your color analysis results were not saved to your profile because consent was not granted. "
                "Check the consent box if you want to store your palette for styling."
            )
            palette_details = SEASON_PALETTES.get(season_key, {})
            return render(request, 'stylist/find_my_colour_results.html', {
                'result': {
                    'season': season_key,
                    'season_name': palette_details.get('name', season_key),
                    'undertone': palette_details.get('undertone', ''),
                    'contrast_level': palette_details.get('contrast', ''),
                    'best_colors': [c.strip() for c in best_colors.split(',') if c.strip()],
                    'colors_to_avoid': palette_details.get('colors_to_avoid', []),
                    'hex_palette': palette_details.get('hex_palette', []),
                    'explanation': notes,
                },
                'save_form': form,
                'palette_details': palette_details,
                'used_photo': False,
            })

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.color_season = season_key
        profile.color_palette_notes = notes
        if best_colors:
            profile.favorite_colors = best_colors
        profile.color_analysis_consent = True
        profile.save()

        messages.success(
            request,
            f"Your {SEASON_PALETTES.get(season_key, {}).get('name', 'personal')} color palette has been saved to your profile with your consent!"
        )
        return redirect('accounts:profile')

