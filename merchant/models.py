from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.db import models
from django.utils import timezone

from bd_models.models import Ball, BallInstance, Player, Special


class MerchantSettings(models.Model):
    """
    Singleton-like model to hold merchant configuration managed from the admin panel.
    """

    singleton_id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=True, help_text="Disable to hide the merchant entirely.")
    rotation_minutes = models.PositiveIntegerField(
        default=24 * 60, help_text="How long a rotation lasts, in minutes. Default: 24h."
    )
    items_per_rotation = models.PositiveSmallIntegerField(
        default=3, help_text="How many offers are selected for each rotation."
    )
    purchase_cooldown_seconds = models.PositiveIntegerField(
        default=3600, help_text="Cooldown between purchases for the same player, in seconds."
    )
    last_rotation_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Merchant settings"

    @classmethod
    async def load(cls) -> "MerchantSettings":
        """
        Retrieve the singleton settings instance, creating it with defaults if missing.
        """
        instance, _ = await cls.objects.aget_or_create(pk=1)
        return instance

    @property
    def rotation_delta(self) -> timedelta:
        return timedelta(minutes=self.rotation_minutes)

    @property
    def purchase_cooldown(self) -> timedelta:
        return timedelta(seconds=self.purchase_cooldown_seconds)


class MerchantItem(models.Model):
    """
    Configurable item pool entry for the merchant rotations.
    """

    display_name = models.CharField(
        max_length=64, blank=True, help_text="Optional override name. Defaults to the ball name."
    )
    description = models.CharField(max_length=200, blank=True)
    price = models.PositiveBigIntegerField(default=1000, help_text="Price charged to the player.")
    weight = models.PositiveIntegerField(default=1, help_text="Relative selection weight for rotations.")
    enabled = models.BooleanField(default=True)
    ball = models.ForeignKey(Ball, on_delete=models.CASCADE)
    special = models.ForeignKey(Special, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return self.label

    @property
    def label(self) -> str:
        return self.display_name or self.ball.country


class MerchantRotation(models.Model):
    """
    Stores generated rotations to persist across restarts.
    """

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ("-starts_at",)

    def is_active(self) -> bool:
        return self.ends_at > timezone.now()

    def remaining(self) -> timedelta:
        return max(self.ends_at - timezone.now(), timedelta())


class MerchantRotationItem(models.Model):
    """
    Snapshot of a merchant offer for a given rotation.
    """

    rotation = models.ForeignKey(MerchantRotation, on_delete=models.CASCADE, related_name="rotation_items")
    item = models.ForeignKey(MerchantItem, on_delete=models.CASCADE, related_name="rotation_entries")
    price_snapshot = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.item.label} ({self.price_snapshot})"

    def as_line(self, currency_name: str, collectible_name: str) -> str:
        special = f" ({self.item.special})" if self.item.special else ""
        return f"{self.item.label}{special} — {self.price_snapshot} {currency_name} ({collectible_name})"


class MerchantPurchase(models.Model):
    """
    Tracks purchases to enforce per-player cooldowns and provide simple auditability.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="merchant_purchases")
    rotation_item = models.ForeignKey(
        MerchantRotationItem, on_delete=models.CASCADE, related_name="purchases"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = (models.Index(fields=("player", "created_at")),)

    def __str__(self) -> str:
        return f"{self.player_id} -> {self.rotation_item_id}"
