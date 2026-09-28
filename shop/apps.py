from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"
    verbose_name = "فروشگاه دیجیتال"

    def ready(self):
        import shop.signals  # noqa
