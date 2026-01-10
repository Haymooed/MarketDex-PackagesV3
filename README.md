# BallsDex V3 Merchant Package

Traveling merchant package for **BallsDex V3**. Provides rotating offers, admin-managed item pool, and slash commands for browsing and purchasing collectibles.

## Installation (extra.toml)

Add this entry to `config/extra.toml` so BallsDex installs the package automatically:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/Haymooed/BallsDex-Merchant-Package.git"
path = "merchant"
enabled = true
editable = false
```
## Enabling & configuring

All configuration is handled through the admin panel:

- `Merchant settings` (singleton):
  - Enable/disable merchant
  - Rotation duration (minutes)
  - Items per rotation
  - Purchase cooldown (seconds)
- `Merchant items`:
  - Selectable pool with price, weight, optional special
- Rotations & purchases are recorded for visibility/audit.

