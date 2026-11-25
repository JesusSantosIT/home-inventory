from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from apps.items.models import Item
from django.utils import timezone

User = get_user_model()


class Lending(models.Model):
    """Track items borrowed by anyone (registered users or external people)"""
    
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='lendings')
    external_household = models.ForeignKey(
        'users.ExternalHousehold', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lendings',
        help_text='External household this lending was requested through (API)'
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], help_text='Number of items borrowed')
    borrower_name = models.CharField(max_length=200, blank=True, null=True, help_text='Name of the person borrowing the item')
    borrowed_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='borrowed_items', help_text='Registered user (if applicable)')
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    returned_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_lendings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-borrowed_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['borrower_name']),
            models.Index(fields=['item']),
            models.Index(fields=['borrowed_by_user']),
            models.Index(fields=['returned_date']),  # For active lending queries
            models.Index(fields=['item', 'returned_date']),  # Composite for available quantity
        ]
    
    def __str__(self):
        if self.borrowed_by_user:
            return f"{self.item.name} borrowed by {self.borrowed_by_user.username}"
        return f"{self.item.name} borrowed by {self.borrower_name}"
    
    @property
    def borrower_display(self):
        """Get the display name for the borrower"""
        if self.borrowed_by_user:
            return self.borrowed_by_user.username
        return self.borrower_name
    
    def save(self, *args, **kwargs):
        # Auto-update status based on dates
        if self.returned_date:
            self.status = 'returned'
        elif self.due_date < timezone.now():
            self.status = 'overdue'
        else:
            self.status = 'borrowed'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def sync_statuses(cls):
        """Bulk-update stale status fields (status is only set on save(),
        so rows become overdue while untouched). Returns number updated."""
        now = timezone.now()
        updated = cls.objects.filter(
            returned_date__isnull=True, due_date__lt=now
        ).exclude(status='overdue').update(status='overdue')
        updated += cls.objects.filter(
            returned_date__isnull=False
        ).exclude(status='returned').update(status='returned')
        updated += cls.objects.filter(
            returned_date__isnull=True, due_date__gte=now
        ).exclude(status='borrowed').update(status='borrowed')
        return updated

    def is_overdue(self):
        """Check if the lending is overdue"""
        return self.due_date < timezone.now() and not self.returned_date
    
    def days_overdue(self):
        """Calculate days overdue"""
        if self.is_overdue():
            return (timezone.now() - self.due_date).days
        return 0
    
    def days_remaining(self):
        """Calculate days remaining until due"""
        if not self.returned_date and self.due_date > timezone.now():
            return (self.due_date - timezone.now()).days
        return 0