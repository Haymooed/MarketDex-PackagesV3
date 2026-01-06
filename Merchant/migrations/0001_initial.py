from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bd_models", "0014_alter_ball_options_alter_ballinstance_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantSettings",
            fields=[
                (
                    "singleton_id",
                    models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False),
                ),
                ("enabled", models.BooleanField(default=True, help_text="Disable to hide the merchant entirely.")),
                (
                    "rotation_minutes",
                    models.PositiveIntegerField(default=1440, help_text="How long a rotation lasts, in minutes. Default: 24h."),
                ),
                (
                    "items_per_rotation",
                    models.PositiveSmallIntegerField(default=3, help_text="How many offers are selected for each rotation."),
                ),
                (
                    "purchase_cooldown_seconds",
                    models.PositiveIntegerField(
                        default=3600, help_text="Cooldown between purchases for the same player, in seconds."
                    ),
                ),
                ("last_rotation_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Merchant settings",
            },
        ),
        migrations.CreateModel(
            name="MerchantRotation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
            ],
            options={
                "ordering": ("-starts_at",),
            },
        ),
        migrations.CreateModel(
            name="MerchantItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, help_text="Optional override name. Defaults to the ball name.", max_length=64)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("price", models.PositiveBigIntegerField(default=1000, help_text="Price charged to the player.")),
                ("weight", models.PositiveIntegerField(default=1, help_text="Relative selection weight for rotations.")),
                ("enabled", models.BooleanField(default=True)),
                ("ball", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="bd_models.ball")),
                (
                    "special",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="bd_models.special"
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="MerchantRotationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_snapshot", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="rotation_entries", to="merchant.merchantitem"
                    ),
                ),
                (
                    "rotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="rotation_items", to="merchant.merchantrotation"
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="MerchantPurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="merchant_purchases",
                        to="bd_models.player",
                    ),
                ),
                (
                    "rotation_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchases",
                        to="merchant.merchantrotationitem",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="merchantpurchase",
            index=models.Index(fields=["player", "created_at"], name="merchant_me_player__8ef229_idx"),
        ),
    ]
