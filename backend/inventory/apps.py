"""Конфигурация Django-приложения inventory."""

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Конфигурация Django-приложения, где собрана логика учета оборудования."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory"
