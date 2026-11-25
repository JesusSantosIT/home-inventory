from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Item, Category, ItemImage


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1
    fields = ['image', 'caption', 'is_primary']


class ItemResource(resources.ModelResource):
    class Meta:
        model = Item
        fields = ('id', 'name', 'description', 'quantity', 'serial_number', 
                 'brand', 'model', 'barcode', 'purchase_date', 'purchase_price',
                 'current_value', 'condition', 'location', 'categories')


class ItemAdmin(ImportExportModelAdmin):
    resource_class = ItemResource
    list_display = ['name', 'location', 'quantity', 'serial_number', 'purchase_price', 
                   'current_value', 'condition', 'created_at']
    list_filter = ['condition', 'purchase_date', 'categories', 'location']
    search_fields = ['name', 'description', 'serial_number', 'brand', 'model', 'barcode']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ItemImageInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'quantity')
        }),
        ('Location & Categories', {
            'fields': ('location', 'categories')
        }),
        ('Identification', {
            'fields': ('serial_number', 'brand', 'model', 'barcode', 'qr_code')
        }),
        ('Purchase Information', {
            'fields': ('purchase_date', 'purchase_price', 'current_value', 'condition')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    search_fields = ['name', 'description']


class ItemImageAdmin(admin.ModelAdmin):
    list_display = ['item', 'caption', 'is_primary', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['item__name', 'caption']


admin.site.register(Item, ItemAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(ItemImage, ItemImageAdmin)