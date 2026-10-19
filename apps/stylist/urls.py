from django.urls import path
from .views import StylistChatView, SendMessageView, FindMyColourView, SaveColourAnalysisView

app_name = 'stylist'

urlpatterns = [
    path('stylist/', StylistChatView.as_view(), name='chat'),
    path('stylist/message/', SendMessageView.as_view(), name='send-message'),
    path('stylist/find-my-colour/', FindMyColourView.as_view(), name='color-analysis'),
    path('stylist/find-my-colour/save/', SaveColourAnalysisView.as_view(), name='color-analysis-save'),
]
