from django.contrib import admin

from .models import MerchantItem, MerchantPurchase, MerchantRotation, MerchantRotationItem, MerchantSettings


@admin.register(MerchantSettings)
class MerchantSettingsAdmin(admin.ModelAdmin):
    list_display = ("enabled", "rotation_minutes", "items_per_rotation", "purchase_cooldown_seconds", "last_rotation_at")
    readonly_fields = ("last_rotation_at",)

    def has_add_permission(self, request):
        # enforce singleton; editing is allowed but creation is not
        return False


@admin.register(MerchantItem)
class MerchantItemAdmin(admin.ModelAdmin):
    list_display = ("label", "price", "weight", "enabled", "ball", "special")
    list_filter = ("enabled", "special")
    search_fields = ("display_name", "ball__country")


class MerchantRotationItemInline(admin.TabularInline):
    model = MerchantRotationItem
    extra = 0
    readonly_fields = ("item", "price_snapshot", "created_at")
    can_delete = False


@admin.register(MerchantRotation)
class MerchantRotationAdmin(admin.ModelAdmin):
    list_display = ("starts_at", "ends_at")
    readonly_fields = ("starts_at", "ends_at")
    inlines = (MerchantRotationItemInline,)

    def has_add_permission(self, request):
        # rotations are generated automatically
        return False


@admin.register(MerchantPurchase)
class MerchantPurchaseAdmin(admin.ModelAdmin):
    list_display = ("player", "rotation_item", "created_at")
    search_fields = ("player__discord_id",)
    readonly_fields = ("player", "rotation_item", "created_at")

    def has_add_permission(self, request):
        return False
