from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    """Extended user profile for additional information"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
        ('lender', 'Lender'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='editor')
    phone = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    notification_email = models.BooleanField(default=True)
    notification_borrowing = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username}'s profile ({self.role})"
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_editor(self):
        return self.role in ['admin', 'editor']
    
    def is_viewer(self):
        return self.role == 'viewer'
    
    def is_lender(self):
        return self.role == 'lender'


class Household(models.Model):
    """Household for grouping users. NOTE: inventory data (items, locations,
    etc.) is intentionally shared across all users - households manage
    membership/invites only and do not scope data."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    members = models.ManyToManyField(User, through='HouseholdMember', related_name='households')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_households')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Household'
        verbose_name_plural = 'Households'
    
    def __str__(self):
        return self.name


class HouseholdMember(models.Model):
    """Through model for household membership with roles"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]
    
    household = models.ForeignKey(Household, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['household', 'user']
        verbose_name = 'Household Member'
        verbose_name_plural = 'Household Members'
    
    def __str__(self):
        return f"{self.user.username} - {self.household.name} ({self.role})"


class ExternalHousehold(models.Model):
    """Track external households connected via API"""
    name = models.CharField(max_length=200)
    base_url = models.URLField(help_text="Base URL of the external instance")
    # api_key_hash stores sha256 of the key the remote household presents to us.
    # The plaintext key is never stored. api_key_for_them is the key WE present
    # to the remote instance, so it must remain retrievable.
    api_key_hash = models.CharField(max_length=64, blank=True, default='', db_index=True,
                                    help_text="SHA-256 hash of the API key they use to call us")
    api_key_for_them = models.CharField(max_length=100, blank=True, help_text="API key we share with them (they use it to call our API)")
    remote_api_key = models.CharField(max_length=100, blank=True, help_text="API key they shared with us (we use it to call THEIR API - stored plaintext because we must present it)")
    allowed_ips = models.TextField(blank=True, help_text="Comma-separated list of allowed IP addresses")
    api_key_expires = models.DateTimeField(null=True, blank=True, help_text="When this API key expires")
    is_instance_key = models.BooleanField(default=False, help_text="Shared instance key - any external household can use it to access this instance's API")
    last_accessed = models.DateTimeField(null=True, blank=True, help_text="Last time this API key was used")
    access_count = models.IntegerField(default=0, help_text="Number of times this API key has been used")
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'External Household'
        verbose_name_plural = 'External Households'
    
    def __str__(self):
        return f"{self.name} ({self.base_url})"
    
    def is_key_valid(self):
        """Check if API key is still valid"""
        if not self.active:
            return False
        if self.api_key_expires and self.api_key_expires < timezone.now():
            return False
        return True
    
    def is_ip_allowed(self, ip_address):
        """Check if IP address is allowed"""
        if not self.allowed_ips:
            return True  # No IP restrictions
        allowed_list = [ip.strip() for ip in self.allowed_ips.split(',')]
        return ip_address in allowed_list