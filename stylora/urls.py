"""
Stylora Master URL Configuration.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def health_check_view(request):
    """Basic application verification route for monitoring and local health checks."""
    return JsonResponse({
        "status": "healthy",
        "app": "Stylora",
        "tagline": "Your wardrobe, styled.",
        "version": "1.0",
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check_view, name='health-check'),
    path('', include('apps.accounts.urls')),
    path('', include('apps.wardrobe.urls')),
    path('', include('apps.stylist.urls')),
]

# Serve media and static files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
