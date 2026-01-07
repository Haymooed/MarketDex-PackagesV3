from django.apps import AppConfig


class MerchantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "merchant"
    verbose_name = "merchant"
    # This attribute is used by BallsDex to load the discord.py extension.
    dpy_package = "merchant.merchant"
