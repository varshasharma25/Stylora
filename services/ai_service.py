import io
import hashlib
import logging
from typing import Optional
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger('stylora.ai')


class ClothingMetadataSuggestion(BaseModel):
    """Structured Pydantic schema for clothing image analysis."""
    category_slug: str = Field(
        description="Best matching category slug: 'tops', 'bottoms', 'footwear', 'outerwear', 'accessories', or 'dresses'"
    )
    primary_color: str = Field(
        description="The dominant primary color of the clothing piece, e.g., 'Navy Blue', 'Pink', 'White', 'Black'"
    )
    secondary_color: str = Field(
        default="",
        description="Secondary accent color if clearly visible, otherwise an empty string"
    )
    pattern: str = Field(
        description="Pattern classification: 'solid', 'striped', 'check', 'floral', 'graphic', 'textured', or 'other'"
    )
    confidence_notes: str = Field(
        default="",
        description="Short observation of the garment silhouette or fabric (e.g., 'Embroidered cotton kurta', 'Distressed denim')"
    )


class RecommendedItemRef(BaseModel):
    item_id: int = Field(description="Database integer ID of the clothing item chosen from provided inventory")
    slot: str = Field(description="Role in outfit: 'top', 'bottom', 'shoes', 'outerwear', 'accessory', or 'dress'")
    item_name: str = Field(description="Name of the item as provided in context")


class OutfitResponseSchema(BaseModel):
    outfit_title: str = Field(description="Creative 2-5 word name for the look, e.g., 'Casual Fest Layered'")
    styling_explanation: str = Field(
        description="Clear, human-friendly explanation of why these pieces, colors, and textures coordinate well"
    )
    items: list[RecommendedItemRef] = Field(
        description="List of selected items strictly chosen from the provided inventory"
    )
    missing_elements_advice: Optional[str] = Field(
        default=None,
        description="Helpful styling note if the closet lacked a key piece, e.g., 'A light neutral scarf would complete this look'"
    )


class ColorAnalysisResult(BaseModel):
    season: str = Field(description="One of the 12 seasons: 'warm_spring', 'light_spring', 'clear_spring', 'cool_summer', 'light_summer', 'soft_summer', 'warm_autumn', 'deep_autumn', 'soft_autumn', 'cool_winter', 'deep_winter', 'clear_winter'")
    season_name: str = Field(description="Human readable name, e.g. 'Deep Autumn', 'Cool Summer'")
    undertone: str = Field(description="Overall undertone: 'Warm', 'Cool', or 'Neutral'")
    contrast_level: str = Field(description="Contrast: 'High', 'Medium', or 'Low/Soft'")
    best_colors: list[str] = Field(description="4 to 6 top flattering colors for this palette")
    colors_to_avoid: list[str] = Field(description="2 to 4 colors that may wash out or overpower this palette")
    hex_palette: list[str] = Field(default_factory=list, description="5 to 6 hex colors representing the palette swatches")
    explanation: str = Field(description="Advisory explanation detailing how skin undertone and contrast harmonize with this palette.")


