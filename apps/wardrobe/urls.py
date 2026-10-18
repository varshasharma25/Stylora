from django.urls import path
from .views import (
    WardrobeGalleryView,
    ClothingItemCreateView,
    ClothingItemUpdateView,
    ClothingItemDeleteView,
    ProtectedMediaView,
    ClothingMetadataSuggestView,
)

app_name = 'wardrobe'

urlpatterns = [
    path('wardrobe/', WardrobeGalleryView.as_view(), name='gallery'),
    path('wardrobe/add/', ClothingItemCreateView.as_view(), name='item-create'),
    path('wardrobe/<int:pk>/edit/', ClothingItemUpdateView.as_view(), name='item-edit'),
    path('wardrobe/<int:pk>/delete/', ClothingItemDeleteView.as_view(), name='item-delete'),
    path('wardrobe/suggest-metadata/', ClothingMetadataSuggestView.as_view(), name='suggest-metadata'),
    path('wardrobe/media/<int:pk>/<str:version>/', ProtectedMediaView.as_view(), name='protected-media'),
]
