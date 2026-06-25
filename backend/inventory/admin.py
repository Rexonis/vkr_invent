"""Регистрация моделей учета оборудования в административной панели Django."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AppSetting,
    AuditLog,
    Category,
    Employee,
    Equipment,
    InventoryCheck,
    InventorySession,
    Location,
    Movement,
    Notification,
    ServiceRequest,
    User,
    WriteOff,
)


@admin.register(User)
class InventoryUserAdmin(UserAdmin):
    """Настраивает отображение пользовательской модели в административной панели Django."""
    fieldsets = UserAdmin.fieldsets + (
        ("Инвентаризация", {"fields": ("full_name", "role", "employee", "two_factor_enabled", "two_factor_secret", "ad_login")}),
    )
    list_display = ("username", "display_name", "role", "employee", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")


admin.site.register(Category)
admin.site.register(Location)
admin.site.register(Employee)
admin.site.register(Equipment)
admin.site.register(InventorySession)
admin.site.register(InventoryCheck)
admin.site.register(ServiceRequest)
admin.site.register(Notification)
admin.site.register(Movement)
admin.site.register(WriteOff)
admin.site.register(AuditLog)
admin.site.register(AppSetting)
