import io
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

# Maximum allowed upload size: 10 MB
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
THUMBNAIL_MAX_DIMENSION = 400

# Security limit: Prevent Decompression Bomb DOS attacks (max 25 Megapixels, approx 5000x5000)
Image.MAX_IMAGE_PIXELS = 25_000_000


class ImageProcessingService:
    """
    Pure Python service for validating, sanitizing, and processing
    user-uploaded clothing images using Pillow.
    """

    @staticmethod
    def validate_and_process_upload(uploaded_file) -> tuple[ContentFile, ContentFile]:
        """
        Validates file size and format, sanitizes EXIF data from the original,
        and generates an optimized 400x400 thumbnail.
        
        Returns:
            (sanitized_original_file, thumbnail_file)
        """
        # 1. Size Validation
        if uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
            raise ValidationError("File size exceeds 10MB limit. Please upload a smaller image.")

        # Read into memory for Pillow inspection
        try:
            image_data = uploaded_file.read()
            uploaded_file.seek(0)
            img = Image.open(io.BytesIO(image_data))
            img.verify()  # Verify binary integrity
            
            # Re-open after verify() (Pillow requirement)
            img = Image.open(io.BytesIO(image_data))
        except Image.DecompressionBombError as e:
            raise ValidationError("The uploaded image resolution is excessively large (decompression risk). Please resize and retry.") from e
        except (UnidentifiedImageError, ValueError, OSError) as e:
            raise ValidationError("The uploaded file is not a valid or readable image.") from e

        # 2. Format Whitelist
        if img.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                f"Unsupported image format: {img.format}. Please upload a JPEG, PNG, or WebP photo."
            )

        # 3. Transpose based on EXIF orientation, then strip all EXIF metadata
        img = ImageOps.exif_transpose(img)

        # Ensure color mode is RGB for consistent rendering (handles RGBA PNGs and CMYK JPEGs)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Keep alpha or convert cleanly with white background for thumbnail
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if 'A' in img.getbands() else None)
            clean_original = rgb_img
        else:
            clean_original = img.convert('RGB')

        # 4. Save Sanitized Original (EXIF stripped)
        original_io = io.BytesIO()
        clean_original.save(original_io, format='JPEG', quality=92, optimize=True)
        sanitized_original_file = ContentFile(original_io.getvalue())

        # 5. Generate Thumbnail (400x400 max bounding box)
        thumb_img = clean_original.copy()
        thumb_img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.Resampling.LANCZOS)
        
        thumb_io = io.BytesIO()
        thumb_img.save(thumb_io, format='JPEG', quality=85, optimize=True)
        thumbnail_file = ContentFile(thumb_io.getvalue())

        return sanitized_original_file, thumbnail_file
