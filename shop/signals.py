"""Model lifecycle hooks; wallet mutations run inside WalletTransaction.save's atomic block."""

from django.core.exceptions import ValidationError
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import OrderItem, Subscription, User, Wallet, WalletTransaction


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=OrderItem)
def handle_order_item_delivery(sender, instance, **kwargs):
    if not instance.is_delivered:
        return
    if not instance.delivered_at:
        OrderItem.objects.filter(pk=instance.pk).update(delivered_at=timezone.now())
    if instance.product.type == "subscription":
        Subscription.objects.get_or_create(
            order_item=instance,
            defaults={
                "user": instance.order.user,
                "product": instance.product,
                "variant": instance.variant,
                "status": Subscription.Status.ACTIVE,
                "expires_at": timezone.now()
                + timezone.timedelta(days=instance.product.duration_days or 30),
            },
        )


@receiver(post_save, sender=WalletTransaction)
def update_wallet_balance(sender, instance, **kwargs):
    if not getattr(instance, "_apply_balance", False):
        return
    wallet = Wallet.objects.select_for_update().get(pk=instance.wallet_id)
    credit = instance.type in [
        WalletTransaction.Type.DEPOSIT,
        WalletTransaction.Type.REFUND,
        WalletTransaction.Type.COMMISSION,
    ]
    if credit:
        if wallet.balance + instance.amount > 999999999999:
            raise ValidationError("Wallet balance limit exceeded.")
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=F("balance") + instance.amount
        )
    elif not Wallet.objects.filter(
        pk=wallet.pk, balance__gte=F("blocked_balance") + instance.amount
    ).update(balance=F("balance") - instance.amount):
        raise ValidationError("Insufficient available wallet balance.")
