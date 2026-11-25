from django.contrib import admin
from .models import Warranty


class WarrantyAdmin(admin.ModelAdmin):
    list_display = ['item', 'provider', 'expiration_date', 'is_active', 'days_remaining', 'created_at']
    list_filter = ['expiration_date', 'provider', 'purchase_date']
    search_fields = ['item__name', 'provider', 'policy_number', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'is_active', 'days_remaining']
    
    fieldsets = (
        (None, {
            'fields': ('item', 'provider', 'policy_number')
        }),
        ('Dates', {
            'fields': ('purchase_date', 'expiration_date')
        }),
        ('Details', {
            'fields': ('coverage_details', 'notes')
        }),
        ('Status', {
            'fields': ('is_active', 'days_remaining'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    def days_remaining(self, obj):
        return obj.days_remaining()
    days_remaining.short_description = 'Days Remaining'


admin.site.register(Warranty, WarrantyAdmin)