from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from django.db import transaction
from django.utils import timezone

from bd_models.models import BallInstance, Player
from settings.models import settings

from .models import MerchantItem, MerchantPurchase, MerchantRotation, MerchantRotationItem, MerchantSettings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


log = logging.getLogger(__name__)
Interaction = discord.Interaction["BallsDexBot"]


class Merchant(commands.GroupCog, name="merchant"):
    """
    Merchant rotation with admin-managed item pool and slash commands.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self._rotation_lock = asyncio.Lock()
        self._rotation_refresher.start()

    async def cog_unload(self):
        self._rotation_refresher.cancel()

    @tasks.loop(minutes=5)
    async def _rotation_refresher(self):
        await self.ensure_rotation()

    @_rotation_refresher.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    async def ensure_rotation(self) -> MerchantRotation | None:
        """
        Ensure a current rotation exists (unless disabled).
        """
        async with self._rotation_lock:
            config = await MerchantSettings.load()
            if not config.enabled:
                return None

            now = timezone.now()
            rotation = await self._active_rotation()
            if rotation and rotation.ends_at > now:
                return rotation

            return await self._create_rotation(config)

    async def _active_rotation(self) -> MerchantRotation | None:
        qs = MerchantRotation.objects.filter(ends_at__gt=timezone.now()).order_by("-starts_at")
        async for rotation in qs[:1]:
            return rotation
        return None

    async def _create_rotation(self, config: MerchantSettings) -> MerchantRotation | None:
        items_qs = (
            MerchantItem.objects.filter(enabled=True)
            .select_related("ball", "special")
            .order_by("id")
        )
        items = [item async for item in items_qs]
        if not items:
            log.warning("Merchant rotation skipped: item pool is empty.")
            return None

        count = min(config.items_per_rotation, len(items))
        selection = self._weighted_sample(items, count)
        now = timezone.now()
        rotation = await MerchantRotation.objects.acreate(starts_at=now, ends_at=now + config.rotation_delta)
        await MerchantRotationItem.objects.abulk_create(
            [
                MerchantRotationItem(rotation=rotation, item=item, price_snapshot=item.price)
                for item in selection
            ]
        )
        await MerchantSettings.objects.filter(pk=config.pk).aupdate(last_rotation_at=now)
        log.info("Merchant rotation created with %s items.", len(selection))
        return rotation

    @staticmethod
    def _weighted_sample(items: list[MerchantItem], k: int) -> list[MerchantItem]:
        pool = list(items)
        selected: list[MerchantItem] = []
        while pool and len(selected) < k:
            weights = [max(1, item.weight) for item in pool]
            choice = random.choices(pool, weights=weights, k=1)[0]
            selected.append(choice)
            pool.remove(choice)
        return selected

    async def _get_rotation_items(self, rotation: MerchantRotation) -> list[MerchantRotationItem]:
        qs = rotation.rotation_items.select_related("item__ball", "item__special")
        return [entry async for entry in qs]

    async def _cooldown_remaining(self, player: Player, cooldown: timedelta) -> timedelta:
        qs = MerchantPurchase.objects.filter(player=player).order_by("-created_at")
        async for purchase in qs[:1]:
            delta = purchase.created_at + cooldown - timezone.now()
            return max(delta, timedelta())
        return timedelta()

    async def _build_embed(self, rotation: MerchantRotation) -> discord.Embed:
        entries = await self._get_rotation_items(rotation)
        currency = settings.currency_name or "coins"
        embed = discord.Embed(
            title="Traveling Merchant",
            description=f"Offers refresh {discord.utils.format_dt(rotation.ends_at, style='R')}.",
            colour=discord.Colour.blurple(),
        )
        if not entries:
            embed.description = "No offers are available right now. Please check back later."
            return embed

        lines = []
        for entry in entries:
            special = f" ({entry.item.special})" if entry.item.special else ""
            lines.append(
                f"`{entry.id}` — {entry.item.label}{special} • {entry.price_snapshot} {currency}"
            )
        embed.add_field(name="Current offers", value="\n".join(lines), inline=False)
        embed.set_footer(text="Use /merchant buy <id> to purchase.")
        return embed

    @app_commands.command(name="view", description="View the current merchant rotation.")
    async def view(self, interaction: Interaction):
        rotation = await self.ensure_rotation()
        if rotation is None:
            await interaction.response.send_message(
                "The merchant is currently disabled or not configured.", ephemeral=True
            )
            return

        embed = await self._build_embed(rotation)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="buy", description="Buy an item from the merchant.")
    async def buy(self, interaction: Interaction, item_id: int):
        config = await MerchantSettings.load()
        if not config.enabled:
            await interaction.response.send_message("The merchant is disabled.", ephemeral=True)
            return

        rotation = await self.ensure_rotation()
        if rotation is None:
            await interaction.response.send_message("No rotation is currently active.", ephemeral=True)
            return

        entries = await self._get_rotation_items(rotation)
        entry = next((x for x in entries if x.id == item_id), None)
        if entry is None:
            await interaction.response.send_message("Unknown offer id. Check /merchant view for valid ids.", ephemeral=True)
            return

        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        remaining = await self._cooldown_remaining(player, config.purchase_cooldown)
        if remaining > timedelta():
            await interaction.response.send_message(
                f"You can buy again {discord.utils.format_dt(timezone.now() + remaining, style='R')}.",
                ephemeral=True,
            )
            return

        price = entry.price_snapshot
        if not player.can_afford(price):
            await interaction.response.send_message(
                f"You need {price} {settings.currency_name} but only have {player.money}.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        async with transaction.atomic():
            player = await Player.objects.select_for_update().aget(pk=player.pk)
            if not player.can_afford(price):
                await interaction.followup.send("You no longer have enough funds.", ephemeral=True)
                return
            await player.remove_money(price)
            instance = await BallInstance.objects.acreate(
                ball_id=entry.item.ball_id,
                player=player,
                special_id=entry.item.special_id,
                tradeable=True,
                server_id=interaction.guild_id,
            )
            await MerchantPurchase.objects.acreate(player=player, rotation_item=entry)

        await interaction.followup.send(
            f"Purchase successful! {instance.description(include_emoji=True, bot=self.bot)} added to your inventory.",
            ephemeral=True,
        )

    @buy.autocomplete("item_id")
    async def autocomplete_item(self, interaction: Interaction, current: str):
        rotation = await self._active_rotation()
        if rotation is None:
            return []
        entries = await self._get_rotation_items(rotation)
        currency = settings.currency_name or "coins"
        filtered = entries
        if current:
            filtered = [x for x in entries if current.lower() in x.item.label.lower()]
        return [
            app_commands.Choice(name=f"{entry.item.label} • {entry.price_snapshot} {currency}", value=entry.id)
            for entry in filtered[:25]
        ]
