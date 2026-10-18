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
                model='gemini-2.5-flash',
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
