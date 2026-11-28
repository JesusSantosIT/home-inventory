from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.conf import settings
from apps.locations.models import Location
import barcode
import qrcode
from io import BytesIO

User = get_user_model()


class LabelTemplate(models.Model):
    """Custom label templates for printing barcodes/QR codes"""
    
    LABEL_SIZE_CHOICES = [
        ('50x25', '50mm x 25mm (Small)'),
        ('50x30', '50mm x 30mm (Medium)'),
        ('60x30', '60mm x 30mm (Large)'),
        ('100x50', '100mm x 50mm (Extra Large)'),
        ('custom', 'Custom Size'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    label_size = models.CharField(max_length=20, choices=LABEL_SIZE_CHOICES, default='50x30')
    width_mm = models.PositiveIntegerField(default=50, help_text='Width in millimeters')
    height_mm = models.PositiveIntegerField(default=30, help_text='Height in millimeters')
    include_name = models.BooleanField(default=True)
    include_barcode = models.BooleanField(default=True)
    include_qr_code = models.BooleanField(default=False)
    include_location = models.BooleanField(default=True)
    include_description = models.BooleanField(default=False)
    font_size = models.PositiveIntegerField(default=12, help_text='Font size in points')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='label_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Category(models.Model):
    """Category for organizing items (e.g., Electronics, Tools, Kitchenware)"""
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', help_text='Parent category for hierarchical organization')
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#007bff', help_text='Hex color code')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    def get_full_path(self):
        """Get the full hierarchical path as a string"""
        if self.parent:
            return f"{self.parent.get_full_path()} → {self.name}"
        return self.name
    
    def get_ancestors(self):
        """Get all ancestor categories"""
        ancestors = []
        category = self
        while category.parent:
            ancestors.append(category.parent)
            category = category.parent
        return ancestors[::-1]  # Return in order from root to parent

    def get_descendants(self):
        """Get all descendant categories (BFS over children)"""
        descendants = []
        queue = list(self.children.all())
        while queue:
            category = queue.pop(0)
            descendants.append(category)
            queue.extend(category.children.all())
        return descendants


class Item(models.Model):
    """Individual inventory item"""
    
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    min_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(0)], help_text='Minimum quantity threshold for low stock alerts')
    
    # Location
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, related_name='items')
    
    # Categories
    categories = models.ManyToManyField(Category, blank=True, related_name='items')
    
    # Lending permissions
    available_for_lending = models.BooleanField(default=True, help_text='Allow external users to borrow this item')
    
    # Identification
    serial_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    
    # Barcodes
    barcode = models.CharField(max_length=100, blank=True, null=True, unique=True)
    qr_code = models.CharField(max_length=500, blank=True, null=True)
    
    # Purchase information
    purchase_date = models.DateField(blank=True, null=True)
    purchase_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    current_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_items')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['barcode']),
            models.Index(fields=['location']),
            models.Index(fields=['available_for_lending']),
            models.Index(fields=['quantity']),
            models.Index(fields=['location', 'available_for_lending']),  # Composite index for API queries
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate barcode if not provided (UUID-based: collision-free)
        if not self.barcode:
            self.barcode = self.generate_barcode()

        super().save(*args, **kwargs)

        # QR code embeds the item URL, which needs the pk - generate after save
        if not self.qr_code:
            self.qr_code = self._qr_code_url()
            super().save(update_fields=['qr_code'])

    def _qr_code_url(self):
        """Absolute URL encoded in the QR code, based on SITE_URL setting."""
        from django.urls import reverse
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
        return f"{site_url}{reverse('items:item_detail', args=[self.pk])}"

    def generate_barcode(self):
        """Generate a unique barcode (UUID-based, collision-free)"""
        import uuid
        return uuid.uuid4().hex[:12].upper()
    
    def generate_barcode_svg(self):
        """Generate Code 128 barcode as SVG"""
        if not self.barcode:
            return None
        
        code128 = barcode.get_barcode('code128', self.barcode)
        return code128.render()
    
    def generate_qr_code_image(self):
        """Generate QR code image"""
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
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('items:item_detail', kwargs={'pk': self.pk})
    
    def is_borrowed(self):
        """Check if item is currently borrowed (any quantity)"""
        from apps.lending.models import Lending
        return Lending.objects.filter(item=self, returned_date__isnull=True).exists()
    
    def get_available_quantity(self):
        """Get available quantity (total - lent)"""
        from apps.lending.models import Lending
        from django.db.models import Sum
        lent_quantity = Lending.objects.filter(
            item=self,
            returned_date__isnull=True
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return self.quantity - lent_quantity
    
    def get_current_borrower(self):
        """Get current borrower if item is borrowed"""
        from apps.lending.models import Lending
        lending = Lending.objects.filter(item=self, returned_date__isnull=True).first()
        return lending.borrower_display if lending else None
    
    def is_low_stock(self):
        """Check if item is below minimum quantity threshold"""
        return self.quantity < self.min_quantity


class ItemImage(models.Model):
    """Multiple images for an item"""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='item_images/')
    thumbnail = models.ImageField(upload_to='item_thumbnails/', blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_primary', '-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.item.name}"
    
    def save(self, *args, **kwargs):
        """Generate thumbnail on save"""
        super().save(*args, **kwargs)
        if self.image and not self.thumbnail:
            from .utils import save_thumbnail
            save_thumbnail(self, 'image', 'thumbnail', size=(300, 300))
            # objects.create() passes force_insert=True through kwargs;
            # the second save must UPDATE the row just inserted, not
            # re-INSERT with the same pk (duplicate key error).
            kwargs.pop('force_insert', None)
            super().save(*args, **kwargs)