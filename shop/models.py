from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Extended user model with profile fields."""

    phone = models.CharField(_("شماره تلفن"), max_length=15, blank=True)
    avatar = models.ImageField(_("آواتار"), upload_to="avatars/", blank=True, null=True)
    email_verified = models.BooleanField(_("ایمیل تایید شده"), default=False)
    phone_verified = models.BooleanField(_("تلفن تایید شده"), default=False)
    two_factor_enabled = models.BooleanField(_("احراز هویت دو مرحله‌ای"), default=False)
    two_factor_secret = models.CharField(
        _("مخفی دو مرحله‌ای"), max_length=32, blank=True
    )
    backup_codes = models.JSONField(_("کدهای پشتیبان 2FA"), default=list, blank=True)
    last_login_ip = models.GenericIPAddressField(
        _("آخرین IP ورود"), null=True, blank=True
    )
    failed_login_attempts = models.PositiveIntegerField(
        _("تلاش‌های ناموفق ورود"), default=0
    )
    locked_until = models.DateTimeField(_("قفل تا"), null=True, blank=True)
    password_changed_at = models.DateTimeField(_("تاریخ تغییر رمز"), auto_now_add=True)
    created_at = models.DateTimeField(_("تاریخ ثبت نام"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("کاربر")
        verbose_name_plural = _("کاربران")
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["locked_until"]),
        ]

    def __str__(self):
        return self.username or self.email

    @property
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def record_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def record_successful_login(self, ip=None):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_ip = ip
        self.save(
            update_fields=["failed_login_attempts", "locked_until", "last_login_ip"]
        )


class LoginAttempt(models.Model):
    """Track login attempts for security auditing and brute-force detection."""

    class Status(models.TextChoices):
        SUCCESS = "success", _("موفق")
        FAILED = "failed", _("ناموفق")
        BLOCKED = "blocked", _("مسدود شده")
        LOCKED = "locked", _("حساب قفل شده")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_attempts",
        verbose_name=_("کاربر"),
        null=True,
        blank=True,
    )
    username = models.CharField(_("نام کاربری"), max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(_("آدرس IP"))
    user_agent = models.TextField(_("User Agent"), blank=True)
    status = models.CharField(_("وضعیت"), max_length=10, choices=Status.choices)
    failure_reason = models.CharField(_("دلیل شکست"), max_length=100, blank=True)
    created_at = models.DateTimeField(_("تاریخ تلاش"), auto_now_add=True)

    class Meta:
        verbose_name = _("تلاش ورود")
        verbose_name_plural = _("تلاش‌های ورود")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["username", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.username} - {self.ip_address} - {self.get_status_display()}"


class Category(models.Model):
    """Product categories (Gaming, AI, VPN, Apps, etc.)"""

    name = models.CharField(_("نام دسته‌بندی"), max_length=100, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=100, unique=True)
    icon = models.CharField(
        _("آیکون"), max_length=50, blank=True, help_text=_("Material Symbols name")
    )
    description = models.TextField(_("توضیحات"), blank=True)
    order = models.PositiveIntegerField(_("ترتیب نمایش"), default=0)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("دسته‌بندی")
        verbose_name_plural = _("دسته‌بندی‌ها")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """Digital products/services for sale."""

    class Type(models.TextChoices):
        GIFT_CARD = "gift_card", _("گیفت کارت")
        SUBSCRIPTION = "subscription", _("اشتراک")
        ACCOUNT = "account", _("اکانت")
        LICENSE = "license", _("لایسنس")

    class Status(models.TextChoices):
        DRAFT = "draft", _("پیش‌نویس")
        ACTIVE = "active", _("فعال")
        OUT_OF_STOCK = "out_of_stock", _("ناموجود")
        ARCHIVED = "archived", _("بایگانی")

    name = models.CharField(_("نام محصول"), max_length=200)
    slug = models.SlugField(_("اسلاگ"), max_length=200, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("دسته‌بندی"),
    )
    type = models.CharField(
        _("نوع محصول"), max_length=20, choices=Type.choices, default=Type.SUBSCRIPTION
    )
    status = models.CharField(
        _("وضعیت"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    description = models.TextField(_("توضیحات کامل"))
    short_description = models.TextField(_("توضیحات کوتاه"), max_length=500, blank=True)
    logo = models.ImageField(
        _("لوگو"), upload_to="products/logos/", blank=True, null=True
    )
    thumbnail = models.ImageField(
        _("تصویر کاور"), upload_to="products/thumbnails/", blank=True, null=True
    )
    price = models.DecimalField(_("قیمت (تومان)"), max_digits=12, decimal_places=0)
    original_price = models.DecimalField(
        _("قیمت اصلی (تومان)"), max_digits=12, decimal_places=0, blank=True, null=True
    )
    duration_days = models.PositiveIntegerField(
        _("مدت اعتبار (روز)"), blank=True, null=True, help_text=_("برای اشتراک‌ها")
    )
    features = models.JSONField(
        _("ویژگی‌ها"),
        default=list,
        blank=True,
        help_text=_("لیست ویژگی‌ها به صورت JSON"),
    )
    metadata = models.JSONField(
        _("اطلاعات تکمیلی"),
        default=dict,
        blank=True,
        help_text=_("اطلاعات اضافه مثل ریجن، نسخه، و غیره"),
    )
    stock = models.PositiveIntegerField(_("موجودی"), default=0)
    sold_count = models.PositiveIntegerField(_("تعداد فروش"), default=0)
    is_featured = models.BooleanField(_("محصول ویژه"), default=False)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["status", "is_featured"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return int((self.original_price - self.price) / self.original_price * 100)
        return 0

    @property
    def is_in_stock(self):
        return self.status == self.Status.ACTIVE and self.stock > 0


class ProductVariant(models.Model):
    """Product variants (e.g., different regions, durations, tiers)."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name=_("محصول"),
    )
    name = models.CharField(_("نام تنوع"), max_length=100)
    sku = models.CharField(_("SKU"), max_length=50, unique=True)
    price = models.DecimalField(_("قیمت (تومان)"), max_digits=12, decimal_places=0)
    stock = models.PositiveIntegerField(_("موجودی"), default=0)
    metadata = models.JSONField(
        _("اطلاعات تکمیلی"),
        default=dict,
        blank=True,
        help_text=_("مثل ریجن، نسخه، و غیره"),
    )
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("تنوع محصول")
        verbose_name_plural = _("تنوع‌های محصول")
        ordering = ["product", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class Order(models.Model):
    """Customer orders."""

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار پرداخت")
        PAID = "paid", _("پرداخت شده")
        PROCESSING = "processing", _("در حال پردازش")
        COMPLETED = "completed", _("تکمیل شده")
        CANCELLED = "cancelled", _("لغو شده")
        REFUNDED = "refunded", _("استرداد شده")
        FAILED = "failed", _("ناموفق")

    class PaymentMethod(models.TextChoices):
        WALLET = "wallet", _("کیف پول")
        CARD = "card", _("کارت بانکی")
        GATEWAY = "gateway", _("درگاه پرداخت")

    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="orders", verbose_name=_("کاربر")
    )
    status = models.CharField(
        _("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING
    )
    payment_method = models.CharField(
        _("روش پرداخت"), max_length=20, choices=PaymentMethod.choices
    )
    tracking_code = models.CharField(_("کد پیگیری"), max_length=20, unique=True)
    subtotal = models.DecimalField(_("مجموع جزئی"), max_digits=12, decimal_places=0)
    discount = models.DecimalField(
        _("تخفیف"), max_digits=12, decimal_places=0, default=0
    )
    tax = models.DecimalField(_("مالیات"), max_digits=12, decimal_places=0, default=0)
    total = models.DecimalField(_("مجموع"), max_digits=12, decimal_places=0)
    paid_at = models.DateTimeField(_("تاریخ پرداخت"), null=True, blank=True)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("سفارش")
        verbose_name_plural = _("سفارش‌ها")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tracking_code"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.tracking_code} - {self.user.username}"


class OrderItem(models.Model):
    """Individual items within an order."""

    class DeliveryType(models.TextChoices):
        CODE = "code", _("کد")
        FILE = "file", _("فایل")
        ACCOUNT = "account", _("اکانت")
        LINK = "link", _("لینک")
        MANUAL = "manual", _("دستی")

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name=_("سفارش")
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name=_("محصول"),
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name=_("تنوع"),
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(_("تعداد"), default=1)
    unit_price = models.DecimalField(_("قیمت واحد"), max_digits=12, decimal_places=0)
    total_price = models.DecimalField(_("قیمت کل"), max_digits=12, decimal_places=0)
    delivery_type = models.CharField(
        _("نوع تحویل"),
        max_length=10,
        choices=DeliveryType.choices,
        default=DeliveryType.CODE,
    )
    delivery_content = models.JSONField(
        _("محتویات تحویل"),
        default=dict,
        blank=True,
        help_text=_("کدها، فایل‌ها، اطلاعات اکانت و غیره"),
    )
    is_delivered = models.BooleanField(_("تحویل داده شده"), default=False)
    delivered_at = models.DateTimeField(_("تاریخ تحویل"), null=True, blank=True)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("مورد سفارش")
        verbose_name_plural = _("موارد سفارش")

    def __str__(self):
        return f"{self.order.tracking_code} - {self.product.name}"


class Subscription(models.Model):
    """User subscriptions for recurring products."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("فعال")
        EXPIRED = "expired", _("منقضی شده")
        CANCELLED = "cancelled", _("لغو شده")
        PENDING = "pending", _("در انتظار فعال‌سازی")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("کاربر"),
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("محصول"),
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("تنوع"),
        null=True,
        blank=True,
    )
    status = models.CharField(
        _("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING
    )
    starts_at = models.DateTimeField(_("تاریخ شروع"), auto_now_add=True)
    expires_at = models.DateTimeField(_("تاریخ انقضا"))
    auto_renew = models.BooleanField(_("تمدید خودکار"), default=False)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("اشتراک")
        verbose_name_plural = _("اشتراک‌ها")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()

    @property
    def days_remaining(self):
        if self.expires_at > timezone.now():
            return (self.expires_at - timezone.now()).days
        return 0


class Wallet(models.Model):
    """User wallet for balance management."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="wallet", verbose_name=_("کاربر")
    )
    balance = models.DecimalField(
        _("موجودی"), max_digits=12, decimal_places=0, default=0
    )
    blocked_balance = models.DecimalField(
        _("موجودی مسدود"), max_digits=12, decimal_places=0, default=0
    )
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("کیف پول")
        verbose_name_plural = _("کیف پول‌ها")

    def __str__(self):
        return f"{self.user.username} - {self.balance:,} تومان"

    @property
    def available_balance(self):
        return self.balance - self.blocked_balance


