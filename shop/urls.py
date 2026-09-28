from django.urls import path

from .template_views import (about_view, catalog_view, home_view, login_view,
                             profile_view, signup_view)

app_name = "shop"

urlpatterns = [
    path("", home_view, name="home"),
    path("catalog/", catalog_view, name="catalog"),
    path("about/", about_view, name="about"),
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("profile/", profile_view, name="profile"),
]
