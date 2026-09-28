from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Category, Product, ProductVariant, Order, OrderItem,
    Subscription, Wallet, WalletTransaction, Coupon, CouponUsage,
    Address, Notification, SiteSettings, LoginAttempt
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'phone', 'email_verified', 'phone_verified', 'two_factor_enabled', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'email_verified', 'phone_verified', 'two_factor_enabled']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('اطلاعات اضافی', {'fields': ('phone', 'avatar', 'email_verified', 'phone_verified', 'two_factor_enabled', 'two_factor_secret')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('اطلاعات اضافی', {'fields': ('email', 'first_name', 'last_name', 'phone')}),
    )
    readonly_fields = ['last_login_ip', 'failed_login_attempts', 'locked_until', 'password_changed_at', 'created_at', 'updated_at']


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['username', 'user', 'ip_address', 'status', 'failure_reason', 'created_at']
    list_filter = ['status']
    search_fields = ['username', 'ip_address', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['user', 'username', 'ip_address', 'user_agent', 'status', 'failure_reason', 'created_at']
    list_per_page = 50

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'order', 'is_active', 'products_count', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']

    def products_count(self, obj):
        return obj.products.count()
    products_count.short_description = 'تعداد محصولات'


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['name', 'sku', 'price', 'stock', 'is_active']
    ordering = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'type', 'status', 'price', 'original_price', 'stock', 'sold_count', 'is_featured', 'is_in_stock']
    list_filter = ['status', 'type', 'category', 'is_featured']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['-created_at']
    readonly_fields = ['sold_count', 'created_at', 'updated_at']
    inlines = [ProductVariantInline]
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'slug', 'category', 'type', 'status', 'is_featured')
        }),
        ('توضیحات', {
            'fields': ('description', 'short_description')
        }),
        ('تصاویر', {
            'fields': ('logo', 'thumbnail')
        }),
        ('قیمت‌گذاری', {
            'fields': ('price', 'original_price', 'duration_days')
        }),
        ('موجودی و فروش', {
            'fields': ('stock', 'sold_count')
        }),
        ('ویژگی‌ها و متادیتا', {
            'fields': ('features', 'metadata'),
            'classes': ('collapse',)
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'sku', 'price', 'stock', 'is_active', 'created_at']
    list_filter = ['is_active', 'product__category']
    search_fields = ['name', 'sku', 'product__name']
    ordering = ['product', 'name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'variant', 'quantity', 'unit_price', 'total_price', 'delivery_type', 'delivery_content', 'is_delivered', 'delivered_at']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['tracking_code', 'user', 'status', 'payment_method', 'total', 'paid_at', 'created_at']
    list_filter = ['status', 'payment_method']
    search_fields = ['tracking_code', 'user__username', 'user__email']
    ordering = ['-created_at']
    readonly_fields = ['tracking_code', 'subtotal', 'discount', 'tax', 'total', 'paid_at', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('user', 'tracking_code', 'status', 'payment_method')
        }),
        ('مبالغ', {
            'fields': ('subtotal', 'discount', 'tax', 'total')
        }),
        ('زمان‌ها', {
            'fields': ('paid_at', 'created_at', 'updated_at')
        }),
        ('اطلاعات پرداخت', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'variant', 'quantity', 'unit_price', 'total_price', 'is_delivered']
    list_filter = ['is_delivered', 'product__category']
    search_fields = ['order__tracking_code', 'product__name']
    readonly_fields = ['order', 'product', 'variant', 'quantity', 'unit_price', 'total_price', 'delivery_type', 'delivery_content', 'is_delivered', 'delivered_at']

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'variant', 'status', 'starts_at', 'expires_at', 'auto_renew', 'is_active']
    list_filter = ['status', 'product__category', 'auto_renew']
    search_fields = ['user__username', 'product__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اشتراک', {
            'fields': ('user', 'product', 'variant', 'order_item', 'status', 'auto_renew')
        }),
        ('زمان‌ها', {
            'fields': ('starts_at', 'expires_at')
        }),
        ('اطلاعات تحویل و متادیتا', {
            'fields': ('delivery_data', 'metadata'),
            'classes': ('collapse',)
        }),
        ('زمان‌های ثبت', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'blocked_balance', 'available_balance', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['updated_at']

    def available_balance(self, obj):
        return obj.available_balance
    available_balance.short_description = 'موجودی قابل استفاده'


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'type', 'status', 'amount', 'reference_id', 'created_at']
    list_filter = ['type', 'status']
    search_fields = ['wallet__user__username', 'reference_id', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'completed_at']
    fieldsets = (
        ('اطلاعات تراکنش', {
            'fields': ('wallet', 'type', 'status', 'amount')
        }),
        ('توضیحات و مرجع', {
            'fields': ('description', 'reference_id', 'metadata')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'completed_at')
        }),
    )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'discount_type', 'discount_value', 'max_discount_amount', 'min_order_amount', 'usage_limit', 'used_count', 'valid_from', 'valid_until', 'is_active']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code']
    ordering = ['-created_at']
    readonly_fields = ['used_count', 'created_at']
    filter_horizontal = ['applicable_categories', 'applicable_products']
    fieldsets = (
        ('اطلاعات کوپن', {
            'fields': ('code', 'name', 'description', 'discount_type', 'discount_value', 'max_discount_amount', 'min_order_amount')
        }),
        ('محدودیت‌ها', {
            'fields': ('usage_limit', 'usage_limit_per_user', 'used_count')
        }),
        ('اعتبار', {
            'fields': ('valid_from', 'valid_until', 'is_active')
        }),
        ('اعمال روی', {
            'fields': ('applicable_categories', 'applicable_products'),
            'classes': ('collapse',)
        }),
        ('زمان ایجاد', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'order', 'discount_amount', 'created_at']
    search_fields = ['coupon__code', 'user__username', 'order__tracking_code']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'full_name', 'phone', 'city', 'province', 'is_default']
    list_filter = ['is_default', 'province', 'city']
    search_fields = ['user__username', 'full_name', 'phone', 'city']
    ordering = ['-is_default', '-created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'title', 'is_read', 'created_at']
    list_filter = ['type', 'is_read']
    search_fields = ['user__username', 'title', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('اطلاعات سایت', {
            'fields': ('site_name', 'site_description', 'contact_email', 'contact_phone', 'address')
        }),
        ('برندینگ', {
            'fields': ('logo', 'favicon', 'primary_color', 'secondary_color')
        }),
        ('حالت تعمیرات', {
            'fields': ('maintenance_mode', 'maintenance_message')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False