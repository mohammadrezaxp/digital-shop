from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (Order, OrderItem, Subscription, User, Wallet,
                     WalletTransaction)


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Create wallet when user is created."""
    if created:
        Wallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=Order)
def update_order_totals(sender, instance, **kwargs):
    """Update order totals when order items change."""
    # This is handled in the view during order creation


@receiver(post_save, sender=OrderItem)
def handle_order_item_delivery(sender, instance, created, **kwargs):
    """Handle subscription creation when order item is marked as delivered."""
    if instance.is_delivered and not instance.delivered_at:
        from django.utils import timezone

        instance.delivered_at = timezone.now()
        instance.save(update_fields=["delivered_at"])

    # If this is a subscription product and marked delivered, create/update subscription
    if instance.is_delivered and instance.product.type == "subscription":
        Subscription.objects.get_or_create(
            order_item=instance,
            defaults={
                "user": instance.order.user,
                "product": instance.product,
                "variant": instance.variant,
                "status": Subscription.Status.ACTIVE,
                "started_at": timezone.now(),
                "expires_at": timezone.now()
                + timezone.timedelta(days=instance.product.duration_days or 30),
                "delivery_data": instance.delivery_data,
            },
        )


@receiver(post_save, sender=WalletTransaction)
def update_wallet_balance(sender, instance, created, **kwargs):
    """Update wallet balance when transaction is completed."""
    if instance.status == WalletTransaction.Status.COMPLETED and created:
        wallet = instance.wallet
        if instance.type in [
            WalletTransaction.Type.DEPOSIT,
            WalletTransaction.Type.REFUND,
            WalletTransaction.Type.REWARD,
            WalletTransaction.Type.BONUS,
        ]:
            wallet.balance += instance.amount
        elif instance.type in [
            WalletTransaction.Type.WITHDRAW,
            WalletTransaction.Type.PAYMENT,
        ]:
            wallet.balance -= instance.amount
        wallet.save(update_fields=["balance", "updated_at"])


@receiver(post_delete, sender=OrderItem)
def restore_stock_on_delete(sender, instance, **kwargs):
    """Restore product stock when order item is deleted (e.g., order cancelled)."""
    if instance.variant:
        instance.variant.stock += instance.quantity
        instance.variant.save(update_fields=["stock"])
    else:
        instance.product.stock += instance.quantity
        instance.product.sold_count -= instance.quantity
        instance.product.save(update_fields=["stock", "sold_count"])
