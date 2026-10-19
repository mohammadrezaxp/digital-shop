"""Transactional checkout, stock reservations, wallet payments and cancellation."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    Coupon,
    CouponUsage,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Wallet,
    WalletTransaction,
)


def prepare_lines(items, lock=False):
    products = Product.objects.all()
    variants = ProductVariant.objects.all()
    if lock:
        products, variants = products.select_for_update(), variants.select_for_update()
    products = {
        p.pk: p
        for p in products.filter(pk__in=[i["product_id"] for i in items]).order_by("pk")
    }
    variants = {
        v.pk: v
        for v in variants.filter(
            pk__in=[i["variant_id"] for i in items if i.get("variant_id")]
        ).order_by("pk")
    }
    lines, quantities = [], {}
    for item in items:
        product = products.get(item["product_id"])
        variant = variants.get(item.get("variant_id"))
        if product is None or product.status != Product.Status.ACTIVE:
            raise ValidationError("Product is not available.")
        if item.get("variant_id") and (
            variant is None or variant.product_id != product.pk or not variant.is_active
        ):
            raise ValidationError(
                "Variant does not belong to this product or is inactive."
            )
        stock_item = variant or product
        key = ("variant" if variant else "product", stock_item.pk)
        quantities[key] = quantities.get(key, 0) + item["quantity"]
        if quantities[key] > stock_item.stock:
            raise ValidationError("Insufficient stock.")
        price = stock_item.price
        if price < 0:
            raise ValidationError("Invalid product price.")
        lines.append(
            dict(
                product=product,
                variant=variant,
                quantity=item["quantity"],
                unit_price=price,
                total_price=price * item["quantity"],
            )
        )
    return lines


def coupon_discount(coupon, user, lines):
    subtotal = sum(line["total_price"] for line in lines)
    valid, message = coupon.is_valid(user, subtotal)
    if not valid:
        raise ValidationError(message)
    eligible = coupon.eligible_subtotal(lines)
    if eligible <= 0:
        raise ValidationError("Coupon does not apply to these products.")
    return coupon.calculate_discount(eligible)


@transaction.atomic
def pay_order(order):
    wallet, _ = Wallet.objects.get_or_create(user=order.user)
    if order.total > 0:
        try:
            WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransaction.Type.PURCHASE,
                status=WalletTransaction.Status.COMPLETED,
                amount=order.total,
                reference_id=order.tracking_code,
                completed_at=timezone.now(),
            )
        except ModelValidationError as exc:
            raise ValidationError(exc.messages)
    order.payment_method = Order.PaymentMethod.WALLET
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["payment_method", "status", "paid_at"])


@transaction.atomic
def create_order(user, data):
    # Serialize this user's checkouts/coupon usage and lock the inventory in stable order.
    type(user).objects.select_for_update().get(pk=user.pk)
    lines = prepare_lines(data["items"], lock=True)
    subtotal = sum(line["total_price"] for line in lines)
    coupon, discount = None, Decimal("0")
    if data.get("coupon_code"):
        try:
            coupon = Coupon.objects.select_for_update().get(
                code__iexact=data["coupon_code"]
            )
        except Coupon.DoesNotExist:
            raise ValidationError("Coupon not found.")
        discount = coupon_discount(coupon, user, lines)
    total = subtotal - discount
    if subtotal > 999999999999 or total < 0:
        raise ValidationError("Order total is outside the supported range.")
    order = Order.objects.create(
        user=user,
        payment_method=data["payment_method"],
        tracking_code=f"DS{uuid.uuid4().hex[:16].upper()}",
        subtotal=subtotal,
        discount=discount,
        tax=0,
        total=total,
    )
    for line in lines:
        stock_item = line["variant"] or line["product"]
        updates = {"stock": F("stock") - line["quantity"]}
        if line["variant"] is None:
            updates["sold_count"] = F("sold_count") + line["quantity"]
        if (
            not type(stock_item)
            .objects.filter(pk=stock_item.pk, stock__gte=line["quantity"])
            .update(**updates)
        ):
            raise ValidationError("Insufficient stock.")
        OrderItem.objects.create(order=order, **line)
    if coupon:
        # Conditional reservation also protects the total usage limit on SQLite.
        available = Coupon.objects.filter(pk=coupon.pk)
        if coupon.usage_limit:
            available = available.filter(used_count__lt=F("usage_limit"))
        if not available.update(used_count=F("used_count") + 1):
            raise ValidationError("Coupon usage limit reached.")
        CouponUsage.objects.create(
            coupon=coupon, user=user, order=order, discount_amount=discount
        )
    if order.payment_method == Order.PaymentMethod.WALLET:
        pay_order(order)
    return order


@transaction.atomic
def cancel_order(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.CANCELLED:
        return order
    if order.status not in [Order.Status.PENDING, Order.Status.PAID]:
        raise ValidationError("This order cannot be cancelled.")
    if order.items.filter(is_delivered=True).exists():
        raise ValidationError("Delivered orders require a manual refund review.")
    if (
        order.status == Order.Status.PAID
        and order.payment_method != Order.PaymentMethod.WALLET
    ):
        raise ValidationError("External payments require a confirmed provider refund.")
    for line in order.items.select_related("product", "variant").order_by(
        "product_id", "variant_id"
    ):
        stock_item = line.variant or line.product
        updates = {"stock": F("stock") + line.quantity}
        if line.variant is None:
            updates["sold_count"] = F("sold_count") - line.quantity
        type(stock_item).objects.filter(pk=stock_item.pk).update(**updates)
    if order.status == Order.Status.PAID and order.total > 0:
        WalletTransaction.objects.create(
            wallet=order.user.wallet,
            type=WalletTransaction.Type.REFUND,
            status=WalletTransaction.Status.COMPLETED,
            amount=order.total,
            reference_id=order.tracking_code,
            completed_at=timezone.now(),
        )
    for usage in order.coupon_usages.select_related("coupon"):
        Coupon.objects.filter(pk=usage.coupon_id, used_count__gt=0).update(
            used_count=F("used_count") - 1
        )
    order.coupon_usages.all().delete()
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order
