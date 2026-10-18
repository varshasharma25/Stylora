from django.urls import path
from .views import SaveOutfitView, DeleteOutfitView, SavedOutfitsListView

app_name = 'outfits'

urlpatterns = [
    path('outfits/', SavedOutfitsListView.as_view(), name='gallery'),
    path('outfits/save/', SaveOutfitView.as_view(), name='save'),
    path('outfits/<int:pk>/delete/', DeleteOutfitView.as_view(), name='delete'),
]
