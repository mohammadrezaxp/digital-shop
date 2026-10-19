from decimal import Decimal
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from shop.models import (
    Category,
    Coupon,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Subscription,
    WalletTransaction,
)


class AuthRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "alice", password="SecurePass!987"
        )
        self.user.two_factor_enabled = True
        self.user.two_factor_secret = pyotp.random_base32()
        self.user.backup_codes = ["BACKUP01"]
        self.user.save()

    def test_second_factor_endpoint_requires_password(self):
        response = self.client.post(
            "/api/auth/2fa/verify/",
            {
                "username": "alice",
                "code": pyotp.TOTP(self.user.two_factor_secret).now(),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access", response.data)

    def test_second_factor_endpoint_checks_password_and_lockout(self):
        data = {
            "username": "alice",
            "password": "wrong",
            "code": pyotp.TOTP(self.user.two_factor_secret).now(),
        }
        self.assertEqual(
            self.client.post("/api/auth/2fa/verify/", data).status_code, 401
        )
        self.user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.user.save()
        data["password"] = "SecurePass!987"
        self.assertEqual(
            self.client.post("/api/auth/2fa/verify/", data).status_code, 400
        )

    def test_second_factor_endpoint_accepts_complete_credentials(self):
        response = self.client.post(
            "/api/auth/2fa/verify/",
            {
                "username": "alice",
                "password": "SecurePass!987",
                "code": pyotp.TOTP(self.user.two_factor_secret).now(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_backup_code_can_only_be_consumed_once(self):
        self.assertTrue(self.user.consume_backup_code("BACKUP01"))
        stale = get_user_model().objects.get(pk=self.user.pk)
        stale.backup_codes = ["BACKUP01"]
        self.assertFalse(stale.consume_backup_code("BACKUP01"))

    def test_registration_rejects_weak_missing_and_mismatched_passwords(self):
        for payload in [
            {"username": "new"},
            {"username": "new", "password": "123"},
            {"username": "new", "password": "SecurePass!987", "password2": "different"},
        ]:
            response = self.client.post("/api/auth/register/", payload)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username="new").exists())

    def test_registration_hashes_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "new",
                "email": "new@example.org",
                "password": "SecurePass!987",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        self.assertTrue(
            get_user_model()
            .objects.get(username="new")
            .check_password("SecurePass!987")
        )

    def test_login_is_throttled(self):
        responses = [
            self.client.post(
                "/api/auth/login/", {"username": "missing", "password": "wrong"}
            ).status_code
            for _ in range(11)
        ]
        self.assertEqual(responses[-1], 429)


class CheckoutRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "buyer", password="SecurePass!987"
        )
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name="Test", slug="test")
        self.product = Product.objects.create(
            name="Example",
            slug="example",
            category=self.category,
            status=Product.Status.ACTIVE,
            price=100,
            stock=5,
        )
        self.user.wallet.balance = 1000
        self.user.wallet.save()

    def checkout(self, items=None, **kwargs):
        payload = dict(
            items=items or [{"product_id": self.product.pk, "quantity": 2}],
            payment_method="wallet",
        )
        payload.update(kwargs)
        return self.client.post("/api/orders/", payload, format="json")

    def test_bad_quantities_and_missing_product_are_validation_errors(self):
        for item in [
            {},
            {"product_id": self.product.pk, "quantity": -1},
            {"product_id": self.product.pk, "quantity": 0},
            {"product_id": self.product.pk, "quantity": "bad"},
        ]:
            self.assertEqual(self.checkout([item]).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_duplicate_lines_cannot_oversell(self):
        response = self.checkout([{"product_id": self.product.pk, "quantity": 3}] * 2)
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(Order.objects.exists())

    def test_wallet_payment_and_cancellation_refund_once(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.status, Order.Status.PAID)
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, 800)
        for _ in range(2):
            self.assertEqual(
                self.client.post(f"/api/orders/{order.pk}/cancel/").status_code, 200
            )
        self.user.wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, 1000)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(WalletTransaction.objects.filter(type="refund").count(), 1)

    def test_insufficient_wallet_rolls_back_inventory_and_order(self):
        self.user.wallet.balance = 10
        self.user.wallet.save()
        self.assertEqual(self.checkout().status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(Order.objects.exists())

    def test_order_status_cannot_be_forged_by_customer(self):
        response = self.checkout(payment_method="card")
        pk = response.data["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/orders/{pk}/", {"status": "paid"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(Order.objects.get(pk=pk).status, Order.Status.PENDING)

    def test_coupon_scope_and_serializer_match_models(self):
        coupon = Coupon.objects.create(
            code="TEST",
            name="Test",
            discount_type="percent",
            discount_value=10,
            valid_until=timezone.now() + timezone.timedelta(days=1),
        )
        other = Product.objects.create(
            name="Other",
            slug="other",
            category=self.category,
            price=50,
            stock=1,
            status="active",
        )
        coupon.applicable_products.add(other)
        self.assertEqual(self.checkout(coupon_code="TEST").status_code, 400)
        coupon.applicable_products.add(self.product)
        response = self.checkout(coupon_code="TEST")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["discount"]), 20)
        from shop.serializers import CouponSerializer

        self.assertEqual(CouponSerializer(coupon).data["discount_value"], "10")

    def test_variant_from_another_product_is_rejected(self):
        other = Product.objects.create(
            name="Other", slug="other", category=self.category, price=10
        )
        variant = ProductVariant.objects.create(
            product=other, name="v", sku="v", price=10, stock=5
        )
        self.assertEqual(
            self.checkout(
                [{"product_id": self.product.pk, "variant_id": variant.pk}]
            ).status_code,
            400,
        )

    def test_subscription_delivery_is_idempotent(self):
        response = self.checkout(payment_method="card")
        item = OrderItem.objects.get(order_id=response.data["id"])
        item.is_delivered = True
        item.save()
        item.save()
        self.assertEqual(Subscription.objects.filter(order_item=item).count(), 1)

    def test_periodic_task_expires_only_due_subscriptions(self):
        from shop.tasks import expire_subscriptions

        Subscription.objects.create(
            user=self.user,
            product=self.product,
            status="active",
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        Subscription.objects.create(
            user=self.user,
            product=self.product,
            status="active",
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        self.assertEqual(expire_subscriptions.run(), 1)
        self.assertEqual(expire_subscriptions.run(), 0)
        self.assertEqual(Subscription.objects.filter(status="active").count(), 1)

    def test_pending_wallet_transaction_applies_on_completion_once(self):
        tx = WalletTransaction.objects.create(
            wallet=self.user.wallet, type="deposit", amount=50
        )
        tx.status = "completed"
        tx.save()
        tx.save()
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, 1050)
        tx.amount = 100
        with self.assertRaises(ValidationError):
            tx.save()
