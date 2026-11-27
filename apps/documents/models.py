from django.db import models
from django.contrib.auth import get_user_model
from apps.items.models import Item

User = get_user_model()


class Document(models.Model):
    """Document model for receipts, manuals, warranties, etc."""
    
    DOCUMENT_TYPES = [
        ('receipt', 'Receipt'),
        ('warranty', 'Warranty'),
        ('manual', 'Manual'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ]
    
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('documents:document_detail', kwargs={'pk': self.pk})
