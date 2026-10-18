from django.shortcuts import render, redirect
from django.views.generic import View, TemplateView
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib import messages
from .forms import SignUpForm, LoginForm


class LandingPageView(View):
    """Public landing page; redirects authenticated users to their dashboard."""

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return render(request, 'accounts/landing.html')


class SignUpView(View):
    """User registration view with automatic session login on completion."""

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = SignUpForm()
        return render(request, 'accounts/signup.html', {'form': form})

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Stylora, {user.username}! Your digital closet is ready.")
            return redirect('accounts:dashboard')
        return render(request, 'accounts/signup.html', {'form': form})


class LoginView(DjangoLoginView):
    """Standard authentication view with tailored styling and redirect."""
    form_class = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return super().form_valid(form)


class LogoutView(View):
    """Secure POST-only logout view."""

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
            messages.info(request, "You have been logged out safely.")
        return redirect('accounts:landing')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Protected home dashboard showing wardrobe statistics and onboarding state."""
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.wardrobe.models import ClothingItem
        from apps.outfits.models import Outfit
        context['wardrobe_count'] = ClothingItem.objects.filter(
            user=self.request.user,
            is_active=True
        ).count()
        context['saved_outfits_count'] = Outfit.objects.filter(
            user=self.request.user
        ).count()
        return context
