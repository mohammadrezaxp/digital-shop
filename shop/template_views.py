from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "shop/home.html"


class CatalogView(TemplateView):
    template_name = "shop/catalog.html"


class AboutView(TemplateView):
    template_name = "shop/about.html"


class LoginView(TemplateView):
    template_name = "shop/login.html"


class SignupView(TemplateView):
    template_name = "shop/signup.html"


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "shop/profile.html"
    login_url = "/login/"


home_view = HomeView.as_view()
catalog_view = CatalogView.as_view()
about_view = AboutView.as_view()
login_view = LoginView.as_view()
signup_view = SignupView.as_view()
profile_view = ProfileView.as_view()
