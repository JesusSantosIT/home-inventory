from django.db import models
from django.contrib.auth import get_user_model
from treebeard.mp_tree import MP_Node
import barcode
import qrcode
from io import BytesIO
import base64

User = get_user_model()


class LocationImage(models.Model):
    """Images for locations"""
    location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='location_images/')
    thumbnail = models.ImageField(upload_to='location_thumbnails/', blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.location.name}"
    
    def save(self, *args, **kwargs):
        """Generate thumbnail on save"""
        super().save(*args, **kwargs)
        if self.image and not self.thumbnail:
            from apps.items.utils import save_thumbnail
            save_thumbnail(self, 'image', 'thumbnail', size=(300, 300))
            # objects.create() passes force_insert=True through kwargs;
            # the second save must UPDATE the row just inserted, not
            # re-INSERT with the same pk (duplicate key error).
            kwargs.pop('force_insert', None)
            super().save(*args, **kwargs)


class Location(MP_Node):
    """
    Hierarchical location structure using Materialized Path Tree.
    Structure: House Name > Room > Room Location > Box > Item
    - House Name: Top-level location (e.g., "Main House", "Garage")
    - Room: Second level (e.g., "Living Room", "Kitchen", "Bedroom")
    - Room Location: Third level - generates barcode (e.g., "North Wall", "East Cabinet")
    - Box: Fourth level - generates barcode (e.g., "Storage Box A", "Tools Box")
    - Item: Fifth level (in Item model) - generates barcode
    """
    
    LOCATION_TYPES = [
        ('house', 'House Name'),
        ('room', 'Room'),
        ('room_location', 'Room Location'),
        ('box', 'Box'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPES,
        default='house'
    )
    barcode = models.CharField(max_length=100, blank=True, null=True, unique=True)
    qr_code = models.CharField(max_length=200, blank=True, null=True, unique=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_locations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['location_type']),
            models.Index(fields=['barcode']),
            models.Index(fields=['qr_code']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate barcode and QR code if not set"""
        if not self.barcode:
            self.barcode = self.generate_barcode()
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        super().save(*args, **kwargs)
    
    def generate_barcode(self):
        """Generate Code 128 barcode for this location.

        Uses pk-based codes once saved (deterministic, unique); UUID-based
        codes before the first save (hash() was non-deterministic across
        processes and collided for same-named locations).
        """
        if self.pk:
            return f"LOC-{self.pk:06d}"
        import uuid
        return f"LOC-{uuid.uuid4().hex[:10].upper()}"

    def generate_qr_code(self):
        """Generate QR code data for this location (same scheme as barcode)."""
        return self.generate_barcode()
    
    def get_barcode_svg(self):
        """Generate SVG barcode for display"""
        if not self.barcode:
            return None
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(self.barcode)
        return barcode_instance.render()
    
    def generate_barcode_image(self):
        """Generate barcode as PNG image"""
        if not self.barcode:
            return None
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(self.barcode, writer='ImageWriter')
        from PIL import Image
        barcode_image = barcode_instance.render()
        return barcode_image
    
    def generate_qr_code_image(self):
        """Generate QR code as PNG image"""
        if not self.qr_code:
            return None
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.qr_code)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
    
    def get_full_path(self):
        """Get the full hierarchical path of this location"""
        path = []
        node = self
        while node:
            path.append(node.name)
            node = node.get_parent()
        return ' → '.join(reversed(path))
    
    def get_item_count(self):
        """Get the total number of items in this location and all sub-locations"""
        from apps.items.models import Item
        return Item.objects.filter(location__in=self.get_descendants(include_self=True)).count()
    
    @property
    def indented_name(self):
        """Name prefixed with indentation reflecting tree depth (for dropdowns)."""
        depth = min(self.get_depth(), 8)
        return '\xa0' * 4 * (depth - 1) + self.name

    def get_ancestors_path(self):
        """Get ancestors as a list for breadcrumb navigation"""
        return list(self.get_ancestors())
    
    def has_barcode(self):
        """Check if this location type should have a barcode"""
        return self.location_type in ['room_location', 'box']