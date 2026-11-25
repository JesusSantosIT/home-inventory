import logging
import os

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def generate_thumbnail(image_field, size=(200, 200), quality=85):
    """
    Generate a thumbnail for an image field.
    
    Args:
        image_field: The image field instance
        size: Tuple of (width, height) for thumbnail
        quality: JPEG quality (1-100)
    
    Returns:
        BytesIO object containing the thumbnail image
    """
    if not image_field:
        return None
    
    try:
        # Open the image
        image = Image.open(image_field)
        
        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        
        # Calculate aspect ratio preserving resize
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        output = BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        return output
    
    except Exception:
        logger.exception("Error generating thumbnail")
        return None


def save_thumbnail(instance, image_field_name, thumbnail_field_name, size=(200, 200)):
    """
    Generate and save a thumbnail for a model instance.
    
    Args:
        instance: The model instance
        image_field_name: Name of the image field
        thumbnail_field_name: Name of the thumbnail field
        size: Tuple of (width, height) for thumbnail
    """
    image_field = getattr(instance, image_field_name)
    if not image_field:
        return
    
    thumbnail_data = generate_thumbnail(image_field, size)
    if thumbnail_data:
        # Create filename for thumbnail
        original_name = os.path.basename(image_field.name)
        name_without_ext = os.path.splitext(original_name)[0]
        thumbnail_name = f"thumb_{name_without_ext}.jpg"
        
        # Save to thumbnail field
        getattr(instance, thumbnail_field_name).save(
            thumbnail_name,
            ContentFile(thumbnail_data.read()),
            save=False
        )