class WalletTransaction(models.Model):
    """Wallet transactions."""

    class Type(models.TextChoices):
        DEPOSIT = "deposit", _("واریز")
        WITHDRAWAL = "withdrawal", _("برداشت")
        PURCHASE = "purchase", _("خرید")
        REFUND = "refund", _("استرداد")
        COMMISSION = "commission", _("کمیسیون")

    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار")
        COMPLETED = "completed", _("تکمیل شده")
        FAILED = "failed", _("ناموفق")
        CANCELLED = "cancelled", _("لغو شده")

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name=_("کیف پول"),
    )
    type = models.CharField(_("نوع تراکنش"), max_length=20, choices=Type.choices)
    status = models.CharField(
        _("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING
    )
    amount = models.DecimalField(_("مبلغ"), max_digits=12, decimal_places=0)
    description = models.TextField(_("توضیحات"), blank=True)
    reference_id = models.CharField(
        _("شناسه مرجع"),
        max_length=100,
        blank=True,
        help_text=_("شناسه سفارش، پرداخت، و غیره"),
    )
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    completed_at = models.DateTimeField(_("تاریخ تکمیل"), null=True, blank=True)

    class Meta:
        verbose_name = _("تراکنش کیف پول")
        verbose_name_plural = _("تراکنش‌های کیف پول")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "type"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["reference_id"]),
        ]

    def __str__(self):
        return (
            f"{self.wallet.user.username} - {self.get_type_display()} - {self.amount:,}"
        )