SEASON_PALETTES = {
    'warm_spring': {
        'name': 'Warm Spring',
        'undertone': 'Warm',
        'contrast': 'Medium to Bright',
        'best_colors': ['Peach', 'Warm Coral', 'Golden Yellow', 'Warm Turquoise', 'Light Moss Green', 'Cream'],
        'colors_to_avoid': ['Stark Black', 'Cool Icy Grey', 'Fuchsia'],
        'hex_palette': ['#FDBA74', '#FB7185', '#FACC15', '#2DD4BF', '#86EFAC', '#FEF3C7'],
        'description': 'Characterized by warm, fresh, and golden undertones with sunny clarity.',
    },
    'light_spring': {
        'name': 'Light Spring',
        'undertone': 'Warm & Light',
        'contrast': 'Delicate & Bright',
        'best_colors': ['Soft Peach', 'Mint Green', 'Warm Apricot', 'Buttercup Yellow', 'Camel', 'Ivory'],
        'colors_to_avoid': ['Heavy Charcoal', 'Dark Burgundy', 'Harsh Black'],
        'hex_palette': ['#FED7AA', '#A7F3D0', '#FDE68A', '#FDBA74', '#D79A62', '#FFFBEB'],
        'description': 'Warm and illuminated with delicate golden-peach undertones.',
    },
    'clear_spring': {
        'name': 'Clear Spring',
        'undertone': 'Warm & Clear',
        'contrast': 'High & Striking',
        'best_colors': ['Bright Coral', 'Cobalt Cyan', 'Poppy Red', 'Sunny Gold', 'Bright Emerald', 'Warm White'],
        'colors_to_avoid': ['Muted Earth Tones', 'Dusty Lavender', 'Washed Grey'],
        'hex_palette': ['#F43F5E', '#06B6D4', '#EF4444', '#EAB308', '#10B981', '#FAF5FF'],
        'description': 'Vibrant and luminous with strong contrast and warm vitality.',
    },
    'cool_summer': {
        'name': 'Cool Summer',
        'undertone': 'Cool',
        'contrast': 'Gentle & Muted',
        'best_colors': ['Powder Blue', 'Lavender', 'Soft Rose', 'Slate Blue', 'Cool Grey', 'Seafoam'],
        'colors_to_avoid': ['Mustard Yellow', 'Rust Orange', 'Golden Brown'],
        'hex_palette': ['#93C5FD', '#C4B5FD', '#F472B6', '#64748B', '#94A3B8', '#99F6E4'],
        'description': 'Subtle, powdery, and harmonious with cool blue or pink undertones.',
    },
    'light_summer': {
        'name': 'Light Summer',
        'undertone': 'Cool & Light',
        'contrast': 'Soft & Low',
        'best_colors': ['Sky Blue', 'Pastel Pink', 'Soft Lilac', 'Pale Sage', 'Heather Grey', 'Chalk White'],
        'colors_to_avoid': ['Stark Neon', 'Deep Terracotta', 'Heavy Black'],
        'hex_palette': ['#BAE6FD', '#FBCFE8', '#DDD6FE', '#BBF7D0', '#CBD5E1', '#F8FAFC'],
        'description': 'Ethereal, delicate coolness with softly blended contrast.',
    },
    'soft_summer': {
        'name': 'Soft Summer',
        'undertone': 'Cool & Muted',
        'contrast': 'Medium & Smoky',
        'best_colors': ['Dusty Rose', 'Slate Blue', 'Muted Sage', 'Taupe Grey', 'Plum Grey', 'Soft Navy'],
        'colors_to_avoid': ['Electric Brights', 'Primary Orange', 'Neon Lime'],
        'hex_palette': ['#FDA4AF', '#60A5FA', '#86EFAC', '#A8A29E', '#7E22CE', '#334155'],
        'description': 'Muted elegance with gentle cool grey or rose undertones.',
    },
    'warm_autumn': {
        'name': 'Warm Autumn',
        'undertone': 'Warm',
        'contrast': 'Medium to Rich',
        'best_colors': ['Terracotta', 'Rust Orange', 'Mustard Yellow', 'Forest Green', 'Warm Camel', 'Dark Olive'],
        'colors_to_avoid': ['Icy Pink', 'Cool Fuchsia', 'Stark Chalk White'],
        'hex_palette': ['#C2410C', '#EA580C', '#CA8A04', '#15803D', '#B45309', '#3F6212'],
        'description': 'Rich, earthy, and sun-warmed with golden or bronze undertones.',
    },
    'deep_autumn': {
        'name': 'Deep Autumn',
        'undertone': 'Warm & Deep',
        'contrast': 'High & Saturated',
        'best_colors': ['Burnt Sienna', 'Deep Forest Olive', 'Burgundy Wine', 'Warm Chocolate', 'Deep Teal', 'Spiced Ochre'],
        'colors_to_avoid': ['Pale Pastel Pink', 'Icy Lavender', 'Pale Muted Grey'],
        'hex_palette': ['#9A3412', '#365314', '#881337', '#451A03', '#115E59', '#D97706'],
        'description': 'Intense and opulent warmth with grounding richness and depth.',
    },
    'soft_autumn': {
        'name': 'Soft Autumn',
        'undertone': 'Warm & Muted',
        'contrast': 'Low to Medium',
        'best_colors': ['Olive Khaki', 'Warm Sand', 'Dusty Peach', 'Muted Cinnamon', 'Sage', 'Creamy Ecru'],
        'colors_to_avoid': ['Crisp Royal Blue', 'Stark Black', 'Vibrant Magenta'],
        'hex_palette': ['#65A30D', '#D97706', '#FDBA74', '#92400E', '#A7F3D0', '#FEF3C7'],
        'description': 'Softened, earthy warmth with gentle golden-khaki harmony.',
    },
    'cool_winter': {
        'name': 'Cool Winter',
        'undertone': 'Cool',
        'contrast': 'High & Dramatic',
        'best_colors': ['Royal Cobalt', 'True Emerald', 'Ruby Red', 'Crisp Pure White', 'Pitch Black', 'Icy Blue'],
        'colors_to_avoid': ['Warm Mustard', 'Rust', 'Earthy Ochre', 'Orange'],
        'hex_palette': ['#1D4ED8', '#047857', '#BE123C', '#FFFFFF', '#0F172A', '#E0F2FE'],
        'description': 'Pure, crisp, and high-contrast coolness with jewel-like clarity.',
    },
    'deep_winter': {
        'name': 'Deep Winter',
        'undertone': 'Cool & Deep',
        'contrast': 'Intense & Sharp',
        'best_colors': ['Jet Black', 'Deep Pine', 'Blackberry Wine', 'Royal Violet', 'True Crimson', 'Crisp White'],
        'colors_to_avoid': ['Warm Camel', 'Mustard Yellow', 'Peachy Orange'],
        'hex_palette': ['#020617', '#064E3B', '#4C0519', '#581C87', '#991B1B', '#F8FAFC'],
        'description': 'Deep, striking coolness with sharp contrast and dramatic saturation.',
    },
    'clear_winter': {
        'name': 'Clear Winter',
        'undertone': 'Cool & Bright',
        'contrast': 'Ultra High & Brilliant',
        'best_colors': ['Electric Royal Blue', 'Hot Fuchsia', 'Bright Emerald', 'True Violet', 'Icy Silver', 'Pure White'],
        'colors_to_avoid': ['Muted Camel', 'Dusty Olive', 'Warm Muddy Brown'],
        'hex_palette': ['#2563EB', '#DB2777', '#059669', '#7C3AED', '#E2E8F0', '#FFFFFF'],
        'description': 'Dazzling contrast and vivid icy coolness with intense luminosity.',
    },
}


