# BallsDex V3 Merchant Package

Traveling merchant package for **BallsDex V3**. Provides rotating offers, admin-managed item pool, and slash commands for browsing and purchasing collectibles.

## Installation (extra.toml)

Add this entry to `config/extra.toml` so BallsDex installs the package automatically:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/Haymooed/MarketDex-PackagesV3.git"
path = "merchant"
enabled = true
editable = false
```

> The package is distributed as a standard Python package; no manual file copying is required.

## Enabling & configuring

All configuration is handled through the admin panel (no hardcoded settings):

- `Merchant settings` (singleton):
  - Enable/disable merchant
  - Rotation duration (minutes)
  - Items per rotation
  - Purchase cooldown (seconds)
- `Merchant items`:
  - Selectable pool with price, weight, optional special
- Rotations & purchases are recorded for visibility/audit.

## Commands (slash, app_commands)

- `/merchant view` — show current offers (rotations refresh automatically).
- `/merchant buy <id>` — purchase the selected offer; creates a `BallInstance`, charges price, and enforces cooldowns.

## Notes

- Rotations are created automatically when the merchant is enabled and the item pool is non-empty.
- Uses BallsDex models (`Ball`, `BallInstance`, `Player`, `Special`) and follows the V3 extra package loading flow.
- Async `setup(bot)` and modern `app_commands`; no legacy decorators or manual loaders.
