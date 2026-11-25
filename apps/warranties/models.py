from django.db import models
from django.contrib.auth import get_user_model
from apps.items.models import Item
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Warranty(models.Model):
    """Warranty information for items"""
    
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='warranty')
    provider = models.CharField(max_length=200)
    policy_number = models.CharField(max_length=100, blank=True, null=True)
    purchase_date = models.DateField(blank=True, null=True)
    expiration_date = models.DateField()
    coverage_details = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_warranties')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Warranties'
        ordering = ['expiration_date']
        indexes = [
            models.Index(fields=['expiration_date']),
            models.Index(fields=['provider']),
        ]
    
    def __str__(self):
        return f"Warranty for {self.item.name} - {self.provider}"
    
    def is_active(self):
        """Check if warranty is still active"""
        return self.expiration_date >= timezone.now().date()
    
    def days_remaining(self):
        """Calculate days remaining until expiration"""
        if self.is_active():
            return (self.expiration_date - timezone.now().date()).days
        return 0
    
    def is_expiring_soon(self, days=30):
        """Check if warranty is expiring within specified days"""
        return self.is_active() and self.days_remaining() <= days