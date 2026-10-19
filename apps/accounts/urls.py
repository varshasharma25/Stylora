from django.urls import path
from .views import (
    LandingPageView,
    SignUpView,
    LoginView,
    LogoutView,
    DashboardView,
    TodayOutfitView,
    ProfileView,
    StyloraPasswordChangeView,
)

app_name = 'accounts'

urlpatterns = [
    path('', LandingPageView.as_view(), name='landing'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/today-outfit/', TodayOutfitView.as_view(), name='today-outfit'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/password-change/', StyloraPasswordChangeView.as_view(), name='password-change'),
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
]
