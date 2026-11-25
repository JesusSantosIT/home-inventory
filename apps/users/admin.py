from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Household, HouseholdMember


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 1


class HouseholdAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at', 'member_count']
    search_fields = ['name', 'description']
    inlines = [HouseholdMemberInline]
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'household', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__username', 'household__name']


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Household, HouseholdAdmin)
admin.site.register(HouseholdMember, HouseholdMemberAdmin)