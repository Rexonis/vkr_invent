"""Маршруты backend API и административной панели Django."""

from django.contrib import admin
from django.conf import settings
from django.shortcuts import redirect
from django.urls import path

from inventory import views


urlpatterns = [
    path("", lambda request: redirect(settings.FRONTEND_URL)),
    path("admin/", admin.site.urls),
    path("api/auth/me", views.auth_me),
    path("api/auth/login", views.auth_login),
    path("api/auth/register", views.auth_register),
    path("api/auth/logout", views.auth_logout),
    path("api/ad/settings", views.ad_settings_view),
    path("api/ad/test", views.ad_test_connection),
    path("api/dictionaries", views.dictionaries),
    path("api/summary", views.summary),
    path("api/cabinet", views.cabinet),
    path("api/equipment", views.equipment_collection),
    path("api/equipment/<int:pk>", views.equipment_detail),
    path("api/requests", views.service_requests),
    path("api/requests/<int:pk>", views.service_request_detail),
    path("api/notifications", views.notifications_collection),
    path("api/notifications/stream", views.notifications_stream),
    path("api/notifications/<int:pk>/read", views.notification_read),
    path("api/network-scan", views.network_scan),
    path("api/network-assets", views.network_assets),
    path("api/network-assets/<str:kind>/<int:pk>", views.network_asset_detail),
    path("api/movements", views.movements_collection),
    path("api/movements/<int:pk>", views.movement_detail),
    path("api/writeoffs", views.writeoffs_collection),
    path("api/writeoffs/<int:pk>", views.writeoff_detail),
    path("api/inventory/sessions", views.inventory_sessions),
    path("api/inventory/sessions/<int:pk>", views.inventory_session_detail),
    path("api/inventory/sessions/<int:pk>/report", views.inventory_session_report),
    path("api/inventory/sessions/<int:pk>/checks", views.inventory_session_checks),
    path("api/reports", views.reports),
    path("api/users", views.users_collection),
    path("api/users/<int:pk>", views.user_detail),
    path("api/audit", views.audit_collection),
    path("api/export/equipment.<str:fmt>", views.export_equipment),
]
