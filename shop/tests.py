"""Tests for shop app - security, auth, validators, serializers."""
import pyotp
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from shop.models import (
    Category, Product, ProductVariant, Order, OrderItem,
    Subscription, Wallet, WalletTransaction, Coupon, CouponUsage,
    Address, Notification, SiteSettings, LoginAttempt
)
from shop.validators import (
    SpecialCharacterValidator, NoCommonPatternsValidator, NoPersonalInfoValidator
)
from django.core.exceptions import ValidationError

User = get_user_model()


class ValidatorTests(TestCase):
    """Password validator tests."""

    def test_special_char_validator(self):
        v = SpecialCharacterValidator()
        v.validate('Password123!', None)  # valid
        with self.assertRaises(ValidationError):
            v.validate('Password123', None)  # no special char

    def test_no_common_patterns_validator(self):
        v = NoCommonPatternsValidator()
        v.validate('SecurePass!987', None)  # valid
        with self.assertRaises(ValidationError):
            v.validate('password123!', None)  # common word
        with self.assertRaises(ValidationError):
            v.validate('aaaaaaaa!', None)  # repeated chars
        with self.assertRaises(ValidationError):
            v.validate('Pass123!999', None)  # 3 repeated digits

    def test_no_personal_info_validator(self):
        v = NoPersonalInfoValidator()
        user = User(username='john', email='john@example.com', first_name='John', last_name='Doe')
        v.validate('SecurePass!987', user)  # valid
        with self.assertRaises(ValidationError):
            v.validate('John123!', user)  # contains first name
        with self.assertRaises(ValidationError):
            v.validate('Doe123!', user)  # contains last name
        with self.assertRaises(ValidationError):
            v.validate('john@example123!', user)  # contains email local part