class Coupon(models.Model):
    """Discount coupons."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", _("درصدی")
        FIXED = "fixed", _("مبلغ ثابت")

    code = models.CharField(_("کد کوپن"), max_length=50, unique=True)
    name = models.CharField(_("نام کوپن"), max_length=100)
    description = models.TextField(_("توضیحات"), blank=True)
    discount_type = models.CharField(
        _("نوع تخفیف"), max_length=10, choices=DiscountType.choices
    )
    discount_value = models.DecimalField(
        _("مقدار تخفیف"), max_digits=10, decimal_places=0
    )
    min_order_amount = models.DecimalField(
        _("حداقل مبلغ سفارش"), max_digits=12, decimal_places=0, default=0
    )
    max_discount_amount = models.DecimalField(
        _("حداکثر تخفیف"), max_digits=12, decimal_places=0, blank=True, null=True
    )
    usage_limit = models.PositiveIntegerField(
        _("محدودیت استفاده کل"), default=0, help_text=_("0 = نامحدود")
    )
    usage_limit_per_user = models.PositiveIntegerField(
        _("محدودیت استفاده هر کاربر"), default=1
    )
    used_count = models.PositiveIntegerField(_("تعداد استفاده شده"), default=0)
    valid_from = models.DateTimeField(_("اعتبار از"), default=timezone.now)
    valid_until = models.DateTimeField(_("اعتبار تا"))
    is_active = models.BooleanField(_("فعال"), default=True)
    applicable_categories = models.ManyToManyField(
        Category,
        related_name="coupons",
        blank=True,
        verbose_name=_("دسته‌بندی‌های شامل"),
    )
    applicable_products = models.ManyToManyField(
        Product, related_name="coupons", blank=True, verbose_name=_("محصولات شامل")
    )
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("کوپن")
        verbose_name_plural = _("کوپن‌ها")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_valid(self, user, cart_total):
        now = timezone.now()
        if not self.is_active:
            return False, "کوپن غیرفعال است"
        if now < self.valid_from or now > self.valid_until:
            return False, "کوپن منقضی شده یا هنوز معتبر نیست"
        if self.usage_limit > 0 and self.used_count >= self.usage_limit:
            return False, "محدودیت استفاده از کوپن تمام شده"
        if cart_total < self.min_order_amount:
            return False, f"حداقل مبلغ سفارش {self.min_order_amount:,} تومان است"
        if (
            CouponUsage.objects.filter(coupon=self, user=user).count()
            >= self.usage_limit_per_user
        ):
            return False, "شما از حد استفاده از این کوپن گذشته‌اید"
        if (
            self.applicable_categories.exists()
            and not self.applicable_categories.filter(products__in=[]).exists()
        ):
            pass  # Skip category check if no categories specified
        if (
            self.applicable_products.exists()
            and not self.applicable_products.filter(id__in=[]).exists()
        ):
            pass  # Skip product check if no products specified
        return True, ""

    def calculate_discount(self, amount):
        if self.discount_type == self.DiscountType.PERCENT:
            discount = amount * self.discount_value / 100
            if self.max_discount_amount and discount > self.max_discount_amount:
                return self.max_discount_amount
            return discount
        return min(self.discount_value, amount)


class CouponUsage(models.Model):
    """Track coupon usage per user."""

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name="usages", verbose_name=_("کوپن")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        verbose_name=_("کاربر"),
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        verbose_name=_("سفارش"),
    )
    discount_amount = models.DecimalField(
        _("مبلغ تخفیف"), max_digits=12, decimal_places=0
    )
    created_at = models.DateTimeField(_("تاریخ استفاده"), auto_now_add=True)

    class Meta:
        verbose_name = _("استفاده از کوپن")
        verbose_name_plural = _("استفاده‌های کوپن")
        unique_together = [["coupon", "user", "order"]]

    def __str__(self):
        return f"{self.coupon.code} - {self.user.username}"


class Address(models.Model):
    """User addresses for physical deliveries."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name=_("کاربر"),
    )
    title = models.CharField(_("عنوان"), max_length=100)
    full_name = models.CharField(_("نام کامل"), max_length=100)
    phone = models.CharField(_("شماره تماس"), max_length=15)
    province = models.CharField(_("استان"), max_length=50)
    city = models.CharField(_("شهر"), max_length=50)
    address = models.TextField(_("آدرس کامل"))
    postal_code = models.CharField(_("کد پستی"), max_length=10)
    is_default = models.BooleanField(_("پیش‌فرض"), default=False)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("آدرس")
        verbose_name_plural = _("آدرس‌ها")
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class Notification(models.Model):
    """User notifications."""

    class Type(models.TextChoices):
        ORDER = "order", _("سفارش")
        PAYMENT = "payment", _("پرداخت")
        SUBSCRIPTION = "subscription", _("اشتراک")
        WALLET = "wallet", _("کیف پول")
        SYSTEM = "system", _("سیستم")
        PROMOTION = "promotion", _("تبلیغات")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("کاربر"),
    )
    type = models.CharField(_("نوع"), max_length=20, choices=Type.choices)
    title = models.CharField(_("عنوان"), max_length=200)
    message = models.TextField(_("پیام"))
    is_read = models.BooleanField(_("خوانده شده"), default=False)
    data = models.JSONField(_("داده‌های اضافه"), default=dict, blank=True)
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("اعلان")
        verbose_name_plural = _("اعلان‌ها")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class SiteSettings(models.Model):
    """Global site settings (singleton)."""

    site_name = models.CharField(_("نام سایت"), max_length=100, default="Digital Shop")
    site_description = models.TextField(_("توضیحات سایت"), blank=True)
    contact_email = models.EmailField(_("ایمیل تماس"), blank=True)
    contact_phone = models.CharField(_("تلفن تماس"), max_length=20, blank=True)
    address = models.TextField(_("آدرس"), blank=True)
    logo = models.ImageField(_("لوگو"), upload_to="site/", blank=True, null=True)
    favicon = models.ImageField(_("فاوآیکون"), upload_to="site/", blank=True, null=True)
    primary_color = models.CharField(_("رنگ اصلی"), max_length=7, default="#2563eb")
    secondary_color = models.CharField(_("رنگ ثانویه"), max_length=7, default="#06b6d4")
    maintenance_mode = models.BooleanField(_("حالت تعمیرات"), default=False)
    maintenance_message = models.TextField(_("پیام تعمیرات"), blank=True)
    social_links = models.JSONField(_("شبکه‌های اجتماعی"), default=dict, blank=True)
    free_shipping_threshold = models.DecimalField(
        _("آستانه ارسال رایگان"), max_digits=12, decimal_places=0, default=1000000
    )
    created_at = models.DateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True)

    class Meta:
        verbose_name = _("تنظیمات سایت")
        verbose_name_plural = _("تنظیمات سایت")

    def __str__(self):
        return "Site Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
