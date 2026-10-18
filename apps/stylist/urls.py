from django.urls import path
from .views import StylistChatView, SendMessageView

app_name = 'stylist'

urlpatterns = [
    path('stylist/', StylistChatView.as_view(), name='chat'),
    path('stylist/message/', SendMessageView.as_view(), name='send-message'),
]
