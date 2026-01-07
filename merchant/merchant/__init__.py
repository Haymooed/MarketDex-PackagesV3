import logging
import textwrap
from typing import TYPE_CHECKING

from .cog import Merchant

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.merchant")

LOGO = textwrap.dedent(r"""
    +---------------------------------------+
    |     BallsDex Merchant Pack v3        |
    |           By Haymooed                |
    |        Licensed under MIT            |
    +---------------------------------------+
""").strip()


async def setup(bot: "BallsDexBot"):
    print(LOGO)
    log.info("Loading Merchant package...")
    await bot.add_cog(Merchant(bot))
    log.info("Merchant package loaded successfully!")
