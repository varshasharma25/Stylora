"""
Stylora Master URL Configuration.
"""

from pathlib import Path

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.contrib.staticfiles import finders


def service_worker_view(request):
    """Serve the PWA service worker from the website root."""
    worker_path = finders.find("js/service-worker.js")
    if not worker_path:
        return HttpResponse("Service worker file not found.", status=404)

    response = HttpResponse(
        Path(worker_path).read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def pwa_manifest_view(request):
    """Serve the PWA manifest with its correct MIME type."""
    manifest_path = finders.find("manifest.webmanifest")
    if not manifest_path:
        return HttpResponse("PWA manifest not found.", status=404)

    response = HttpResponse(
        Path(manifest_path).read_text(encoding="utf-8"),
        content_type="application/manifest+json; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    return response


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
    path('service-worker.js', service_worker_view, name='service-worker'),
    path('manifest.webmanifest', pwa_manifest_view, name='pwa-manifest'),
    path('', include('apps.accounts.urls')),
    path('', include('apps.wardrobe.urls')),
    path('', include('apps.stylist.urls')),
    path('', include('apps.outfits.urls')),
]

# Serve media and static files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
