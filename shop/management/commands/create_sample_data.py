from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from shop.models import Category, Product, ProductVariant, Coupon, SiteSettings


class Command(BaseCommand):
    help = 'Create sample data for the digital shop'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create categories
        categories_data = [
            {'name': 'گیمینگ', 'slug': 'gaming', 'icon': 'sports_esports', 'order': 1, 'description': 'گیفت کارت‌ها و اشتراک‌های گیمینگ'},
            {'name': 'هوش مصنوعی', 'slug': 'ai', 'icon': 'psychology', 'order': 2, 'description': 'اشتراک‌های هوش مصنوعی و ابزارهای AI'},
            {'name': 'فیلترشکن', 'slug': 'vpn', 'icon': 'vpn_key', 'order': 3, 'description': 'اشتراک‌های VPN و پروکسی'},
            {'name': 'استریمینگ', 'slug': 'streaming', 'icon': 'movie', 'order': 4, 'description': 'اشتراک‌های فیلم، سریال و موزیک'},
            {'name': 'نرم‌افزار', 'slug': 'software', 'icon': 'desktop_mac', 'order': 5, 'description': 'لایسنس‌ها و اشتراک‌های نرم‌افزاری'},
        ]
        
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(slug=cat_data['slug'], defaults=cat_data)
            if created:
                self.stdout.write(f'  Created category: {cat.name}')
        
        # Get categories
        gaming = Category.objects.get(slug='gaming')
        ai = Category.objects.get(slug='ai')
        vpn = Category.objects.get(slug='vpn')
        streaming = Category.objects.get(slug='streaming')
        software = Category.objects.get(slug='software')
        
        # Create products
        products_data = [
            # Gaming
            {
                'name': 'Steam Gift Card', 'slug': 'steam-gift-card', 'category': gaming,
                'type': 'gift_card', 'status': 'active',
                'description': 'شارژ کیف پول استیم با کارت‌های گیفت رسمية برای خرید بازی‌های دلخواه.',
                'short_description': 'شارژ استیم با ریجن‌های مختلف',
                'price': Decimal('500000'), 'original_price': Decimal('550000'),
                'stock': 100, 'is_featured': True,
                'features': ['تحویل فوری', 'کد رسمی', 'بدون انقضا', 'پشتیبانی ۲۴/۷'],
                'metadata': {'region': 'Turkey/US/EU', 'denominations': [500000, 1000000, 2500000, 5000000]},
            },
            {
                'name': 'PlayStation Plus', 'slug': 'playstation-plus', 'category': gaming,
                'type': 'subscription', 'status': 'active',
                'description': 'اشتراک پلی‌استیشن پلاس برای بازی‌های آنلاین، بازی‌های ماهانه رایگان و تخفیفات انحصاری.',
                'short_description': 'اشتراک پلی‌استیشن برای بازی آنلاین',
                'price': Decimal('600000'), 'original_price': Decimal('650000'),
                'duration_days': 30, 'stock': 50, 'is_featured': True,
                'features': ['بازی‌های ماهانه رایگان', 'ملتی‌پلیر آنلاین', 'تخفیفات انحصاری', 'ذخیره ابری'],
                'metadata': {'region': 'Turkey/US', 'tier': 'Essential'},
            },
            {
                'name': 'Xbox Game Pass Ultimate', 'slug': 'xbox-game-pass', 'category': gaming,
                'type': 'subscription', 'status': 'active',
                'description': 'دسترسی به صدها بازی با کیفیت بالا برای کنسول، PC و Cloud Gaming.',
                'short_description': 'دسترسی به صدها بازی Xbox',
                'price': Decimal('450000'), 'original_price': Decimal('500000'),
                'duration_days': 30, 'stock': 50, 'is_featured': True,
                'features': ['بازی‌های روز اول', 'Cloud Gaming', 'EA Play शामिल', 'PC + Console'],
                'metadata': {'region': 'Turkey/Argentina', 'includes': ['EA Play', 'Cloud Gaming']},
            },
            # AI
            {
                'name': 'ChatGPT Plus', 'slug': 'chatgpt-plus', 'category': ai,
                'type': 'subscription', 'status': 'active',
                'description': 'دسترسی به GPT-4، سرعت پاسخ‌دهی بالاتر، و اولویت در دسترسی در اوج ترافیک.',
                'short_description': 'اشتراک پیشرفته ChatGPT با GPT-4',
                'price': Decimal('800000'), 'original_price': Decimal('900000'),
                'duration_days': 30, 'stock': 30, 'is_featured': True,
                'features': ['دسترسی به GPT-4o', 'سرعت بالاتر', 'اولویت در ترافیک بالا', 'ابزارهای پیشرفته'],
                'metadata': {'model': 'GPT-4o', 'billing': 'monthly'},
            },
            {
                'name': 'Claude Pro', 'slug': 'claude-pro', 'category': ai,
                'type': 'subscription', 'status': 'active',
                'description': 'اشتراک Claude Pro با دسترسی به Claude 3.5 Sonnet و Haiku، محدودیت ۵ برابر.',
                'short_description': 'اشتراک Claude AI پیشرفته',
                'price': Decimal('850000'), 'original_price': Decimal('950000'),
                'duration_days': 30, 'stock': 20, 'is_featured': True,
                'features': ['Claude 3.5 Sonnet', '۵ برابر محدودیت', 'اولویت دسترسی', 'پنجره متن ۲۰۰K'],
                'metadata': {'model': 'Claude 3.5 Sonnet', 'context_window': '200K'},
            },
            {
                'name': 'Midjourney Subscription', 'slug': 'midjourney', 'category': ai,
                'type': 'subscription', 'status': 'active',
                'description': 'سازماندهی پیشرفته تصویر با Midjourney، شامل GPU سریع و Commercial rights.',
                'short_description': 'تولید تصویر با هوش مصنوعی',
                'price': Decimal('1200000'), 'original_price': Decimal('1350000'),
                'duration_days': 30, 'stock': 15,
                'features': ['GPU سریع', 'Commercial Rights', 'Stealth Mode', 'اولویت رندر'],
                'metadata': {'plan': 'Standard', 'fast_hours': 15},
            },
            # VPN
            {
                'name': 'NordVPN', 'slug': 'nordvpn', 'category': vpn,
                'type': 'subscription', 'status': 'active',
                'description': 'VPN پرسرعت با ۵۴۰۰+ سرور در ۶۰ کشور، بدون ثبت لاگ، و امنیت سطح نظامی.',
                'short_description': 'VPN امن و پرسرعت NordVPN',
                'price': Decimal('350000'), 'original_price': Decimal('400000'),
                'duration_days': 365, 'stock': 100,
                'features': ['۵۴۰۰+ سرور', 'No-logs policy', '۶ دستگاه همزمان', 'Kill Switch'],
                'metadata': {'plan': '1 Year', 'devices': 6, 'servers': '5400+'},
            },
            {
                'name': 'ExpressVPN', 'slug': 'expressvpn', 'category': vpn,
                'type': 'subscription', 'status': 'active',
                'description': 'VPN با سرعت بالا، سرور در ۹۴ کشور، و رمزنگاری AES-256.',
                'short_description': 'VPN پرسرعت ExpressVPN',
                'price': Decimal('400000'), 'original_price': Decimal('450000'),
                'duration_days': 365, 'stock': 80,
                'features': ['۹۴ کشور', 'TrustedServer', 'Split Tunneling', '۸ دستگاه'],
                'metadata': {'plan': '1 Year', 'devices': 8, 'countries': 94},
            },
            # Streaming
            {
                'name': 'Netflix Premium', 'slug': 'netflix-premium', 'category': streaming,
                'type': 'subscription', 'status': 'active',
                'description': 'اشتراک نتفلیکس پرمیوم با کیفیت ۴K، ۴ دستگاه همزمان، و دانلود نامحدود.',
                'short_description': 'نتفلیکس ۴K با ۴ صفحه',
                'price': Decimal('750000'), 'original_price': Decimal('850000'),
                'duration_days': 30, 'stock': 40, 'is_featured': True,
                'features': ['کیفیت ۴K HDR', '۴ دستگاه همزمان', 'دانلود نامحدود', 'پروفایل‌های متعدد'],
                'metadata': {'plan': 'Premium', 'screens': 4, 'quality': '4K HDR'},
            },
            {
                'name': 'Spotify Premium', 'slug': 'spotify-premium', 'category': streaming,
                'type': 'subscription', 'status': 'active',
                'description': 'موزیک بدون تبلیغ، کیفیت بالا، دانلود آفلاین، و Spotify Connect.',
                'short_description': 'موزیک بدون تبلیغ با کیفیت بالا',
                'price': Decimal('250000'), 'original_price': Decimal('300000'),
                'duration_days': 30, 'stock': 100,
                'features': ['بدون تبلیغ', 'کیفیت ۳۲۰kbps', 'دانلود آفلاین', 'Spotify Connect'],
                'metadata': {'plan': 'Individual', 'quality': '320kbps'},
            },
            {
                'name': 'YouTube Premium', 'slug': 'youtube-premium', 'category': streaming,
                'type': 'subscription', 'status': 'active',
                'description': 'یوتیوب بدون تبلیغ، پخش در پس‌زمینه، یوتیوب موزیک، و دانلود ویدیو.',
                'short_description': 'یوتیوب بدون تبلیغ + یوتیوب موزیک',
                'price': Decimal('300000'), 'original_price': Decimal('350000'),
                'duration_days': 30, 'stock': 60, 'is_featured': True,
                'features': ['بدون تبلیغ', 'پخش پس‌زمینه', 'YouTube Music', 'دانلود ویدیو'],
                'metadata': {'plan': 'Individual', 'includes': 'YouTube Music'},
            },
            # Software
            {
                'name': 'Microsoft 365 Personal', 'slug': 'microsoft-365', 'category': software,
                'type': 'subscription', 'status': 'active',
                'description': 'سوییت آفیس کامل (Word, Excel, PowerPoint, Outlook) + ۱TB OneDrive.',
                'short_description': 'آفیس ۳۶۵ با ۱TB فضای ابری',
                'price': Decimal('450000'), 'original_price': Decimal('500000'),
                'duration_days': 365, 'stock': 50,
                'features': ['Office Apps', '۱TB OneDrive', '۶ دستگاه', 'امنیت پیشرفته'],
                'metadata': {'plan': 'Personal', 'storage': '1TB', 'devices': '5'},
            },
            {
                'name': 'Canva Pro', 'slug': 'canva-pro', 'category': software,
                'type': 'subscription', 'status': 'active',
                'description': 'طراحی گرافیک حرفه‌ای با قالب‌های نامحدود، برند کیت، و ۱۰۰GB فضای ابری.',
                'short_description': 'طراحی گرافیک حرفه‌ای با Canva Pro',
                'price': Decimal('400000'), 'original_price': Decimal('450000'),
                'duration_days': 365, 'stock': 30,
                'features': ['قالب‌های پرمیوم', 'Brand Kit', '۱۰۰GB فضای ابری', 'Background Remover'],
                'metadata': {'plan': 'Pro', 'storage': '100GB'},
            },
        ]
        
        for prod_data in products_data:
            variants_data = prod_data.pop('variants', None)
            product, created = Product.objects.get_or_create(slug=prod_data['slug'], defaults=prod_data)
            if created:
                self.stdout.write(f'  Created product: {product.name}')
                # Create default variant
                ProductVariant.objects.create(
                    product=product,
                    name='پیش‌فرض',
                    sku=f"{product.slug.upper()}-DEF",
                    price=product.price,
                    stock=product.stock,
                    is_active=True,
                )
        
        # Create coupons
        coupons_data = [
            {'code': 'WELCOME10', 'name': 'خوش‌آمدید ۱۰%', 'discount_type': 'percent', 'discount_value': Decimal('10'), 'max_discount_amount': Decimal('50000'), 'min_order_amount': Decimal('200000'), 'usage_limit': 100, 'valid_from': timezone.now(), 'valid_until': timezone.now() + timezone.timedelta(days=30), 'is_active': True},
            {'code': 'SAVE50K', 'name': 'تخفیف ۵۰ هزار تومان', 'discount_type': 'fixed', 'discount_value': Decimal('50000'), 'min_order_amount': Decimal('500000'), 'usage_limit': 50, 'valid_from': timezone.now(), 'valid_until': timezone.now() + timezone.timedelta(days=15), 'is_active': True},
            {'code': 'FIRSTORDER', 'name': 'اولین سفارش ۱۵%', 'discount_type': 'percent', 'discount_value': Decimal('15'), 'max_discount_amount': Decimal('100000'), 'usage_limit_per_user': 1, 'valid_from': timezone.now(), 'valid_until': timezone.now() + timezone.timedelta(days=60), 'is_active': True},
        ]
        
        for coupon_data in coupons_data:
            coupon, created = Coupon.objects.get_or_create(code=coupon_data['code'], defaults=coupon_data)
            if created:
                self.stdout.write(f'  Created coupon: {coupon.code}')
        
        # Create site settings
        settings, created = SiteSettings.objects.get_or_create(pk=1, defaults={
            'site_name': 'دیجیتال شاپ',
            'site_description': 'بهترین فروشگاه دیجیتال ایران با محصولات متنوع گیمینگ، هوش مصنوعی، VPN و استریمینگ',
            'contact_email': 'support@digitalshop.ir',
            'contact_phone': '۰۲۱-۱۲۳۴۵۶۷۸',
            'address': 'تهران، خیابان ولیعصر، پلاک ۱۲۳',
            'social_links': {
                'telegram': 'https://t.me/digitalshop',
                'instagram': 'https://instagram.com/digitalshop',
                'twitter': 'https://twitter.com/digitalshop',
            },
            'free_shipping_threshold': Decimal('1000000'),
        })
        if created:
            self.stdout.write('  Created site settings')
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))