import os
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import (AnonRateThrottle, ScopedRateThrottle,
                                       UserRateThrottle)
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (Address, Category, Coupon, CouponUsage, LoginAttempt,
                     Notification, Order, OrderItem, Product, ProductVariant,
                     SiteSettings, Subscription, User, Wallet,
                     WalletTransaction)
from .serializers import (AddressSerializer, CategorySerializer,
                          CouponSerializer, CouponValidateSerializer,
                          NotificationSerializer, OrderCreateSerializer,
                          OrderItemSerializer, OrderSerializer,
                          ProductDetailSerializer, ProductListSerializer,
                          ProductVariantSerializer, SiteSettingsSerializer,
                          SubscriptionSerializer, UserProfileSerializer,
                          UserSerializer, WalletSerializer,
                          WalletTransactionSerializer)


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
            data = super().validate(attrs)
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
                    failure_reason=str(e),
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
                self.user.backup_codes.remove(two_factor_code)
                self.user.save(update_fields=["backup_codes"])
                verified = True

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

        data["user"] = UserSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AnonRateThrottle]
    throttle_scope = "login"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.set_password(request.data["password"])
        user.save()
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

    @transaction.atomic
    def _create_order(self, user, data):
        items_data = data["items"]
        coupon_code = data.get("coupon_code", "").strip()
        payment_method = data["payment_method"]

        product_ids = [item["product_id"] for item in items_data]
        variant_ids = [
            item.get("variant_id") for item in items_data if item.get("variant_id")
        ]

        products = Product.objects.in_bulk(product_ids)
        variants = ProductVariant.objects.in_bulk(variant_ids) if variant_ids else {}

        subtotal = Decimal("0")
        order_items = []

        for item_data in items_data:
            product = products.get(item_data["product_id"])
            if not product or product.status != Product.Status.ACTIVE:
                return Response(
                    {"error": f"محصول {item_data['product_id']} موجود نیست"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            variant = None
            if item_data.get("variant_id"):
                variant = variants.get(item_data["variant_id"])
                if (
                    not variant
                    or variant.product_id != product.id
                    or not variant.is_active
                ):
                    return Response(
                        {"error": f"تنوع محصول معتبر نیست"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                unit_price = variant.price
                if variant.stock < item_data.get("quantity", 1):
                    return Response(
                        {"error": f"موجودی تنوع {variant.name} کافی نیست"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                unit_price = product.price
                if product.stock < item_data.get("quantity", 1):
                    return Response(
                        {"error": f"موجودی {product.name} کافی نیست"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            quantity = item_data.get("quantity", 1)
            total_price = unit_price * quantity
            subtotal += total_price

            order_items.append(
                {
                    "product": product,
                    "variant": variant,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                }
            )

        discount = Decimal("0")
        coupon = None
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code)
                valid, msg = coupon.is_valid(user, subtotal)
                if not valid:
                    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
                discount = coupon.calculate_discount(subtotal)
            except Coupon.DoesNotExist:
                return Response(
                    {"error": "کوپن یافت نشد"}, status=status.HTTP_400_BAD_REQUEST
                )

        tax = Decimal("0")
        total = subtotal - discount + tax

        order = Order.objects.create(
            user=user,
            status=Order.Status.PENDING,
            payment_method=payment_method,
            tracking_code=self._generate_tracking_code(),
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            total=total,
        )

        for item_data in order_items:
            OrderItem.objects.create(
                order=order,
                product=item_data["product"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            )
            if item_data["variant"]:
                item_data["variant"].stock -= item_data["quantity"]
                item_data["variant"].save(update_fields=["stock"])
            else:
                item_data["product"].stock -= item_data["quantity"]
                item_data["product"].sold_count += item_data["quantity"]
                item_data["product"].save(update_fields=["stock", "sold_count"])

        if coupon:
            CouponUsage.objects.create(
                coupon=coupon,
                user=user,
                order=order,
                discount_amount=discount,
            )
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def _generate_tracking_code(self):
        import uuid

        return f"DS{uuid.uuid4().hex[:10].upper()}"

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status not in [Order.Status.PENDING, Order.Status.PAID]:
            return Response(
                {"error": "سفارش قابل لغو نیست"}, status=status.HTTP_400_BAD_REQUEST
            )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order).data)


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

        cart_total = serializer.validated_data["cart_total"]
        valid, msg = coupon.is_valid(request.user, cart_total)
        if not valid:
            return Response(
                {"valid": False, "message": msg}, status=status.HTTP_400_BAD_REQUEST
            )

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
                user.orders.select_related().prefetch_related("items__product")[:5],
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
            user.backup_codes.remove(code)
            verified = True

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
    """Verify 2FA code during login (used after password auth)."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "").strip()
        code = request.data.get("code", "").strip()

        if not username or not code:
            return Response(
                {"error": "Username and code required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.two_factor_enabled:
            return Response(
                {"error": "2FA not enabled for this account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify TOTP
        verified = False
        if user.two_factor_secret:
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(code, valid_window=1):
                verified = True

        # Verify backup code
        if not verified and user.backup_codes and code in user.backup_codes:
            user.backup_codes.remove(code)
            user.save(update_fields=["backup_codes"])
            verified = True

        if not verified:
            return Response(
                {"error": "Invalid 2FA code"}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Return tokens (like normal login)
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


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
            user.backup_codes.remove(code)
            verified = True

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
