import os
from decimal import Decimal

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    UserRateThrottle,
)
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    Address,
    Category,
    Coupon,
    CouponUsage,
    LoginAttempt,
    Notification,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    SiteSettings,
    Subscription,
    User,
    Wallet,
    WalletTransaction,
)
from .serializers import (
    AddressSerializer,
    CategorySerializer,
    CouponSerializer,
    CouponValidateSerializer,
    NotificationSerializer,
    OrderCreateSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    SiteSettingsSerializer,
    SubscriptionSerializer,
    UserProfileSerializer,
    UserSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    two_factor_code = serializers.CharField(required=False, write_only=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["is_staff"] = user.is_staff
        return token

    def validate(self, attrs):
        # Get client IP
        request = self.context.get("request")
        ip = None
        if request:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR")

        # Check if user exists and is locked
        username = attrs.get("username") or attrs.get("email")
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(email=username)
                except User.DoesNotExist:
                    pass

        if user and user.is_locked:
            LoginAttempt.objects.create(
                user=user,
                username=user.username,
                ip_address=ip or "unknown",
                user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
                status=LoginAttempt.Status.LOCKED,
                failure_reason="Account temporarily locked due to failed attempts",
            )
            raise serializers.ValidationError(
                {
                    "detail": "حساب شما به دلیل تلاش‌های ناموفق موقتاً قفل شده است. لطفاً ۳۰ دقیقه صبر کنید.",
                    "code": "account_locked",
                    "locked_until": (
                        user.locked_until.isoformat() if user.locked_until else None
                    ),
                }
            )

        # Check if 2FA is enabled and code provided
        two_factor_code = (
            attrs.get("two_factor_code", "").strip()
            if attrs.get("two_factor_code")
            else ""
        )

        # Call parent validate (handles authentication)
        try:
            self.user = authenticate(
                request=request,
                username=attrs.get("username"),
                password=attrs.get("password"),
            )
            if self.user is None or not self.user.is_active:
                raise AuthenticationFailed(
                    "No active account found with the given credentials"
                )
            data = {}
        except Exception as e:
            # Log failed attempt
            if user:
                user.record_failed_login()
                LoginAttempt.objects.create(
                    user=user,
                    username=user.username,
                    ip_address=ip or "unknown",
                    user_agent=(
                        request.META.get("HTTP_USER_AGENT", "") if request else ""
                    ),
                    status=LoginAttempt.Status.FAILED,
                    failure_reason="Invalid credentials",
                )
            else:
                # Log attempt for non-existent user (but don't reveal user existence)
                LoginAttempt.objects.create(
                    username=username or "unknown",
                    ip_address=ip or "unknown",
                    user_agent=(
                        request.META.get("HTTP_USER_AGENT", "") if request else ""
                    ),
                    status=LoginAttempt.Status.FAILED,
                    failure_reason="Invalid credentials",
                )
            # Re-raise the original exception
            raise

        # Check if 2FA is required
        if self.user and self.user.two_factor_enabled:
            if not two_factor_code:
                # 2FA required but no code provided
                raise serializers.ValidationError(
                    {
                        "detail": "کد احراز هویت دو مرحله‌ای مورد نیاز است",
                        "code": "two_factor_required",
                    }
                )

            # Verify 2FA code
            import pyotp

            verified = False
            if self.user.two_factor_secret:
                totp = pyotp.TOTP(self.user.two_factor_secret)
                if totp.verify(two_factor_code, valid_window=1):
                    verified = True

            if (
                not verified
                and self.user.backup_codes
                and two_factor_code in self.user.backup_codes
            ):
                verified = self.user.consume_backup_code(two_factor_code)

            if not verified:
                # Log failed 2FA attempt
                self.user.record_failed_login()
                LoginAttempt.objects.create(
                    user=self.user,
                    username=self.user.username,
                    ip_address=ip or "unknown",
                    user_agent=(
                        request.META.get("HTTP_USER_AGENT", "") if request else ""
                    ),
                    status=LoginAttempt.Status.FAILED,
                    failure_reason="Invalid 2FA code",
                )
                raise serializers.ValidationError(
                    {
                        "detail": "کد احراز هویت دو مرحله‌ای نامعتبر است",
                        "code": "invalid_two_factor_code",
                    }
                )

        # Record successful login
        if self.user:
            self.user.record_successful_login(ip)
            LoginAttempt.objects.create(
                user=self.user,
                username=self.user.username,
                ip_address=ip or "unknown",
                user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
                status=LoginAttempt.Status.SUCCESS,
            )

        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = UserSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        from .serializers import RegisterSerializer

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        Wallet.objects.get_or_create(user=user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).annotate(
        products_count=Count(
            "products", filter=Q(products__status=Product.Status.ACTIVE)
        )
    )
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["order", "name"]
    ordering = ["order", "name"]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Product.objects.filter(status=Product.Status.ACTIVE)
        .select_related("category")
        .prefetch_related("variants")
    )
    permission_classes = [AllowAny]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["category__slug", "type", "is_featured"]
    search_fields = ["name", "short_description", "description"]
    ordering_fields = ["price", "sold_count", "created_at"]
    ordering = ["-created_at"]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        return qs

    @action(detail=False, methods=["get"])
    def featured(self, request):
        products = self.get_queryset().filter(is_featured=True)[:8]
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def categories_with_products(self, request):
        categories = Category.objects.filter(is_active=True).prefetch_related(
            "products"
        )
        data = []
        for cat in categories:
            products = cat.products.filter(status=Product.Status.ACTIVE)[:4]
            data.append(
                {
                    "category": CategorySerializer(cat).data,
                    "products": ProductListSerializer(products, many=True).data,
                }
            )
        return Response(data)


class ProductVariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductVariant.objects.filter(is_active=True).select_related("product")
    serializer_class = ProductVariantSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["product__slug"]


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related(
            "items__product", "items__variant"
        )

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._create_order(request.user, serializer.validated_data)

    def _create_order(self, user, data):
        from .services import create_order

        order = create_order(user, data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Financial state is server-managed. Only unpaid payment method changes are editable.
        with transaction.atomic():
            order = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if order.status != Order.Status.PENDING or set(request.data) - {
                "payment_method"
            }:
                raise serializers.ValidationError(
                    "Only the payment method of a pending order can be edited."
                )
            method = request.data.get("payment_method", order.payment_method)
            if method not in Order.PaymentMethod.values:
                raise serializers.ValidationError("Invalid payment method.")
            if method == Order.PaymentMethod.WALLET and method != order.payment_method:
                from .services import pay_order

                pay_order(order)
            else:
                order.payment_method = method
                order.save(update_fields=["payment_method"])
        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        # Keep the financial record; the delete operation cancels the order.
        from .services import cancel_order

        cancel_order(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        from .services import cancel_order

        return Response(OrderSerializer(cancel_order(self.get_object())).data)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related(
            "product", "variant"
        )


class WalletView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["type", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet.transactions.all()


class CouponValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            coupon = Coupon.objects.get(code__iexact=serializer.validated_data["code"])
        except Coupon.DoesNotExist:
            return Response(
                {"valid": False, "message": "کوپن یافت نشد"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .services import coupon_discount, prepare_lines

        items = serializer.validated_data.get("items")
        if items:
            lines = prepare_lines(items)
            discount = coupon_discount(coupon, request.user, lines)
        else:
            if (
                coupon.applicable_products.exists()
                or coupon.applicable_categories.exists()
            ):
                raise serializers.ValidationError(
                    "Items are required for a scoped coupon."
                )
            cart_total = serializer.validated_data["cart_total"]
            valid, msg = coupon.is_valid(request.user, cart_total)
            if not valid:
                raise serializers.ValidationError(msg)
            discount = coupon.calculate_discount(cart_total)

        return Response(
            {
                "valid": True,
                "discount": discount,
                "coupon": CouponSerializer(coupon).data,
            }
        )


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user, is_default=True).update(
                is_default=False
            )
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user, is_default=True).update(
                is_default=False
            )
        serializer.save()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["type", "is_read"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"status": "ok"})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "ok"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})


class SiteSettingsView(generics.RetrieveAPIView):
    serializer_class = SiteSettingsSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return SiteSettings.get_settings()


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)

        stats = {
            "orders": {
                "total": user.orders.count(),
                "pending": user.orders.filter(status=Order.Status.PENDING).count(),
                "completed": user.orders.filter(status=Order.Status.COMPLETED).count(),
            },
            "subscriptions": {
                "total": user.subscriptions.count(),
                "active": user.subscriptions.filter(
                    status=Subscription.Status.ACTIVE, expires_at__gt=timezone.now()
                ).count(),
                "expiring_soon": user.subscriptions.filter(
                    status=Subscription.Status.ACTIVE,
                    expires_at__gt=timezone.now(),
                    expires_at__lte=timezone.now() + timezone.timedelta(days=7),
                ).count(),
            },
            "wallet": {
                "balance": wallet.balance,
                "available": wallet.available_balance,
            },
            "notifications": {
                "unread": user.notifications.filter(is_read=False).count(),
            },
            "recent_orders": OrderSerializer(
                user.orders.prefetch_related("items__product")[:5],
                many=True,
            ).data,
            "active_subscriptions": SubscriptionSerializer(
                user.subscriptions.filter(
                    status=Subscription.Status.ACTIVE, expires_at__gt=timezone.now()
                ).select_related("product", "variant")[:5],
                many=True,
            ).data,
        }
        return Response(stats)


