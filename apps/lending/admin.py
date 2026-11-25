from django.contrib import admin
from .models import Lending


class LendingAdmin(admin.ModelAdmin):
    list_display = ['item', 'borrower_display', 'borrowed_date', 'due_date', 'returned_date', 'status']
    list_filter = ['status', 'borrowed_date', 'due_date']
    search_fields = ['item__name', 'borrower_name', 'borrowed_by_user__username', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'status']
    
    fieldsets = (
        (None, {
            'fields': ('item', 'borrower_name', 'borrowed_by_user', 'due_date', 'returned_date', 'notes')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        Lending.sync_statuses()
        qs = super().get_queryset(request)
        return qs.select_related('item', 'borrowed_by_user', 'created_by')


admin.site.register(Lending, LendingAdmin)