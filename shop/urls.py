from django.urls import path
from .template_views import (
    home_view, catalog_view, about_view,
    login_view, signup_view, profile_view
)

app_name = 'shop'

urlpatterns = [
    path('', home_view, name='home'),
    path('catalog/', catalog_view, name='catalog'),
    path('about/', about_view, name='about'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('profile/', profile_view, name='profile'),
]