class AIServiceError(Exception):
    """Custom exception raised when an AI generation or validation step fails."""
    pass


class AIService:
    """
    Dedicated AI service layer wrapping the Gemini Flash API.
    Handles multimodal vision analysis, structured JSON validation,
    request caching, and graceful failure fallbacks.
    """

    CACHE_TTL_SECONDS = 3600  # Cache identical image analyses for 1 hour

    @classmethod
    def get_api_key(cls) -> str:
        """Reads API key from settings; never hardcodes credentials."""
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        return api_key.strip() if api_key else ''

    @classmethod
    def suggest_clothing_metadata(cls, image_bytes: bytes, mime_type: str = 'image/jpeg') -> ClothingMetadataSuggestion:
        """
        Analyzes a clothing photo and suggests category, colors, and pattern.
        Utilizes hash-based caching to avoid redundant API consumption.
        """
        if not image_bytes:
            raise AIServiceError("No image data provided for analysis.")

        # 1. Check Hash Cache to avoid redundant API charges
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        cache_key = f"stylora:ai:metadata:{image_hash}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info("Serving metadata suggestion from cache for hash %s", image_hash[:10])
            return ClothingMetadataSuggestion(**cached_result)

        api_key = cls.get_api_key()
        if not api_key:
            logger.warning("AI auto-detection requested but GEMINI_API_KEY is not configured.")
            raise AIServiceError("AI styling service is not configured. Please fill in details manually.")

        # 2. Call Gemini API via official google-genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = (
                "You are an expert fashion stylist. Analyze this uploaded clothing photograph carefully. "
                "Classify its category slug (one of: tops, bottoms, footwear, outerwear, accessories, dresses), "
                "identify its primary visible color and secondary color (if any), and determine its pattern type."
            )

            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=ClothingMetadataSuggestion.model_json_schema(),
                    temperature=0.2,  # Low temperature for deterministic classification
                ),
            )

            if not response.text:
                raise AIServiceError("Empty response received from AI model.")

            # 3. Validate against Pydantic schema
            suggestion = ClothingMetadataSuggestion.model_validate_json(response.text)

            # Sanitize category_slug to supported taxonomy
            valid_categories = {'tops', 'bottoms', 'footwear', 'outerwear', 'accessories', 'dresses'}
            if suggestion.category_slug.lower() not in valid_categories:
                suggestion.category_slug = 'tops'  # Safe fallback default

            valid_patterns = {'solid', 'striped', 'check', 'floral', 'graphic', 'textured', 'other'}
            if suggestion.pattern.lower() not in valid_patterns:
                suggestion.pattern = 'solid'

            # 4. Save to cache
            cache.set(cache_key, suggestion.model_dump(), timeout=cls.CACHE_TTL_SECONDS)
            logger.info("AI metadata suggested successfully: %s (%s)", suggestion.category_slug, suggestion.primary_color)
            return suggestion

        except ValidationError as e:
            logger.warning("AI returned output that failed schema validation: %s", str(e))
            raise AIServiceError("Unable to extract structured clothing details from image.") from e
        except Exception as e:
            # Catch timeouts, rate limits, or network failures cleanly without exposing keys/tracebacks to user
            logger.error("AI service error during image analysis: %s", str(e), exc_info=True)
            raise AIServiceError("AI auto-detection is temporarily unavailable. Please enter details manually.") from e

    @classmethod
    def generate_wardrobe_outfit(
        cls,
        user_prompt: str,
        inventory: list[dict],
        mode: str = 'full',
        required_items: Optional[list[str]] = None,
        excluded_items: Optional[list[str]] = None,
        chat_history: Optional[list[dict]] = None,
        current_outfit: Optional[dict] = None
    ) -> OutfitResponseSchema:
        """
        Coordinates a personalized outfit using exclusively the user's owned inventory.
        Enforces structured output matching OutfitResponseSchema.
        Supports multi-turn conversational refinement, replace-item requests, styling focus modes, and style inquiries.
        """
        if not inventory:
            raise AIServiceError("Your wardrobe is empty. Please upload clothes before generating an outfit.")

        api_key = cls.get_api_key()
        if not api_key:
            logger.warning("AI styling requested but GEMINI_API_KEY is not configured.")
            raise AIServiceError("AI styling service is not configured. Please contact support or set GEMINI_API_KEY.")

        try:
            from google import genai
            from google.genai import types
            import json

            client = genai.Client(api_key=api_key)

            # Build compact JSON representation of owned inventory
            inventory_summary = json.dumps(inventory, indent=2)

            # Format current active outfit if this is a follow-up refinement
            outfit_context = ""
            if current_outfit and current_outfit.get('items'):
                items_desc = "\n".join(
                    f"- [{item.get('slot', 'Item')}] ID {item.get('id')}: {item.get('name')} "
                    f"({item.get('category')}, {item.get('primary_color')})"
                    for item in current_outfit.get('items', [])
                )
                outfit_context = (
                    "CURRENT ACTIVE OUTFIT BEING DISCUSSED:\n"
                    f"Title: {current_outfit.get('outfit_title', 'Current Look')}\n"
                    f"Explanation: {current_outfit.get('styling_explanation', '')}\n"
                    f"Items:\n{items_desc}\n\n"
                )

            # Format recent conversation history (last 4 turns) for context
            history_context = ""
            if chat_history:
                turns = []
                for turn in chat_history[-4:]:
                    role = "User" if turn.get('sender') == 'user' else "Stylist"
                    text = turn.get('text', '')
                    if text:
                        turns.append(f"{role}: {text}")
                if turns:
                    history_context = "RECENT CONVERSATION HISTORY:\n" + "\n".join(turns) + "\n\n"

            # Build prompt with strict grounding constraints
            constraints = []
            if required_items:
                constraints.append(f"Must include these items if possible: {', '.join(required_items)}")
            if excluded_items:
                constraints.append(f"Exclude these items or colors: {', '.join(excluded_items)}")
            
            constraints_text = "\n".join(constraints) if constraints else "No special inclusions/exclusions specified."

            # Mode-specific instructions
            mode_instructions = {
                'tops': (
                    "STYLING FOCUS MODE: 'Tops only'.\n"
                    "- Recommend 1 or 2 top(s), shirt(s), t-shirt(s), or kurta(s) strictly from the provided inventory matching the request.\n"
                    "- Do NOT select items from any other category (no bottoms, footwear, or accessories)."
                ),
                'bottoms': (
                    "STYLING FOCUS MODE: 'Bottoms only'.\n"
                    "- Recommend 1 or 2 bottom(s), pant(s), trouser(s), skirt(s), or jean(s) strictly from the provided inventory matching the request.\n"
                    "- Do NOT select items from any other category (no tops, footwear, or accessories)."
                ),
                'shoes': (
                    "STYLING FOCUS MODE: 'Shoes only'.\n"
                    "- Recommend 1 pair of shoes, sneaker(s), or footwear strictly from the provided inventory matching the request.\n"
                    "- Do NOT select items from any other category (no tops, bottoms, or accessories)."
                ),
                'accessories': (
                    "STYLING FOCUS MODE: 'Accessories only'.\n"
                    "- Recommend 1 or more bag(s), scarf/scarves, belt(s), or accessory item(s) strictly from the provided inventory matching the request.\n"
                    "- Do NOT select items from any other category (no tops, bottoms, or footwear)."
                ),
                'full': (
                    "STYLING FOCUS MODE: 'Full outfit'.\n"
                    "- Construct a stylish, cohesive combination matching the user's request by coordinating compatible tops, bottoms, footwear, and optional layers/accessories available in their inventory."
                ),
            }
            active_mode_instruction = mode_instructions.get(mode, mode_instructions['full'])

            system_instruction = (
                "You are Stylora, an expert personal fashion stylist.\n\n"
                f"{active_mode_instruction}\n\n"
                "CRITICAL GROUNDING RULE: You may ONLY recommend clothing items from the user's provided inventory. "
                "NEVER invent items, reference external stores, or hallucinate item IDs. "
                "Every single item in your recommendation MUST have an 'item_id' that exists in the provided inventory list.\n\n"
                "CONVERSATIONAL REFINEMENT RULES:\n"
                "- If the user asks to modify or refine an outfit (e.g. 'Make this more formal', 'Keep the shoes and change the top', 'Swap the jacket'): "
                "respect their instructions, retain specified items from the current outfit, and select suitable replacements from their inventory.\n"
                "- If the user asks for another option (e.g. 'Give me another option'): propose an alternative combination from their inventory.\n"
                "- If the user asks an aesthetic or color theory question (e.g. 'Explain why these colors work together'): "
                "maintain the items from the current outfit and provide an articulate, educational breakdown in 'styling_explanation'.\n"
                "- Provide a creative title and clear explanation."
            )

            prompt_content = (
                f"{system_instruction}\n\n"
                f"USER'S OWNED INVENTORY (Only choose from these items):\n{inventory_summary}\n\n"
                f"{outfit_context}"
                f"{history_context}"
                f"SPECIAL CONSTRAINTS:\n{constraints_text}\n\n"
                f"USER STYLING REQUEST:\n\"{user_prompt}\"\n\n"
                "Return your recommendation as a JSON object adhering to the schema."
            )

            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=OutfitResponseSchema.model_json_schema(),
                    temperature=0.3,
                ),
            )

            if not response.text:
                raise AIServiceError("Empty response received from stylist model.")

            # Validate against Pydantic schema
            outfit_data = OutfitResponseSchema.model_validate_json(response.text)
            logger.info("Outfit generated: '%s' with %d items", outfit_data.outfit_title, len(outfit_data.items))
            return outfit_data

        except ValidationError as e:
            logger.warning("AI generated outfit failed schema validation: %s", str(e))
            raise AIServiceError("Stylora received an unreadable outfit recommendation. Please try rephrasing.") from e
        except Exception as e:
            logger.error("AI service error during outfit generation: %s", str(e), exc_info=True)
            raise AIServiceError("Stylora is experiencing heavy demand or connectivity issues. Please try again.") from e

    @classmethod
    def derive_rule_based_season(cls, q_data: dict) -> ColorAnalysisResult:
        """
        Deterministic, offline rule engine that maps user questionnaire observations
        (vein color, sun response, jewelry preference, visual contrast) to one of
        the 12 seasonal palettes without requiring external AI calls.
        """
        warm_score = 0
        cool_score = 0

        vein = q_data.get('vein_color', '')
        if vein == 'green_olive':
            warm_score += 2
        elif vein == 'blue_purple':
            cool_score += 2
        elif vein == 'blue_green':
            warm_score += 1
            cool_score += 1

        sun = q_data.get('sun_reaction', '')
        if sun == 'tans_easily':
            warm_score += 2
        elif sun == 'burns_easily':
            cool_score += 2
        elif sun == 'burns_then_tans':
            warm_score += 1
            cool_score += 1

        jewelry = q_data.get('jewelry', '')
        if jewelry == 'gold':
            warm_score += 2
        elif jewelry == 'silver':
            cool_score += 2
        elif jewelry == 'both':
            warm_score += 1
            cool_score += 1

        contrast = q_data.get('contrast', 'medium')
        pref_palette = q_data.get('preferred_palette', 'earthy')

        is_warm = warm_score >= cool_score

        if is_warm:
            if contrast == 'high':
                season_key = 'clear_spring' if pref_palette in ('vibrant', 'jewel') else 'deep_autumn'
            elif contrast == 'soft':
                season_key = 'light_spring' if pref_palette == 'pastels' else 'soft_autumn'
            else:
                season_key = 'warm_spring' if pref_palette in ('pastels', 'vibrant') else 'warm_autumn'
        else:
            if contrast == 'high':
                season_key = 'clear_winter' if pref_palette == 'vibrant' else 'deep_winter'
            elif contrast == 'soft':
                season_key = 'light_summer' if pref_palette == 'pastels' else 'soft_summer'
            else:
                season_key = 'cool_winter' if pref_palette in ('jewel', 'monochrome') else 'cool_summer'

        if season_key not in SEASON_PALETTES:
            season_key = 'warm_autumn' if is_warm else 'cool_summer'

        p = SEASON_PALETTES[season_key]
        undertone_str = "Warm" if is_warm else ("Cool" if cool_score > warm_score else "Neutral-Leaning")
        contrast_title = contrast.capitalize()

        if q_data and any(q_data.values()):
            explanation = (
                f"Based on your undertone tendency ({undertone_str}) and visual contrast ({contrast_title}), "
                f"your natural coloring is best complemented by the {p['name']} palette. "
                f"{p['description']} These colors harmonize to give your complexion a radiant, balanced glow."
            )
        else:
            explanation = (
                f"Based on your photo analysis ({undertone_str} undertone, {contrast_title} contrast), "
                f"your natural coloring is best complemented by the {p['name']} palette. "
                f"{p['description']} These colors harmonize to give your complexion a radiant, balanced glow."
            )

        return ColorAnalysisResult(
            season=season_key,
            season_name=p['name'],
            undertone=p['undertone'],
            contrast_level=p['contrast'],
            best_colors=p['best_colors'],
            colors_to_avoid=p['colors_to_avoid'],
            hex_palette=p['hex_palette'],
            explanation=explanation
        )

    @classmethod
    def analyze_personal_color(
        cls,
        questionnaire_data: Optional[dict] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = 'image/jpeg'
    ) -> ColorAnalysisResult:
        """
        Performs personal seasonal color analysis.
        If image_bytes is provided and GEMINI_API_KEY is configured, leverages Gemini 3.8 Flash
        multimodal vision analysis to suggest one of the 12 seasons based on the uploaded photo.
        If Gemini encounters a timeout/API failure or API key is absent,
        falls back gracefully and deterministically to the color analysis rule engine.
        """
        questionnaire_data = questionnaire_data or {}
        api_key = cls.get_api_key()
        if not image_bytes or not api_key:
            return cls.derive_rule_based_season(questionnaire_data)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            q_summary = ""
            if questionnaire_data and any(questionnaire_data.values()):
                items = [f"- {k}: {v}" for k, v in questionnaire_data.items() if v]
                if items:
                    q_summary = f"USER OBSERVATIONS:\n" + "\n".join(items) + "\n\n"

            prompt = (
                "You are an expert personal color analyst. Analyze this photograph "
                "to determine the user's best personal seasonal color palette.\n\n"
                f"{q_summary}"
                "TASK:\n"
                "1. Inspect the skin undertone, natural hair color, eye depth, and overall contrast in this photo.\n"
                "2. Determine their personal color season (must be exactly one of: warm_spring, light_spring, clear_spring, "
                "cool_summer, light_summer, soft_summer, warm_autumn, deep_autumn, soft_autumn, cool_winter, deep_winter, clear_winter).\n"
                "3. Identify undertone ('Warm', 'Cool', or 'Neutral') and visual contrast ('High', 'Medium', or 'Low/Soft').\n"
                "4. Recommend 4 to 6 best flattering colors and 2 to 4 colors to avoid.\n"
                "5. In 'explanation', provide an advisory, non-dogmatic breakdown explaining why this seasonal palette illuminates their features.\n"
                "Return valid JSON adhering strictly to the schema."
            )

            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=ColorAnalysisResult.model_json_schema(),
                    temperature=0.2,
                ),
            )

            if not response.text:
                return cls.derive_rule_based_season(questionnaire_data)

            result = ColorAnalysisResult.model_validate_json(response.text)
            if result.season not in SEASON_PALETTES:
                result.season = 'cool_summer' if 'cool' in result.undertone.lower() else 'warm_autumn'

            if not result.hex_palette or len(result.hex_palette) < 3:
                result.hex_palette = SEASON_PALETTES[result.season]['hex_palette']

            logger.info("AI Color Analysis completed: %s (%s)", result.season_name, result.undertone)
            return result

        except Exception as e:
            logger.warning("AI color analysis fallback to rule engine due to: %s", str(e))
            return cls.derive_rule_based_season(questionnaire_data)

