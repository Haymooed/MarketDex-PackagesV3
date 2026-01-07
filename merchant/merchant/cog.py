from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta
from typing import TYPE_CHECKING, List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from django.db import transaction
from django.utils import timezone

from bd_models.models import BallInstance, Player
from settings.models import settings

# ✅ IMPORTANT:
# BallsDex v3 expects imports from the PACKAGE ROOT, not parent-relative paths
from merchant.models.item import MerchantItem
from merchant.models.purchase import MerchantPurchase
from merchant.models.rotation import MerchantRotation, MerchantRotationItem
from merchant.models.settings import MerchantSettings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger(__name__)
Interaction = discord.Interaction["BallsDexBot"]


class Merchant(commands.GroupCog, name="merchant"):
    """Traveling merchant system (BallsDex v3 compatible)."""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self._rotation_lock = asyncio.Lock()
        self._rotation_refresher.start()

    async def cog_unload(self) -> None:
        self._rotation_refresher.cancel()

    # ========================
    # Rotation handling
    # ========================

    @tasks.loop(minutes=5)
    async def _rotation_refresher(self) -> None:
        await self.ensure_rotation()

    @_rotation_refresher.before_loop
    async def _before_rotation_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def ensure_rotation(self) -> Optional[MerchantRotation]:
        async with self._rotation_lock:
            config = await MerchantSettings.load()
            if not config.enabled:
                return None

            now = timezone.now()
            rotation = await self._get_active_rotation()
            if rotation and rotation.ends_at > now:
                return rotation

            return await self._create_rotation(config)

    async def _get_active_rotation(self) -> Optional[MerchantRotation]:
        qs = MerchantRotation.objects.filter(
            ends_at__gt=timezone.now()
        ).order_by("-starts_at")

        async for rotation in qs[:1]:
            return rotation
        return None

    async def _create_rotation(
        self, config: MerchantSettings
    ) -> Optional[MerchantRotation]:
        qs = (
            MerchantItem.objects.filter(enabled=True)
            .select_related("ball", "special")
            .order_by("id")
        )
        items = [item async for item in qs]
        if not items:
            log.warning("Merchant rotation skipped: no enabled items.")
            return None

        count = min(config.items_per_rotation, len(items))
        selection = self._weighted_sample(items, count)

        now = timezone.now()
        rotation = await MerchantRotation.objects.acreate(
            starts_at=now,
            ends_at=now + config.rotation_delta,
        )

        await MerchantRotationItem.objects.abulk_create(
            [
                MerchantRotationItem(
                    rotation=rotation,
                    item=item,
                    price_snapshot=item.price,
                )
                for item in selection
            ]
        )

        await MerchantSettings.objects.filter(pk=config.pk).aupdate(
            last_rotation_at=now
        )

        log.info("Merchant rotation created (%s items).", len(selection))
        return rotation

    @staticmethod
    def _weighted_sample(
        items: List[MerchantItem], k: int
    ) -> List[MerchantItem]:
        pool = list(items)
        chosen: List[MerchantItem] = []

        while pool and len(chosen) < k:
            weights = [max(1, i.weight) for i in pool]
            pick = random.choices(pool, weights=weights, k=1)[0]
            chosen.append(pick)
            pool.remove(pick)

        return chosen

    async def _rotation_items(
        self, rotation: MerchantRotation
    ) -> List[MerchantRotationItem]:
        qs = rotation.rotation_items.select_related(
            "item__ball",
            "item__special",
        )
        return [entry async for entry in qs]

    async def _cooldown_remaining(
        self, player: Player, cooldown: timedelta
    ) -> timedelta:
        qs = MerchantPurchase.objects.filter(
            player=player
        ).order_by("-created_at")

        async for purchase in qs[:1]:
            remaining = (
                purchase.created_at + cooldown - timezone.now()
            )
            return max(remaining, timedelta())

        return timedelta()

    # ========================
    # Embeds
    # ========================

    async def _build_embed(
        self, rotation: MerchantRotation
    ) -> discord.Embed:
        entries = await self._rotation_items(rotation)
        currency = settings.currency_name or "coins"

        embed = discord.Embed(
            title="🧳 Traveling Merchant",
            description=(
                f"Offers refresh "
                f"{discord.utils.format_dt(rotation.ends_at, style='R')}."
            ),
            colour=discord.Colour.blurple(),
        )

        if not entries:
            embed.description = "No offers available."
            return embed

        lines = []
        for entry in entries:
            special = f" ({entry.item.special})" if entry.item.special else ""
            lines.append(
                f"`{entry.id}` — {entry.item.label}{special} "
                f"• {entry.price_snapshot} {currency}"
            )

        embed.add_field(
            name="Current offers",
            value="\n".join(lines),
            inline=False,
        )
        embed.set_footer(
            text="Use /merchant buy <id> to purchase."
        )
        return embed

    # ========================
    # Slash commands
    # ========================

    @app_commands.command(
        name="view",
        description="View the current merchant rotation.",
    )
    async def view(self, interaction: Interaction) -> None:
        rotation = await self.ensure_rotation()
        if rotation is None:
            await interaction.response.send_message(
                "The merchant is disabled.",
                ephemeral=True,
            )
            return

        embed = await self._build_embed(rotation)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(
        name="buy",
        description="Buy an item from the merchant.",
    )
    async def buy(
        self,
        interaction: Interaction,
        item_id: int,
    ) -> None:
        config = await MerchantSettings.load()
        if not config.enabled:
            await interaction.response.send_message(
                "The merchant is disabled.",
                ephemeral=True,
            )
            return

        rotation = await self.ensure_rotation()
        if rotation is None:
            await interaction.response.send_message(
                "No active rotation.",
                ephemeral=True,
            )
            return

        entries = await self._rotation_items(rotation)
        entry = next(
            (e for e in entries if e.id == item_id),
            None,
        )
        if entry is None:
            await interaction.response.send_message(
                "Invalid item ID.",
                ephemeral=True,
            )
            return

        player, _ = await Player.objects.aget_or_create(
            discord_id=interaction.user.id
        )

        remaining = await self._cooldown_remaining(
            player, config.purchase_cooldown
        )
        if remaining > timedelta():
            await interaction.response.send_message(
                f"You can buy again "
                f"{discord.utils.format_dt(timezone.now() + remaining, style='R')}.",
                ephemeral=True,
            )
            return

        price = entry.price_snapshot
        if not player.can_afford(price):
            await interaction.response.send_message(
                f"You need {price} {settings.currency_name}.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        async with transaction.atomic():
            player = await Player.objects.select_for_update().aget(
                pk=player.pk
            )
            if not player.can_afford(price):
                await interaction.followup.send(
                    "Insufficient funds.",
                    ephemeral=True,
                )
                return

            await player.remove_money(price)

            instance = await BallInstance.objects.acreate(
                ball_id=entry.item.ball_id,
                player=player,
                special_id=entry.item.special_id,
                tradeable=True,
                server_id=interaction.guild_id,
            )

            await MerchantPurchase.objects.acreate(
                player=player,
                rotation_item=entry,
            )

        await interaction.followup.send(
            f"Purchase successful! "
            f"{instance.description(include_emoji=True, bot=self.bot)}",
            ephemeral=True,
        )

    # ========================
    # Autocomplete
    # ========================

    @buy.autocomplete("item_id")
    async def autocomplete_item(
        self,
        interaction: Interaction,
        current: str,
    ):
        rotation = await self._get_active_rotation()
        if rotation is None:
            return []

        entries = await self._rotation_items(rotation)
        currency = settings.currency_name or "coins"

        if current:
            entries = [
                e for e in entries
                if current.lower() in e.item.label.lower()
            ]

        return [
            app_commands.Choice(
                name=f"{e.item.label} • {e.price_snapshot} {currency}",
                value=e.id,
            )
            for e in entries[:25]
        ]
