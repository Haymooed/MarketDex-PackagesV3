import logging
import textwrap
from typing import TYPE_CHECKING

from .cog import Merchant

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

# Configure logger for this package
log = logging.getLogger("ballsdex.packages.merchant")

# Optional ASCII banner (clean and professional)
LOGO = textwrap.dedent(r"""
    +--------------------------------------------------+
    |          Merchant Package  By Haymooed           |
    |            Licensed under MIT       |            |
    +--------------------------------------------------+
""").strip()


async def setup(bot: "BallsDexBot"):
    # Print banner to console
    print(LOGO)

    log.info("Initializing Merchant package...")
    await bot.add_cog(Merchant(bot))
    log.info("Merchant package loaded successfully!")
