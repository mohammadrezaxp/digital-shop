from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("wallet/", views.wallet, name="wallet"),
    path("transfer/", views.transfer, name="transfer"),
    path("transactions/", views.transactions, name="transactions"),
    path("profile/", views.profile, name="profile"),
]