import base64

# Two-Factor Authentication Views
import pyotp


class TwoFactorSetupView(APIView):
    """Setup 2FA for authenticated user - returns QR code and secret."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.two_factor_enabled:
            return Response(
                {"error": "2FA already enabled"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Generate TOTP secret if not exists
        if not user.two_factor_secret:
            secret = pyotp.random_base32()
            user.two_factor_secret = secret
            user.save(update_fields=["two_factor_secret"])
        else:
            secret = user.two_factor_secret

        # Generate QR code URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email or user.username, issuer_name="Digital Shop"
        )

        return Response(
            {
                "secret": secret,
                "qr_code_uri": provisioning_uri,
                "backup_codes": user.backup_codes or [],
            }
        )

    def post(self, request):
        """Verify TOTP code and enable 2FA."""
        user = request.user
        code = request.data.get("code", "").strip()

        if user.two_factor_enabled:
            raise serializers.ValidationError("2FA already enabled.")
        if not user.two_factor_secret:
            return Response(
                {"error": "2FA setup not initiated"}, status=status.HTTP_400_BAD_REQUEST
            )

        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"error": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Enable 2FA and generate backup codes
        user.two_factor_enabled = True
        backup_codes = [base64.b32encode(os.urandom(5)).decode()[:8] for _ in range(10)]
        user.backup_codes = backup_codes
        user.save(update_fields=["two_factor_enabled", "backup_codes"])

        return Response(
            {
                "message": "2FA enabled successfully",
                "backup_codes": backup_codes,
            }
        )


class TwoFactorDisableView(APIView):
    """Disable 2FA for authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        code = request.data.get("code", "").strip()

        if not user.two_factor_enabled:
            return Response(
                {"error": "2FA not enabled"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Verify either TOTP or backup code
        verified = False
        if user.two_factor_secret:
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(code, valid_window=1):
                verified = True

        if not verified and user.backup_codes and code in user.backup_codes:
            verified = user.consume_backup_code(code)

        if not verified:
            return Response(
                {"error": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.two_factor_enabled = False
        user.two_factor_secret = ""
        user.backup_codes = []
        user.save(
            update_fields=["two_factor_enabled", "two_factor_secret", "backup_codes"]
        )

        return Response({"message": "2FA disabled successfully"})


class TwoFactorVerifyView(APIView):
    """Compatibility endpoint: password and second factor are both required."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        payload = request.data.copy()
        payload["two_factor_code"] = payload.get("two_factor_code") or payload.get(
            "code", ""
        )
        serializer = CustomTokenObtainPairSerializer(
            data=payload, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class TwoFactorBackupCodesView(APIView):
    """Regenerate backup codes for 2FA."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.two_factor_enabled:
            return Response(
                {"error": "2FA not enabled"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Require current TOTP or backup code to regenerate
        code = request.data.get("code", "").strip()

        verified = False
        if user.two_factor_secret:
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(code, valid_window=1):
                verified = True

        if not verified and user.backup_codes and code in user.backup_codes:
            verified = user.consume_backup_code(code)

        if not verified:
            return Response(
                {"error": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST
            )

        backup_codes = [base64.b32encode(os.urandom(5)).decode()[:8] for _ in range(10)]
        user.backup_codes = backup_codes
        user.save(update_fields=["backup_codes"])

        return Response({"backup_codes": backup_codes})


class HealthCheckView(APIView):
    """Health check endpoint for Docker/load balancer."""

    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection

        try:
            connection.ensure_connection()
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"
        return Response(
            {
                "status": "healthy" if db_status == "healthy" else "unhealthy",
                "database": db_status,
                "version": "1.0.0",
            },
            status=(
                status.HTTP_200_OK
                if db_status == "healthy"
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )
