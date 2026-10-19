from celery import shared_task
from django.utils import timezone

from .models import Subscription


@shared_task
def expire_subscriptions():
    return Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, expires_at__lte=timezone.now()
    ).update(status=Subscription.Status.EXPIRED)