class AuthSecurityTests(TestCase):
    """Authentication and security flow tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass!987'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='AdminPass!987'
        )

    def test_login_success(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'WrongPass!987'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_lockout_after_5_failures(self):
        for _ in range(5):
            self.client.post('/api/auth/login/', {
                'username': 'testuser',
                'password': 'WrongPass!987'
            }, format='json')

        user = User.objects.get(username='testuser')
        self.assertTrue(user.is_locked)
        self.assertEqual(user.failed_login_attempts, 5)

        # Correct password but locked
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['details']['code'][0], 'account_locked')

    def test_2fa_setup_and_verify(self):
        # First login to get tokens
        login = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

        response = self.client.get('/api/auth/2fa/setup/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        secret = response.data['secret']

        # Enable with valid TOTP
        code = pyotp.TOTP(secret).now()
        response = self.client.post('/api/auth/2fa/setup/', {'code': code}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('backup_codes', response.data)

        # Verify 2FA login flow
        self.client.credentials()  # clear auth
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['details']['code'][0], 'two_factor_required')

        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987',
            'two_factor_code': pyotp.TOTP(secret).now()
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_2fa_disable(self):
        self._enable_2fa_for_user(self.user)
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/auth/2fa/disable/', {
            'code': self.user.backup_codes[0]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)
        self.assertEqual(self.user.two_factor_secret, '')
        self.assertEqual(self.user.backup_codes, [])

    def _enable_2fa_for_user(self, user):
        """Helper to enable 2FA for a user."""
        secret = pyotp.random_base32()
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        user.backup_codes = [f'BC{i:04d}' for i in range(8)]
        user.save()

    def test_login_attempt_logging(self):
        self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'WrongPass!987'
        }, format='json')

        attempts = LoginAttempt.objects.filter(username='testuser')
        self.assertEqual(attempts.count(), 1)
        self.assertEqual(attempts.first().status, LoginAttempt.Status.FAILED)

        self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')

        attempts = LoginAttempt.objects.filter(username='testuser')
        self.assertEqual(attempts.filter(status=LoginAttempt.Status.SUCCESS).count(), 1)


class SerializerTests(TestCase):
    """Serializer validation tests."""

    def setUp(self):
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            category=self.category,
            status=Product.Status.ACTIVE,
            price=100000,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Test Variant',
            sku='TEST-001',
            price=100000,
            stock=10,
            is_active=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass!987'
        )
        # Wallet created by signal
        self.wallet = self.user.wallet

    def test_product_serializer(self):
        from shop.serializers import ProductDetailSerializer
        serializer = ProductDetailSerializer(self.product)
        data = serializer.data
        self.assertEqual(data['name'], 'Test Product')
        self.assertIn('variants', data)

    def test_order_create_serializer(self):
        from shop.serializers import OrderCreateSerializer
        serializer = OrderCreateSerializer(data={
            'items': [{'variant': self.variant.id, 'quantity': 1}],
            'payment_method': 'wallet'
        })
        self.assertTrue(serializer.is_valid())

    def test_coupon_validate_serializer(self):
        coupon = Coupon.objects.create(
            code='TEST10',
            name='Test 10%',
            discount_type=Coupon.DiscountType.PERCENT,
            discount_value=10,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )
        from shop.serializers import CouponValidateSerializer
        serializer = CouponValidateSerializer(data={
            'code': 'TEST10',
            'cart_total': 100000,
            'items': [{'product_id': self.product.id, 'quantity': 1}]
        })
        self.assertTrue(serializer.is_valid())


class ModelTests(TestCase):
    """Model method and property tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass!987'
        )
        # Wallet created by signal
        self.wallet = self.user.wallet
        self.wallet.balance = 1000000
        self.wallet.blocked_balance = 50000
        self.wallet.save()

    def test_wallet_available_balance(self):
        self.assertEqual(self.wallet.available_balance, 950000)

    def test_user_locked_property(self):
        self.assertFalse(self.user.is_locked)
        self.user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.user.save()
        self.assertTrue(self.user.is_locked)
        self.user.locked_until = timezone.now() - timezone.timedelta(minutes=1)
        self.user.save()
        self.assertFalse(self.user.is_locked)

    def test_coupon_is_valid(self):
        coupon = Coupon.objects.create(
            code='VALID10',
            name='Valid 10%',
            discount_type=Coupon.DiscountType.PERCENT,
            discount_value=10,
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )
        valid, msg = coupon.is_valid(self.user, 100000)
        self.assertTrue(valid)

        expired = Coupon.objects.create(
            code='EXPIRED10',
            name='Expired 10%',
            discount_type=Coupon.DiscountType.PERCENT,
            discount_value=10,
            valid_from=timezone.now() - timezone.timedelta(days=60),
            valid_until=timezone.now() - timezone.timedelta(days=1),
            is_active=True
        )
        valid, msg = expired.is_valid(self.user, 100000)
        self.assertFalse(valid)


class APITests(TestCase):
    """General API endpoint tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass!987'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='AdminPass!987'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            category=self.category,
            status=Product.Status.ACTIVE,
            price=100000,
        )
        ProductVariant.objects.create(
            product=self.product,
            name='Variant 1',
            sku='VAR-001',
            price=50000,
            stock=10,
            is_active=True
        )

    def test_public_endpoints(self):
        """Public endpoints accessible without auth."""
        endpoints = ['/api/products/', '/api/categories/', '/api/settings/']
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f'Failed: {url}')

    def test_protected_endpoints_require_auth(self):
        """Protected endpoints require authentication."""
        endpoints = [
            '/api/dashboard/', '/api/wallet/', '/api/orders/',
            '/api/subscriptions/', '/api/addresses/', '/api/notifications/'
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, f'Should be 401: {url}')

    def test_protected_endpoints_with_auth(self):
        """Protected endpoints work with valid token."""
        login = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePass!987'
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

        endpoints = [
            '/api/dashboard/', '/api/wallet/', '/api/orders/',
            '/api/subscriptions/', '/api/addresses/', '/api/notifications/'
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f'Failed: {url}')

    def test_register_endpoint(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'SecurePass!987',
            'password2': 'SecurePass!987'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())