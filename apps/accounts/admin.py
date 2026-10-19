from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_aesthetic', 'fit_preference', 'dressing_goal', 'color_season', 'color_analysis_consent', 'updated_at')
    list_filter = ('preferred_aesthetic', 'fit_preference', 'dressing_goal', 'color_season', 'color_analysis_consent')
    search_fields = ('user__username', 'user__email', 'favorite_colors')
