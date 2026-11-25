from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory
from .models import Location


class LocationAdmin(TreeAdmin):
    form = movenodeform_factory(Location)
    list_display = ['name', 'location_type', 'get_full_path', 'get_item_count', 'created_at']
    list_filter = ['location_type', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'get_full_path', 'get_item_count']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'location_type', 'description')
        }),
        ('Hierarchy', {
            'fields': ('_position', '_ref_node_id'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('get_full_path', 'get_item_count'),
            'classes': ('collapse',),
        }),
    )


admin.site.register(Location, LocationAdmin)