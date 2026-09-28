"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from shop.views import (AddressViewSet, CategoryViewSet, CouponValidateView,
                        CustomTokenObtainPairView, DashboardStatsView,
                        HealthCheckView, NotificationViewSet, OrderViewSet,
                        ProductVariantViewSet, ProductViewSet, RegisterView,
                        SiteSettingsView, SubscriptionViewSet,
                        TwoFactorBackupCodesView, TwoFactorDisableView,
                        TwoFactorSetupView, TwoFactorVerifyView,
                        UserProfileView, WalletTransactionViewSet, WalletView)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"variants", ProductVariantViewSet, basename="variant")
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(
    r"wallet/transactions", WalletTransactionViewSet, basename="wallet-transaction"
)
router.register(r"addresses", AddressViewSet, basename="address")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("admin/", admin.site.urls),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Health check
    path("health/", HealthCheckView.as_view(), name="health-check"),
    # Auth
    path(
        "api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/profile/", UserProfileView.as_view(), name="user-profile"),
    # 2FA endpoints
    path("api/auth/2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("api/auth/2fa/disable/", TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("api/auth/2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path(
        "api/auth/2fa/backup-codes/",
        TwoFactorBackupCodesView.as_view(),
        name="2fa-backup-codes",
    ),
    # Core API
    path("api/wallet/", WalletView.as_view(), name="wallet"),
    path("api/coupons/validate/", CouponValidateView.as_view(), name="coupon-validate"),
    path("api/settings/", SiteSettingsView.as_view(), name="site-settings"),
    path("api/dashboard/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("api/", include(router.urls)),
    path("", include("shop.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=(
            settings.STATICFILES_DIRS[0]
            if settings.STATICFILES_DIRS
            else settings.STATIC_ROOT
        ),
    )
