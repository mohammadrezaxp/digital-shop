from rest_framework import serializers
from django.utils import timezone
from .models import (
    User, Category, Product, ProductVariant, Order, OrderItem,
    Subscription, Wallet, WalletTransaction, Coupon, CouponUsage,
    Address, Notification, SiteSettings
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "avatar", "email_verified", "date_joined", "last_login"]
        read_only_fields = ["id", "email_verified", "date_joined", "last_login"]


class UserProfileSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.SerializerMethodField()
    active_subscriptions_count = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "avatar", "email_verified", "wallet_balance", "active_subscriptions_count", "orders_count"]
        read_only_fields = ["id", "email_verified"]

    def get_wallet_balance(self, obj):
        return obj.wallet.balance if hasattr(obj, "wallet") else 0

    def get_active_subscriptions_count(self, obj):
        return obj.subscriptions.filter(status=Subscription.Status.ACTIVE, expires_at__gt=timezone.now()).count()

    def get_orders_count(self, obj):
        return obj.orders.count()


class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "description", "order", "is_active", "products_count"]


class ProductVariantSerializer(serializers.ModelSerializer):
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ["id", "name", "sku", "price", "metadata", "stock", "is_active", "discount_percent"]

    def get_discount_percent(self, obj):
        return 0


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    discount_percent = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category_name", "category_slug", "type", "status", "short_description", "logo", "thumbnail", "price", "original_price", "duration_days", "discount_percent", "is_in_stock", "is_featured", "sold_count"]

    def get_discount_percent(self, obj):
        if obj.original_price and obj.original_price > obj.price:
            return int((obj.original_price - obj.price) / obj.original_price * 100)
        return 0


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    discount_percent = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "type", "status", "description", "short_description", "logo", "thumbnail", "price", "original_price", "duration_days", "features", "metadata", "stock", "sold_count", "is_featured", "variants", "discount_percent", "is_in_stock", "created_at", "updated_at"]

    def get_discount_percent(self, obj):
        if obj.original_price and obj.original_price > obj.price:
            return int((obj.original_price - obj.price) / obj.original_price * 100)
        return 0


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "product_slug", "variant", "variant_name", "quantity", "unit_price", "total_price", "delivery_content", "is_delivered", "delivered_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "tracking_code", "status", "status_display", "payment_method", "payment_method_display", "subtotal", "discount", "tax", "total", "items", "paid_at", "created_at", "updated_at"]
        read_only_fields = ["id", "tracking_code", "subtotal", "discount", "tax", "total", "paid_at", "created_at", "updated_at"]


class OrderCreateSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)


class SubscriptionSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "product", "variant", "status", "status_display", "starts_at", "expires_at", "auto_renew", "is_active", "days_remaining", "created_at"]


class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = Wallet
        fields = ["balance", "blocked_balance", "available_balance", "updated_at"]
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = ["id", "type", "type_display", "status", "status_display", "amount", "description", "reference_id", "created_at", "completed_at"]
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Coupon
        fields = ["id", "code", "type", "type_display", "value", "max_discount", "min_order_amount", "valid_from", "valid_until", "is_active"]


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    cart_total = serializers.DecimalField(max_digits=12, decimal_places=0, default=0)
    items = serializers.ListField(child=serializers.DictField(), required=False)


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "full_name", "phone", "province", "city", "address", "postal_code", "is_default"]


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "type", "type_display", "title", "message", "data", "is_read", "created_at"]
        read_only_fields = fields


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ["site_name", "site_description", "contact_email", "contact_phone", "address", "social_links", "maintenance_mode", "maintenance_message", "free_shipping_threshold"]
        read_only_fields = fields