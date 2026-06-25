"""API-представления и сервисные функции backend: авторизация, оборудование, заявки, отчеты и уведомления."""

import json
from html import escape
from io import BytesIO
import ipaddress
from pathlib import Path
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import CharField, Count, Sum, Q
from django.db.models.functions import Cast
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import ad as active_directory
from .models import (
    AppSetting, AuditLog, Category, Employee, Equipment, InfrastructureSegment,
    InternetLink, InventoryCheck, InventorySession, Location, Movement, Network,
    NetworkDomain, NetworkIpAddress, NetworkVlan, Notification, ServiceRequest,
    TelephonyLine, User, WriteOff,
)
from .security import normalize_search_query, parse_choice_filter, parse_positive_int_filter


ROLE_PERMISSIONS = {
    "it_admin": {
        "equipment:view", "equipment:write", "equipment:delete", "inventory:write",
        "reports:view", "users:manage", "audit:view", "lifecycle:manage", "ml:manage",
        "requests:create", "requests:approve", "network:scan", "network:manage",
    },
    "warehouse": {"equipment:view", "equipment:write", "inventory:write", "reports:view", "requests:approve", "lifecycle:manage"},
    "accountant": {"equipment:view", "reports:view", "finance:view"},
    "manager": {"equipment:view", "reports:view", "requests:approve"},
    "employee": {"requests:create"},
}


ROLES = {
    value: {"name": label, "permissions": sorted(ROLE_PERMISSIONS[value])}
    for value, label in User.Role.choices
}

MOVEMENT_STATUSES = {
    "planned": "Запланировано",
    "done": "Выполнено",
    "cancelled": "Отменено",
}

WRITEOFF_STATUSES = {
    "prepared": "Подготовлено",
    "review": "На согласовании",
    "written_off": "Списано",
    "rejected": "Отклонено",
}

INVENTORY_RESULTS = {
    "found": "Найдено",
    "missing": "Не найдено",
    "moved": "Перемещено",
}

# Единый белый список аватаров: backend принимает только варианты, которые есть в интерфейсе.
AVATAR_KEYS = {
    "slate", "mint", "amber", "rose", "violet", "sky", "forest", "graphite",
    "cat", "dog", "fox", "bear", "panda", "owl", "rabbit",
    "rocket", "star", "shield", "gem", "bolt", "compass",
}

REQUEST_TITLE_KEYWORDS = (
    "ноутбук", "компьютер", "пк", "монитор", "принтер", "мфу", "сканер",
    "клавиатур", "мыш", "телефон", "гарнитур", "проектор", "планшет",
    "сервер", "роутер", "кабель", "картридж", "оборуд", "техник",
    "доступ", "аккаунт", "учет", "парол", "права", "почт", "сеть",
    "интернет", "лицензи", "программ", "софт", "установ", "настро",
    "ремонт", "замен", "выдать", "требу", "рабоч", "мест",
)


AD_SETTING_KEYS = {
    "enabled": "ad.enabled",
    "domain": "ad.domain",
    "server": "ad.server",
    "controller": "ad.controller",
    "port": "ad.port",
    "use_ssl": "ad.use_ssl",
    "base_dn": "ad.base_dn",
    "bind_user": "ad.bind_user",
}


def setting_value(key, default=""):
    """Получает значение системной настройки из базы данных с резервным значением."""
    row = AppSetting.objects.filter(pk=key).first()
    return row.value if row else default


def ad_settings():
    """Собирает настройки Active Directory из хранилища приложения."""
    server = setting_value(AD_SETTING_KEYS["server"], "") or setting_value(AD_SETTING_KEYS["controller"], "")
    use_ssl = False
    port = setting_value(AD_SETTING_KEYS["port"], "389")
    if str(port) == "636":
        port = "389"
    return {
        "enabled": setting_value(AD_SETTING_KEYS["enabled"], "false") == "true",
        "domain": setting_value(AD_SETTING_KEYS["domain"], ""),
        "server": server,
        "controller": server,
        "port": int(port or 389),
        "use_ssl": use_ssl,
        "base_dn": setting_value(AD_SETTING_KEYS["base_dn"], ""),
        "bind_user": setting_value(AD_SETTING_KEYS["bind_user"], ""),
    }


def save_ad_settings(data):
    """Проверяет и сохраняет настройки Active Directory из административного интерфейса."""
    server_value = data.get("controller") if "controller" in data else data.get("server")
    server = (server_value or "").strip()
    use_ssl = False
    port = int(data.get("port") or 389)
    if port == 636:
        port = 389
    if port < 1 or port > 65535:
        raise ValueError("Invalid AD controller port")
    settings = {
        "enabled": bool(data.get("enabled")),
        "domain": (data.get("domain") or "").strip(),
        "server": server,
        "controller": server,
        "port": port,
        "use_ssl": use_ssl,
        "base_dn": (data.get("base_dn") or "").strip(),
        "bind_user": (data.get("bind_user") or "").strip(),
    }
    if settings["enabled"] and not (settings["domain"] or settings["server"]):
        raise ValueError("Укажите домен и контроллер домена")
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["enabled"], defaults={"value": "true" if settings["enabled"] else "false"})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["domain"], defaults={"value": settings["domain"]})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["server"], defaults={"value": settings["server"]})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["controller"], defaults={"value": settings["server"]})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["port"], defaults={"value": str(settings["port"])})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["use_ssl"], defaults={"value": "true" if settings["use_ssl"] else "false"})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["base_dn"], defaults={"value": settings["base_dn"]})
    AppSetting.objects.update_or_create(key=AD_SETTING_KEYS["bind_user"], defaults={"value": settings["bind_user"]})
    return settings


def json_body(request):
    """Читает JSON-тело HTTP-запроса и возвращает словарь параметров."""
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def error(message, status=400):
    """Формирует единый JSON-ответ с текстом ошибки и HTTP-статусом."""
    return JsonResponse({"error": message}, status=status)


def validate_request_title(value):
    """Проверяет тему заявки на длину, осмысленность и связь с ИТ-предметной областью."""
    title = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(title) < 8:
        raise ValueError("Тема заявки должна содержать не менее 8 символов")
    if len(title) > 120:
        raise ValueError("Тема заявки должна быть не длиннее 120 символов")
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", title)
    if len(letters) < 6:
        raise ValueError("Тема заявки должна содержать понятное описание, а не набор символов")
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{2,}", title)
    if len(words) < 2:
        raise ValueError("Укажите тему заявки минимум из двух слов, например: Замена клавиатуры")
    compact = re.sub(r"[^A-Za-zА-Яа-яЁё0-9]", "", title).lower()
    if re.search(r"([A-Za-zА-Яа-яЁё])\1{3,}", compact):
        raise ValueError("Тема заявки похожа на случайный набор букв")
    if any(pattern in compact for pattern in ("qwerty", "asdf", "zxcv", "йцу", "фыв", "ячс", "апрол")):
        raise ValueError("Тема заявки похожа на случайный набор букв")
    if not any(keyword in compact for keyword in REQUEST_TITLE_KEYWORDS):
        raise ValueError("Укажите конкретный предмет заявки: ноутбук, монитор, принтер, доступ, ремонт и т.д.")
    return title


def public_user(user):
    """Преобразует пользователя в безопасную структуру для клиентского приложения."""
    if not user.is_authenticated:
        return None
    permissions = sorted(ROLE_PERMISSIONS.get(user.role, set()))
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.display_name(),
        "email": user.email,
        "role": user.role,
        "avatar": user.avatar or "slate",
        "employee_id": user.employee_id,
        "ad_login": user.ad_login,
        "can_edit_profile": not bool(user.ad_login),
        "permissions": permissions,
    }


def require_login(request):
    """Проверяет наличие авторизованного пользователя для защищенных API-методов."""
    if request.user.is_authenticated:
        return None
    return error("Требуется авторизация", 401)


def require_permission(request, permission):
    """Проверяет наличие требуемого разрешения у роли текущего пользователя."""
    denied = require_login(request)
    if denied:
        return denied
    if permission in ROLE_PERMISSIONS.get(request.user.role, set()):
        return None
    return error("Недостаточно прав для операции", 403)


def choice_rows(choices):
    """Преобразует Django choices в список словарей для выпадающих списков интерфейса."""
    return [{"id": value, "name": label} for value, label in choices]


def employee_to_dict(row):
    """Преобразует сотрудника в JSON-структуру для API."""
    return {
        "id": row.id,
        "full_name": row.full_name,
        "department": row.department,
        "email": row.email,
        "phone": row.phone,
    }


def equipment_qr_payload(row):
    """Формирует полезную нагрузку QR-кода для карточки оборудования."""
    return {
        "type": "equipment",
        "id": row.id,
        "inventory_number": row.inventory_number,
        "name": row.name,
        "category": row.category.name if row.category else "",
        "serial_number": row.serial_number,
        "location": str(row.location) if row.location else "",
        "employee": row.employee.full_name if row.employee else "",
        "status": row.get_status_display(),
        "ip_address": row.ip_address or "",
        "mac_address": row.mac_address,
        "warranty_until": row.warranty_until.isoformat() if row.warranty_until else "",
    }


def build_qr_svg(payload):
    """Генерирует SVG-изображение QR-кода по переданным данным."""
    import io
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=3)
    output = io.BytesIO()
    image.save(output)
    return output.getvalue().decode("utf-8")


def ensure_equipment_qr(row):
    """Обновляет QR-код оборудования, если его содержимое устарело."""
    payload = equipment_qr_payload(row)
    if row.qr_payload == payload and row.qr_svg:
        return row.qr_payload, row.qr_svg
    row.qr_payload = payload
    row.qr_svg = build_qr_svg(payload)
    row.save(update_fields=["qr_payload", "qr_svg", "updated_at"])
    return row.qr_payload, row.qr_svg


def equipment_to_dict(row):
    """Преобразует карточку оборудования в полный JSON-ответ для интерфейса."""
    qr_payload, qr_svg = ensure_equipment_qr(row)
    return {
        "id": row.id,
        "inventory_number": row.inventory_number,
        "name": row.name,
        "category_id": row.category_id,
        "category_name": row.category.name if row.category else "",
        "serial_number": row.serial_number,
        "location_id": row.location_id,
        "location_name": str(row.location) if row.location else "",
        "location_room": row.location.room if row.location else "",
        "employee_id": row.employee_id,
        "employee_name": row.employee.full_name if row.employee else "",
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else "",
        "warranty_until": row.warranty_until.isoformat() if row.warranty_until else "",
        "price": float(row.price or 0),
        "status": row.status,
        "status_label": row.get_status_display(),
        "condition": row.condition,
        "condition_label": row.get_condition_display(),
        "ip_address": row.ip_address or "",
        "mac_address": row.mac_address,
        "specs": row.specs,
        "notes": row.notes,
        "qr_payload": qr_payload,
        "qr_svg": qr_svg,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def filtered_equipment_queryset(request):
    """Строит queryset оборудования с поиском, фильтрами и ролевыми ограничениями."""
    queryset = Equipment.objects.select_related("category", "location", "employee")
    query = normalize_search_query(request.GET.get("q"))
    if query:
        queryset = queryset.annotate(ip_text=Cast("ip_address", CharField()))
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(inventory_number__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(ip_text__icontains=query)
            | Q(employee__full_name__icontains=query)
        )
    for field in ["category_id", "location_id", "employee_id"]:
        value = parse_positive_int_filter(request.GET.get(field), field)
        if value is not None:
            queryset = queryset.filter(**{field: value})
    status = parse_choice_filter(request.GET.get("status"), Equipment.Status.values, "status")
    if status:
        queryset = queryset.filter(status=status)
    condition = parse_choice_filter(request.GET.get("condition"), Equipment.Condition.values, "condition")
    if condition:
        queryset = queryset.filter(condition=condition)
    if request.user.role == User.Role.EMPLOYEE and request.user.employee_id:
        queryset = queryset.filter(employee_id=request.user.employee_id)
    return queryset


def movement_to_dict(row):
    """Преобразует запись перемещения оборудования в JSON-структуру."""
    return {
        "id": row.id,
        "equipment_id": row.equipment_id,
        "inventory_number": row.inventory_number,
        "equipment_name": row.equipment_name,
        "from_location_id": row.from_location_id,
        "from_location_name": str(row.from_location) if row.from_location else "",
        "from_location_room": row.from_location.room if row.from_location else "",
        "to_location_id": row.to_location_id,
        "to_location_name": str(row.to_location) if row.to_location else "",
        "to_location_room": row.to_location.room if row.to_location else "",
        "employee_id": row.employee_id,
        "employee_name": row.employee.full_name if row.employee else "",
        "moved_at": row.moved_at.isoformat(),
        "status": row.status,
        "status_label": MOVEMENT_STATUSES.get(row.status, row.status),
        "created_at": row.created_at.isoformat(),
        "archived": row.archived,
    }


def writeoff_to_dict(row):
    """Преобразует запись списания оборудования в JSON-структуру."""
    return {
        "id": row.id,
        "equipment_id": row.equipment_id,
        "inventory_number": row.inventory_number,
        "equipment_name": row.equipment_name,
        "reason": row.reason,
        "writeoff_date": row.writeoff_date.isoformat(),
        "commission": row.commission,
        "status": row.status,
        "status_label": WRITEOFF_STATUSES.get(row.status, row.status),
        "created_at": row.created_at.isoformat(),
        "archived": row.archived,
    }


def inventory_session_to_dict(row):
    """Преобразует сессию инвентаризации и ее прогресс в JSON-структуру."""
    total = Equipment.objects.count()
    checked = row.checks.count()
    return {
        "id": row.id,
        "title": row.title,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else "",
        "status": row.status,
        "status_label": row.status,
        "checked_count": checked,
        "total_count": total,
        "archived": row.archived,
    }


def user_to_dict(row):
    """Преобразует пользователя и связанного сотрудника в структуру для администрирования."""
    employee = row.employee
    return {
        "id": row.id,
        "username": row.username,
        "full_name": row.display_name(),
        "profile_full_name": row.full_name,
        "email": row.email,
        "role": row.role,
        "role_name": row.get_role_display(),
        "avatar": row.avatar or "slate",
        "employee_id": row.employee_id,
        "employee_name": employee.full_name if employee else "",
        "employee_department": employee.department if employee else "",
        "employee_email": employee.email if employee else "",
        "employee_phone": employee.phone if employee else "",
        "ad_login": row.ad_login,
        "can_edit_profile": not bool(row.ad_login),
        "two_factor_enabled": row.two_factor_enabled,
        "is_active": row.is_active,
        "is_staff": row.is_staff,
        "is_superuser": row.is_superuser,
        "last_login": row.last_login.isoformat() if row.last_login else "",
    }


LOCAL_PROFILE_FIELDS = {"full_name", "email", "department", "phone"}


def apply_local_profile_payload(user, data):
    """Применяет изменения локального профиля пользователя и связанного сотрудника."""
    if user.ad_login:
        raise PermissionError("Профиль пользователя AD редактируется в Active Directory")
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    department = (data.get("department") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not full_name:
        raise ValueError("Укажите ФИО")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("Укажите корректный email")
    user.full_name = full_name[:180]
    user.email = email[:254]
    employee = user.employee or Employee()
    employee.full_name = full_name[:180]
    employee.email = email[:254]
    employee.department = department[:160]
    employee.phone = phone[:80]
    employee.save()
    user.employee = employee


def apply_avatar_payload(user, data):
    # Аватар можно менять отдельно от личных данных, в том числе для учетных записей AD.
    """Проверяет и сохраняет выбранный аватар пользователя."""
    if "avatar" not in data:
        return
    avatar = (data.get("avatar") or "slate").strip()
    if avatar not in AVATAR_KEYS:
        raise ValueError("Выберите аватар из списка")
    user.avatar = avatar


def audit_to_dict(row):
    """Преобразует запись аудита в JSON-структуру для журнала операций."""
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "username": row.username,
        "action": row.action,
        "entity": row.entity,
        "entity_id": row.entity_id,
    }


def service_request_to_dict(row):
    """Преобразует заявку сотрудника в JSON-структуру для списка и карточки."""
    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "status_label": row.get_status_display(),
        "requested_specs": row.requested_specs,
        "justification": row.justification,
        "decision_reason": row.decision_reason,
        "archived_by_requester": row.archived_by_requester,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else "",
        "user_id": row.user_id,
        "username": row.user.username if row.user else "",
        "requester_name": row.user.display_name() if row.user else "",
        "employee_name": row.employee.full_name if row.employee else "",
        "employee_department": row.employee.department if row.employee else "",
        "category_id": row.category_id,
        "category_name": row.category.name if row.category else "",
        "decided_by_id": row.decided_by_id,
        "decided_by_name": row.decided_by.display_name() if row.decided_by else "",
    }


def notification_to_dict(row):
    """Преобразует уведомление пользователя в JSON-структуру."""
    return {
        "id": row.id,
        "title": row.title,
        "message": row.message,
        "link": row.link,
        "is_read": row.is_read,
        "created_at": row.created_at.isoformat(),
    }


def create_notification(user, title, message, link=""):
    """Создает уведомление для конкретного пользователя."""
    if not user:
        return None
    return Notification.objects.create(user=user, title=title, message=message, link=link)


def notification_rows(user):
    """Возвращает последние уведомления пользователя для интерфейса."""
    rows = Notification.objects.filter(user=user).order_by("-created_at", "-id")[:50]
    return [notification_to_dict(row) for row in rows]


def notify_users_with_permission(permission, title, message, link="", exclude_user_id=None):
    """Рассылает уведомление всем активным пользователям с заданным разрешением."""
    roles = [role for role, permissions in ROLE_PERMISSIONS.items() if permission in permissions]
    users = User.objects.filter(role__in=roles, is_active=True)
    if exclude_user_id:
        users = users.exclude(id=exclude_user_id)
    return [
        create_notification(user, title, message, link)
        for user in users
    ]


def add_audit(request, action, entity="", entity_id="", before=None, after=None):
    """Записывает действие пользователя в журнал аудита с состоянием до и после операции."""
    user = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        user=user,
        username=user.username if user else "",
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        before_json=before,
        after_json=after,
    )


def parse_fk(model, value):
    """Преобразует идентификатор из запроса в объект модели или None."""
    if value in ("", None):
        return None
    try:
        return model.objects.get(pk=value)
    except (model.DoesNotExist, TypeError, ValueError):
        raise ValueError("Связанная запись не найдена")


def parse_optional_date(value, field_name):
    """Проверяет необязательную дату из запроса и возвращает объект date."""
    if value in ("", None):
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        raise ValueError(f"Некорректная дата в поле {field_name}")
    return parsed


def parse_movement_datetime(value):
    """Преобразует дату перемещения в timezone-aware datetime."""
    source = value or timezone.localdate().isoformat()
    try:
        parsed = timezone.datetime.fromisoformat(str(source))
    except ValueError:
        raise ValueError("Некорректная дата перемещения")
    if parsed.tzinfo is None:
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed.astimezone(timezone.get_current_timezone())


NETWORK_ASSET_CONFIG = {
    "segments": {
        "model": InfrastructureSegment,
        "fields": ["name", "code", "owner", "description"],
        "required": ["name"],
    },
    "networks": {
        "model": Network,
        "fields": ["name", "cidr", "gateway", "purpose", "notes"],
        "fk": {"segment": (InfrastructureSegment, "segment_id")},
        "required": ["name", "cidr"],
    },
    "vlans": {
        "model": NetworkVlan,
        "fields": ["vlan_id", "name", "purpose", "notes"],
        "fk": {"segment": (InfrastructureSegment, "segment_id"), "network": (Network, "network_id")},
        "required": ["vlan_id", "name"],
    },
    "ips": {
        "model": NetworkIpAddress,
        "fields": ["address", "hostname", "owner", "status", "notes"],
        "fk": {"network": (Network, "network_id"), "vlan": (NetworkVlan, "vlan_id")},
        "required": ["address"],
    },
    "domains": {
        "model": NetworkDomain,
        "fields": ["name", "registrar", "dns_servers", "owner", "expires_at", "notes"],
        "date_fields": ["expires_at"],
        "required": ["name"],
    },
    "internet": {
        "model": InternetLink,
        "fields": ["provider", "contract_number", "speed_mbps", "external_ip", "location", "status", "contacts", "notes"],
        "required": ["provider"],
    },
    "telephony": {
        "model": TelephonyLine,
        "fields": ["provider", "number", "line_type", "location", "employee", "status", "notes"],
        "required": ["provider", "number"],
    },
}

SCAN_PORTS = (22, 53, 80, 443, 445, 3389)
MAX_SCAN_HOSTS = 512
MAX_SCAN_TOTAL_HOSTS = 2048


def network_asset_config(kind):
    """Возвращает модель и сериализатор для выбранного типа сетевого актива."""
    config = NETWORK_ASSET_CONFIG.get(kind)
    if not config:
        raise ValueError("Неизвестный тип сетевого объекта")
    return config


def network_asset_to_dict(row):
    """Преобразует сетевой актив в JSON-структуру в зависимости от его модели."""
    data = {"id": row.id}
    for field in [
        "name", "code", "owner", "description", "cidr", "gateway", "purpose", "notes",
        "vlan_id", "address", "hostname", "status", "registrar", "dns_servers",
        "expires_at", "provider", "contract_number", "speed_mbps", "external_ip",
        "location", "contacts", "number", "line_type", "employee", "scan_source",
        "last_seen_at", "last_scanned_at",
    ]:
        if hasattr(row, field):
            value = getattr(row, field)
            data[field] = value.isoformat() if hasattr(value, "isoformat") else (value or "")
    if hasattr(row, "segment_id"):
        data["segment_id"] = row.segment_id or ""
        data["segment_name"] = row.segment.name if row.segment else ""
    if hasattr(row, "network_id"):
        data["network_id"] = row.network_id or ""
        data["network_name"] = str(row.network) if row.network else ""
    if isinstance(row, NetworkIpAddress):
        data["vlan_id"] = row.vlan_id or ""
        data["vlan_name"] = str(row.vlan) if row.vlan else ""
        data["status_label"] = row.get_status_display()
    data["created_at"] = row.created_at.isoformat()
    data["updated_at"] = row.updated_at.isoformat()
    return data


def apply_network_asset_payload(row, kind, data):
    """Заполняет поля сетевого актива из данных запроса."""
    config = network_asset_config(kind)
    for field in config.get("required", []):
        if data.get(field) in ("", None):
            raise ValueError("Заполните обязательные поля")
    for field in config.get("fields", []):
        if field in config.get("date_fields", []):
            setattr(row, field, parse_optional_date(data.get(field), field))
        elif field in ["gateway", "external_ip"]:
            setattr(row, field, data.get(field) or None)
        elif field in ["speed_mbps", "vlan_id"]:
            setattr(row, field, int(data.get(field) or 0))
        else:
            setattr(row, field, data.get(field) or "")
    for field, (model, payload_key) in config.get("fk", {}).items():
        setattr(row, field, parse_fk(model, data.get(payload_key)))


def network_scan_hosts(network):
    """Формирует список IP-адресов сети, которые нужно проверить при сканировании."""
    try:
        parsed = ipaddress.ip_network(network.cidr, strict=False)
    except ValueError:
        raise ValueError("Некорректная сеть CIDR")
    if parsed.num_addresses > MAX_SCAN_HOSTS + 2:
        raise ValueError(f"Сканирование ограничено {MAX_SCAN_HOSTS} адресами за одну сеть")
    hosts = list(parsed.hosts())
    if not hosts and parsed.num_addresses == 1:
        hosts = [parsed.network_address]
    return [str(address) for address in hosts[:MAX_SCAN_HOSTS]]


def probe_network_host(address):
    """Проверяет доступность IP-адреса и пытается определить hostname."""
    hostname = ""
    open_ports = []
    for port in SCAN_PORTS:
        try:
            with socket.create_connection((address, port), timeout=0.35):
                open_ports.append(port)
        except OSError:
            continue
    if not open_ports:
        return None
    try:
        hostname = socket.gethostbyaddr(address)[0]
    except (OSError, socket.herror, socket.gaierror, TimeoutError):
        hostname = ""
    source_parts = []
    if hostname:
        source_parts.append("dns")
    if open_ports:
        source_parts.append("tcp:" + ",".join(str(port) for port in open_ports))
    return {
        "address": address,
        "hostname": hostname,
        "scan_source": "; ".join(source_parts),
    }


def save_scanned_ip(network, result):
    """Сохраняет результат сетевого сканирования в справочник IP-адресов."""
    now = timezone.now()
    row = (
        NetworkIpAddress.objects.filter(address=result["address"], network=network).first()
        or NetworkIpAddress.objects.filter(address=result["address"], network__isnull=True).first()
        or NetworkIpAddress.objects.filter(address=result["address"]).order_by("id").first()
    )
    if not row:
        NetworkIpAddress.objects.create(
            network=network,
            address=result["address"],
            hostname=result["hostname"],
            status=NetworkIpAddress.Status.USED,
            scan_source=result["scan_source"],
            last_seen_at=now,
            last_scanned_at=now,
        )
        return "created"

    changed_fields = []
    if row.network_id != network.id:
        row.network = network
        changed_fields.append("network")
    if result["hostname"] and row.hostname != result["hostname"]:
        row.hostname = result["hostname"]
        changed_fields.append("hostname")
    if row.status != NetworkIpAddress.Status.USED:
        row.status = NetworkIpAddress.Status.USED
        changed_fields.append("status")
    if row.scan_source != result["scan_source"]:
        row.scan_source = result["scan_source"]
        changed_fields.append("scan_source")
    if not changed_fields:
        return "unchanged"
    row.last_seen_at = now
    row.last_scanned_at = now
    row.save(update_fields=[*changed_fields, "last_seen_at", "last_scanned_at", "updated_at"])
    return "updated"


def scan_network(network):
    """Сканирует IP-адреса выбранной сети параллельными проверками."""
    hosts = network_scan_hosts(network)
    summary = {
        "network_id": network.id,
        "network_name": network.name,
        "cidr": network.cidr,
        "scanned": len(hosts),
        "discovered": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
    }
    if not hosts:
        return summary
    results = []
    with ThreadPoolExecutor(max_workers=min(32, len(hosts))) as executor:
        future_map = {executor.submit(probe_network_host, address): address for address in hosts}
        for future in as_completed(future_map):
            result = future.result()
            if result:
                results.append(result)
    for result in results:
        action = save_scanned_ip(network, result)
        summary["discovered"] += 1
        summary[action] += 1
    return summary


def merge_scan_summaries(summaries):
    """Объединяет результаты сканирования нескольких сетей в общую сводку."""
    total = {
        "networks": len(summaries),
        "scanned": 0,
        "discovered": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "items": summaries,
    }
    for item in summaries:
        for key in ["scanned", "discovered", "created", "updated", "unchanged"]:
            total[key] += item.get(key, 0)
    return total


def apply_equipment_payload(equipment, data):
    """Проверяет и применяет поля карточки оборудования из запроса."""
    equipment.inventory_number = (data.get("inventory_number") or "").strip()
    equipment.name = (data.get("name") or "").strip()
    if not equipment.inventory_number or not equipment.name:
        raise ValueError("Заполните инвентарный номер и название")
    equipment.category = parse_fk(Category, data.get("category_id"))
    equipment.location = parse_fk(Location, data.get("location_id"))
    equipment.employee = parse_fk(Employee, data.get("employee_id"))
    equipment.serial_number = (data.get("serial_number") or "").strip()
    equipment.purchase_date = parse_optional_date(data.get("purchase_date"), "purchase_date")
    equipment.warranty_until = parse_optional_date(data.get("warranty_until"), "warranty_until")
    equipment.price = data.get("price") or 0
    equipment.status = data.get("status") or Equipment.Status.IN_USE
    equipment.condition = data.get("condition") or Equipment.Condition.OK
    equipment.ip_address = data.get("ip_address") or None
    equipment.mac_address = (data.get("mac_address") or "").strip()
    equipment.specs = data.get("specs") or ""
    equipment.notes = data.get("notes") or ""


@require_http_methods(["GET"])
def auth_me(request):
    """Возвращает данные текущей сессии пользователя."""
    return JsonResponse({"user": public_user(request.user), "roles": ROLES})


@csrf_exempt
@require_http_methods(["POST"])
def auth_login(request):
    """Выполняет вход локального пользователя или пользователя Active Directory."""
    data = json_body(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if data.get("ad"):
        try:
            profile = active_directory.authenticate(ad_settings(), username, password)
            user, created = active_directory.sync_user(profile)
        except active_directory.ActiveDirectoryError as exc:
            return error(str(exc), 401)
        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)
        AuditLog.objects.create(
            user=user,
            username=user.username,
            action="auth.ad_login.created" if created else "auth.ad_login",
            entity="user",
            entity_id=str(user.id),
        )
        return JsonResponse({"user": public_user(user), "roles": ROLES})

    user = authenticate(request, username=username, password=password)
    if not user:
        return error("Неверный логин или пароль", 401)
    login(request, user)
    AuditLog.objects.create(user=user, username=user.username, action="auth.login", entity="user", entity_id=str(user.id))
    return JsonResponse({"user": public_user(user), "roles": ROLES})


@csrf_exempt
@require_http_methods(["POST"])
def auth_register(request):
    """Регистрирует локальную учетную запись сотрудника."""
    data = json_body(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    if not username or not password or not full_name:
        return error("Заполните логин, пароль и ФИО")
    if User.objects.filter(username=username).exists():
        return error("Пользователь с таким логином уже существует", 409)
    user = User(username=username, full_name=full_name, email=(data.get("email") or "").strip(), role=User.Role.EMPLOYEE)
    user.set_password(password)
    user.save()
    AuditLog.objects.create(user=user, username=user.username, action="auth.register", entity="user", entity_id=str(user.id))
    return JsonResponse({"user": public_user(user)}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout(request):
    """Завершает пользовательскую сессию и фиксирует событие в аудите."""
    if request.user.is_authenticated:
        AuditLog.objects.create(user=request.user, username=request.user.username, action="auth.logout", entity="user", entity_id=str(request.user.id))
    logout(request)
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def dictionaries(request):
    """Возвращает справочники, необходимые для форм интерфейса."""
    denied = require_login(request)
    if denied:
        return denied
    return JsonResponse({
        "categories": list(Category.objects.values("id", "name", "lifetime_months")),
        "locations": list(Location.objects.values("id", "name", "room", "responsible")),
        "employees": [employee_to_dict(row) for row in Employee.objects.all()],
        "roles": ROLES,
        "statuses": choice_rows(Equipment.Status.choices),
        "conditions": choice_rows(Equipment.Condition.choices),
    })


@require_http_methods(["GET"])
def summary(request):
    """Формирует краткую сводку по оборудованию, заявкам, гарантиям и сетевой инфраструктуре."""
    denied = require_permission(request, "equipment:view")
    if denied:
        return denied
    queryset = Equipment.objects.all()
    if request.user.role == User.Role.EMPLOYEE and request.user.employee_id:
        queryset = queryset.filter(employee_id=request.user.employee_id)
    totals = queryset.aggregate(total=Count("id"), value=Sum("price"))
    issues = queryset.filter(condition__in=[Equipment.Condition.SERVICE, Equipment.Condition.BROKEN, Equipment.Condition.LOST]).count()
    warranty_limit = timezone.localdate() + timezone.timedelta(days=60)
    warranty = queryset.filter(warranty_until__isnull=False, warranty_until__lte=warranty_limit).count()
    by_status = [{"name": row["status"], "label": Equipment.Status(row["status"]).label, "count": row["count"]} for row in queryset.values("status").annotate(count=Count("id"))]
    by_category = [{"name": row["category__name"] or "Без категории", "count": row["count"]} for row in queryset.values("category__name").annotate(count=Count("id"))]
    recent = [equipment_to_dict(row) for row in queryset.select_related("category", "location", "employee").order_by("-updated_at")[:5]]
    return JsonResponse({
        "total": totals["total"] or 0,
        "value": float(totals["value"] or 0),
        "issues": issues,
        "warranty": warranty,
        "by_status": by_status,
        "by_category": by_category,
        "recent": recent,
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def equipment_collection(request):
    """Обрабатывает список оборудования и создание новых карточек."""
    if request.method == "GET":
        denied = require_permission(request, "equipment:view")
        if denied:
            return denied
        try:
            queryset = filtered_equipment_queryset(request)
        except ValueError as exc:
            return error(str(exc))
        return JsonResponse([equipment_to_dict(row) for row in queryset[:500]], safe=False)

    denied = require_permission(request, "equipment:write")
    if denied:
        return denied
    try:
        equipment = Equipment()
        apply_equipment_payload(equipment, json_body(request))
        equipment.save()
        add_audit(request, "equipment.created", "equipment", equipment.id, after=equipment_to_dict(equipment))
    except ValueError as exc:
        return error(str(exc))
    return JsonResponse(equipment_to_dict(equipment), status=201)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def equipment_detail(request, pk):
    """Обрабатывает просмотр, изменение и удаление конкретной карточки оборудования."""
    equipment = Equipment.objects.select_related("category", "location", "employee").filter(pk=pk).first()
    if not equipment:
        return error("Оборудование не найдено", 404)
    if request.method == "GET":
        denied = require_permission(request, "equipment:view")
        if denied:
            return denied
        return JsonResponse(equipment_to_dict(equipment))
    if request.method == "DELETE":
        denied = require_permission(request, "equipment:delete")
        if denied:
            return denied
        before = equipment_to_dict(equipment)
        equipment.delete()
        add_audit(request, "equipment.deleted", "equipment", pk, before=before)
        return JsonResponse({"ok": True})
    denied = require_permission(request, "equipment:write")
    if denied:
        return denied
    try:
        before = equipment_to_dict(equipment)
        apply_equipment_payload(equipment, json_body(request))
        equipment.save()
        add_audit(request, "equipment.updated", "equipment", equipment.id, before=before, after=equipment_to_dict(equipment))
    except ValueError as exc:
        return error(str(exc))
    return JsonResponse(equipment_to_dict(equipment))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def service_requests(request):
    """Обрабатывает список заявок и создание новой заявки сотрудником."""
    denied = require_login(request)
    if denied:
        return denied
    if request.method == "GET":
        permissions = ROLE_PERMISSIONS.get(request.user.role, set())
        if "requests:approve" not in permissions and "requests:create" not in permissions:
            return error("Недостаточно прав для операции", 403)
        queryset = ServiceRequest.objects.select_related("user", "employee", "category", "decided_by")
        if "requests:approve" not in permissions:
            queryset = queryset.filter(user=request.user)
        return JsonResponse([service_request_to_dict(row) for row in queryset[:200]], safe=False)
    denied = require_permission(request, "requests:create")
    if denied:
        return denied
    data = json_body(request)
    try:
        title = validate_request_title(data.get("title"))
        row = ServiceRequest.objects.create(
            user=request.user,
            employee=request.user.employee,
            category=parse_fk(Category, data.get("category_id")),
            title=title,
            requested_specs=data.get("requested_specs") or "",
            justification=data.get("justification") or "",
        )
    except ValueError as exc:
        return error(str(exc))
    add_audit(request, "request.created", "service_request", row.id, after=service_request_to_dict(row))
    notify_users_with_permission(
        "requests:approve",
        "Новая заявка",
        f"{request.user.display_name()} отправил заявку «{row.title}».",
        f"requests:{row.id}",
        exclude_user_id=request.user.id,
    )
    return JsonResponse(service_request_to_dict(row), status=201)


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def service_request_detail(request, pk):
    """Обрабатывает изменение статуса, ответ по заявке и архивирование заявителем."""
    denied = require_login(request)
    if denied:
        return denied
    row = ServiceRequest.objects.select_related("user", "employee", "category", "decided_by").filter(pk=pk).first()
    if not row:
        return error("Заявка не найдена", 404)
    permissions = ROLE_PERMISSIONS.get(request.user.role, set())
    can_approve = "requests:approve" in permissions
    can_edit_own = "requests:create" in permissions and row.user_id == request.user.id
    if not can_approve and not can_edit_own:
        return error("Недостаточно прав для операции", 403)
    if request.method == "GET":
        return JsonResponse(service_request_to_dict(row))

    before = service_request_to_dict(row)
    data = json_body(request)
    previous_reason = row.decision_reason
    previous_status = row.status

    own_fields = {"title", "category_id", "requested_specs", "justification", "archived_by_requester"}
    approval_fields = {"status", "decision_reason", "take_in_work"}
    if not can_edit_own and own_fields.intersection(data):
        return error("Можно редактировать только свои заявки", 403)
    if not can_approve and approval_fields.intersection(data):
        return error("Недостаточно прав для изменения статуса", 403)

    if can_edit_own:
        if "title" in data:
            try:
                row.title = validate_request_title(data.get("title"))
            except ValueError as exc:
                return error(str(exc))
        if "category_id" in data:
            try:
                row.category = parse_fk(Category, data.get("category_id"))
            except ValueError as exc:
                return error(str(exc))
        if "requested_specs" in data:
            row.requested_specs = data.get("requested_specs") or ""
        if "justification" in data:
            row.justification = data.get("justification") or ""
        if "archived_by_requester" in data:
            archive = bool(data.get("archived_by_requester"))
            if archive and row.status != ServiceRequest.Status.DONE:
                return error("В архив можно перенести только выполненную заявку")
            row.archived_by_requester = archive

    if can_approve and approval_fields.intersection(data):
        if data.get("take_in_work"):
            if row.decided_by_id and row.decided_by_id != request.user.id:
                return error("Заявку уже взял в работу другой сотрудник")
            if row.status in {ServiceRequest.Status.DONE, ServiceRequest.Status.REJECTED}:
                return error("Завершенную или отклоненную заявку нельзя взять в работу")
            row.status = ServiceRequest.Status.APPROVED
            row.decided_by = request.user
            row.decided_at = timezone.now()
        else:
            next_status = data.get("status") or row.status
            valid_statuses = {value for value, _label in ServiceRequest.Status.choices}
            if next_status not in valid_statuses:
                return error("Неверный статус заявки")
            row.status = next_status
            row.decision_reason = data.get("decision_reason", row.decision_reason) or ""
            if row.status != previous_status or row.decision_reason != previous_reason:
                row.decided_at = timezone.now()

    try:
        row.save()
    except ValueError as exc:
        return error(str(exc))
    row = ServiceRequest.objects.select_related("user", "employee", "category", "decided_by").get(pk=row.pk)
    after = service_request_to_dict(row)
    add_audit(request, "request.updated", "service_request", row.id, before=before, after=after)
    if row.status != previous_status or row.decision_reason != previous_reason:
        create_notification(
            row.user,
            "Статус заявки изменен",
            f"Заявка «{row.title}» теперь: {row.get_status_display()}.",
            f"requests:{row.id}",
        )
    return JsonResponse(after)


def cabinet_payload(user):
    """Собирает данные личного кабинета пользователя."""
    user = User.objects.select_related("employee").get(pk=user.pk)
    equipment = Equipment.objects.select_related("category", "location", "employee")
    if user.employee_id:
        equipment = equipment.filter(employee_id=user.employee_id)
    else:
        equipment = equipment.none()
    employee = user.employee
    return {
        "user": user_to_dict(user),
        "employee": employee_to_dict(employee) if employee else None,
        "equipment": [equipment_to_dict(row) for row in equipment],
    }


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def cabinet(request):
    """Возвращает или обновляет данные личного кабинета текущего пользователя."""
    denied = require_login(request)
    if denied:
        return denied
    if request.method == "GET":
        return JsonResponse(cabinet_payload(request.user))
    user = User.objects.select_related("employee").get(pk=request.user.pk)
    before = user_to_dict(user)
    try:
        data = json_body(request)
        apply_avatar_payload(user, data)
        if LOCAL_PROFILE_FIELDS.intersection(data):
            apply_local_profile_payload(user, data)
    except PermissionError as exc:
        return error(str(exc), 403)
    except ValueError as exc:
        return error(str(exc))
    user.save()
    after = user_to_dict(User.objects.select_related("employee").get(pk=user.pk))
    add_audit(request, "user.profile.updated", "user", user.id, before=before, after=after)
    return JsonResponse(cabinet_payload(user))


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def ad_settings_view(request):
    """Возвращает и сохраняет настройки Active Directory через API."""
    denied = require_permission(request, "users:manage")
    if denied:
        return denied
    if request.method == "GET":
        return JsonResponse(ad_settings())
    try:
        settings = save_ad_settings(json_body(request))
    except ValueError as exc:
        return error(str(exc))
    add_audit(request, "ad.settings.updated", "app_setting", "ad")
    return JsonResponse(settings)


@csrf_exempt
@require_http_methods(["POST"])
def ad_test_connection(request):
    """Запускает проверку соединения с Active Directory и пишет результат в аудит."""
    denied = require_permission(request, "users:manage")
    if denied:
        return denied
    data = json_body(request)
    try:
        result = active_directory.test_connection({**ad_settings(), **data})
    except (active_directory.ActiveDirectoryError, ValueError) as exc:
        return error(str(exc), 400)
    add_audit(request, "ad.connection.tested", "app_setting", "ad")
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def network_scan(request):
    """Запускает сканирование одной сети или всех настроенных сетей."""
    denied = require_permission(request, "network:scan")
    if denied:
        return denied
    data = json_body(request)
    kind = data.get("kind") or "network"
    try:
        if kind == "all_networks":
            networks = list(Network.objects.all()[:50])
            if not networks:
                return error("Добавьте хотя бы одну сеть для сканирования")
            prepared = [(network, network_scan_hosts(network)) for network in networks]
            total_hosts = sum(len(hosts) for _network, hosts in prepared)
            if total_hosts > MAX_SCAN_TOTAL_HOSTS:
                return error(f"Общее сканирование ограничено {MAX_SCAN_TOTAL_HOSTS} адресами")
            summary = merge_scan_summaries([scan_network(network) for network, _hosts in prepared])
        else:
            network = Network.objects.filter(pk=data.get("network_id")).first()
            if not network:
                return error("Сеть для сканирования не найдена", 404)
            summary = scan_network(network)
    except ValueError as exc:
        return error(str(exc))
    add_audit(request, "network.scan", "network", data.get("network_id") or kind, after=summary)
    return JsonResponse({"ok": True, "summary": summary})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def network_assets(request):
    """Обрабатывает список сетевых активов и создание новых записей."""
    denied = require_permission(request, "network:manage")
    if denied:
        return denied
    if request.method == "GET":
        return JsonResponse({
            kind: [network_asset_to_dict(row) for row in config["model"].objects.all()[:500]]
            for kind, config in NETWORK_ASSET_CONFIG.items()
        })
    data = json_body(request)
    kind = data.get("kind") or ""
    try:
        config = network_asset_config(kind)
        row = config["model"]()
        apply_network_asset_payload(row, kind, data)
        row.save()
    except ValueError as exc:
        return error(str(exc))
    after = network_asset_to_dict(row)
    add_audit(request, "network.created", kind, row.id, after=after)
    return JsonResponse(after, status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def network_asset_detail(request, kind, pk):
    """Обрабатывает изменение и удаление конкретного сетевого актива."""
    denied = require_permission(request, "network:manage")
    if denied:
        return denied
    try:
        config = network_asset_config(kind)
    except ValueError as exc:
        return error(str(exc), 404)
    row = config["model"].objects.filter(pk=pk).first()
    if not row:
        return error("Сетевой объект не найден", 404)
    before = network_asset_to_dict(row)
    if request.method == "DELETE":
        row.delete()
        add_audit(request, "network.deleted", kind, pk, before=before)
        return JsonResponse({"ok": True})
    try:
        apply_network_asset_payload(row, kind, json_body(request))
        row.save()
    except ValueError as exc:
        return error(str(exc))
    after = network_asset_to_dict(row)
    add_audit(request, "network.updated", kind, row.id, before=before, after=after)
    return JsonResponse(after)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def movements_collection(request):
    """Возвращает список перемещений и создает новое перемещение оборудования."""
    denied = require_permission(request, "lifecycle:manage")
    if denied:
        return denied
    if request.method == "GET":
        rows = Movement.objects.select_related("equipment", "from_location", "to_location", "employee").order_by("-moved_at", "-id")[:300]
        return JsonResponse([movement_to_dict(row) for row in rows], safe=False)

    data = json_body(request)
    try:
        row = save_movement_payload(Movement(created_by=request.user), data, require_equipment=True)
    except ValueError as exc:
        return error(str(exc))
    add_audit(request, "movement.created", "movement", row.id, after=movement_to_dict(row))
    return JsonResponse(movement_to_dict(row), status=201)


def save_movement_payload(row, data, require_equipment=False):
    """Проверяет и сохраняет поля перемещения оборудования."""
    if require_equipment or "equipment_id" in data:
        equipment = Equipment.objects.select_related("location", "employee").filter(pk=data.get("equipment_id")).first()
        if not equipment:
            raise ValueError("Оборудование не найдено")
        row.equipment = equipment
        row.inventory_number = equipment.inventory_number
        row.equipment_name = equipment.name
    if "from_location_id" in data:
        row.from_location = parse_fk(Location, data.get("from_location_id"))
    if "to_location_id" in data:
        row.to_location = parse_fk(Location, data.get("to_location_id"))
    if "employee_id" in data:
        row.employee = parse_fk(Employee, data.get("employee_id"))
    if require_equipment or "moved_at" in data:
        row.moved_at = parse_movement_datetime(data.get("moved_at"))
    if require_equipment or "status" in data:
        status = data.get("status") or "planned"
        if status not in MOVEMENT_STATUSES:
            raise ValueError("Неверный статус перемещения")
        row.status = status
    if "archived" in data:
        archived = bool(data.get("archived"))
        if archived and row.status != "done":
            raise ValueError("В архив можно перенести только выполненное перемещение")
        row.archived = archived
    if row.archived and row.status != "done":
        raise ValueError("Архивное перемещение должно быть выполненным")
    row.save()
    if row.status == "done":
        equipment = row.equipment
        equipment.location = row.to_location
        equipment.employee = row.employee
        equipment.save(update_fields=["location", "employee", "updated_at"])
    return row


@csrf_exempt
@require_http_methods(["PATCH"])
def movement_detail(request, pk):
    """Обрабатывает изменение и архивирование записи перемещения."""
    denied = require_permission(request, "lifecycle:manage")
    if denied:
        return denied
    row = Movement.objects.select_related("equipment", "from_location", "to_location", "employee").filter(pk=pk).first()
    if not row:
        return error("Перемещение не найдено", 404)
    before = movement_to_dict(row)
    try:
        save_movement_payload(row, json_body(request))
    except ValueError as exc:
        return error(str(exc))
    row = Movement.objects.select_related("equipment", "from_location", "to_location", "employee").get(pk=row.pk)
    after = movement_to_dict(row)
    add_audit(request, "movement.updated", "movement", row.id, before=before, after=after)
    return JsonResponse(after)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def writeoffs_collection(request):
    """Возвращает список списаний и создает новое списание оборудования."""
    denied = require_permission(request, "lifecycle:manage")
    if denied:
        return denied
    if request.method == "GET":
        rows = WriteOff.objects.select_related("equipment").order_by("-writeoff_date", "-id")[:300]
        return JsonResponse([writeoff_to_dict(row) for row in rows], safe=False)

    data = json_body(request)
    try:
        row = save_writeoff_payload(WriteOff(created_by=request.user), data, require_equipment=True)
    except ValueError as exc:
        return error(str(exc))
    add_audit(request, "writeoff.created", "writeoff", row.id, after=writeoff_to_dict(row))
    return JsonResponse(writeoff_to_dict(row), status=201)


def save_writeoff_payload(row, data, require_equipment=False):
    """Проверяет и сохраняет поля акта списания оборудования."""
    if require_equipment or "equipment_id" in data:
        equipment = Equipment.objects.filter(pk=data.get("equipment_id")).first()
        if not equipment:
            raise ValueError("Оборудование не найдено")
        row.equipment = equipment
        row.inventory_number = equipment.inventory_number
        row.equipment_name = equipment.name
    if require_equipment or "reason" in data:
        row.reason = data.get("reason") or ""
    if require_equipment or "writeoff_date" in data:
        row.writeoff_date = parse_optional_date(data.get("writeoff_date") or timezone.localdate(), "writeoff_date")
    if require_equipment or "commission" in data:
        row.commission = data.get("commission") or ""
    if require_equipment or "status" in data:
        status = data.get("status") or "prepared"
        if status not in WRITEOFF_STATUSES:
            raise ValueError("Неверный статус списания")
        row.status = status
    if "archived" in data:
        archived = bool(data.get("archived"))
        if archived and row.status != "written_off":
            raise ValueError("В архив можно перенести только выполненное списание")
        row.archived = archived
    if row.archived and row.status != "written_off":
        raise ValueError("Архивное списание должно быть выполненным")
    row.save()
    if row.status == "written_off":
        equipment = row.equipment
        equipment.status = Equipment.Status.WRITTEN_OFF
        equipment.save(update_fields=["status", "updated_at"])
    return row


@csrf_exempt
@require_http_methods(["PATCH"])
def writeoff_detail(request, pk):
    """Обрабатывает изменение и архивирование записи списания."""
    denied = require_permission(request, "lifecycle:manage")
    if denied:
        return denied
    row = WriteOff.objects.select_related("equipment").filter(pk=pk).first()
    if not row:
        return error("Списание не найдено", 404)
    before = writeoff_to_dict(row)
    try:
        save_writeoff_payload(row, json_body(request))
    except ValueError as exc:
        return error(str(exc))
    row = WriteOff.objects.select_related("equipment").get(pk=row.pk)
    after = writeoff_to_dict(row)
    add_audit(request, "writeoff.updated", "writeoff", row.id, before=before, after=after)
    return JsonResponse(after)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def inventory_sessions(request):
    """Возвращает список инвентаризаций и создает новую сессию."""
    denied = require_permission(request, "inventory:write")
    if denied:
        return denied
    if request.method == "GET":
        rows = InventorySession.objects.prefetch_related("checks").order_by("-started_at", "-id")[:100]
        return JsonResponse([inventory_session_to_dict(row) for row in rows], safe=False)

    title = (json_body(request).get("title") or "").strip()
    if not title:
        return error("Введите название инвентаризации")
    row = InventorySession.objects.create(title=title)
    add_audit(request, "inventory_session.created", "inventory_session", row.id)
    return JsonResponse(inventory_session_to_dict(row), status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
def inventory_session_detail(request, pk):
    """Обновляет статус или архивный признак сессии инвентаризации."""
    denied = require_permission(request, "inventory:write")
    if denied:
        return denied
    row = InventorySession.objects.prefetch_related("checks").filter(pk=pk).first()
    if not row:
        return error("Сессия не найдена", 404)
    before = inventory_session_to_dict(row)
    data = json_body(request)
    if "archived" in data:
        row.archived = bool(data.get("archived"))
    if "status" in data:
        row.status = (data.get("status") or row.status).strip() or row.status
    row.save()
    after = inventory_session_to_dict(row)
    add_audit(request, "inventory_session.updated", "inventory_session", row.id, before=before, after=after)
    return JsonResponse(after)


@require_http_methods(["GET"])
def inventory_session_report(request, pk):
    """Формирует отчет по проверенному и отсутствующему оборудованию в сессии."""
    denied = require_permission(request, "inventory:write")
    if denied:
        return denied
    session = InventorySession.objects.filter(pk=pk).first()
    if not session:
        return error("Сессия не найдена", 404)
    checks = InventoryCheck.objects.select_related("equipment", "equipment__category", "equipment__location", "equipment__employee").filter(session=session)
    checked_ids = set(checks.values_list("equipment_id", flat=True))
    checked = []
    for row in checks:
        item = equipment_to_dict(row.equipment)
        item.update({
            "result": row.result,
            "result_label": INVENTORY_RESULTS.get(row.result, row.result),
            "condition": row.condition,
            "condition_label": dict(Equipment.Condition.choices).get(row.condition, row.condition),
            "checked_at": row.checked_at.isoformat(),
        })
        checked.append(item)
    missing = Equipment.objects.select_related("category", "location", "employee").exclude(id__in=checked_ids)
    return JsonResponse({
        "session": inventory_session_to_dict(session),
        "checked": checked,
        "missing": [equipment_to_dict(row) for row in missing[:500]],
    })


@csrf_exempt
@require_http_methods(["POST"])
def inventory_session_checks(request, pk):
    """Сохраняет результат проверки оборудования в рамках инвентаризации."""
    denied = require_permission(request, "inventory:write")
    if denied:
        return denied
    session = InventorySession.objects.filter(pk=pk).first()
    equipment = Equipment.objects.filter(pk=json_body(request).get("equipment_id")).first()
    if not session or not equipment:
        return error("Сессия или оборудование не найдены", 404)
    if session.archived:
        return error("Архивную инвентаризацию нельзя изменять")
    data = json_body(request)
    row, _ = InventoryCheck.objects.update_or_create(
        session=session,
        equipment=equipment,
        defaults={
            "result": data.get("result") or "found",
            "condition": data.get("condition") or equipment.condition,
        },
    )
    add_audit(request, "inventory_check.saved", "inventory_check", row.id)
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def reports(request):
    """Формирует аналитические данные для раздела отчетов."""
    denied = require_permission(request, "reports:view")
    if denied:
        return denied
    queryset = Equipment.objects.select_related("category", "location", "employee")
    totals = queryset.aggregate(total=Count("id"), value=Sum("price"))
    today = timezone.localdate()
    warranty_limit = today + timezone.timedelta(days=60)
    warranty = queryset.filter(warranty_until__isnull=False, warranty_until__lte=warranty_limit)
    age_rows = {"0-1 год": 0, "1-3 года": 0, "3-5 лет": 0, "5+ лет": 0}
    for row in queryset:
        if not row.purchase_date:
            continue
        years = (today - row.purchase_date).days / 365.25
        if years < 1:
            age_rows["0-1 год"] += 1
        elif years < 3:
            age_rows["1-3 года"] += 1
        elif years < 5:
            age_rows["3-5 лет"] += 1
        else:
            age_rows["5+ лет"] += 1
    max_age = max(age_rows.values() or [1]) or 1
    status_labels = dict(Equipment.Status.choices)
    condition_labels = dict(Equipment.Condition.choices)
    movement_rows = Movement.objects.select_related("equipment", "from_location", "to_location", "employee").order_by("-moved_at", "-id")[:12]
    writeoff_rows = WriteOff.objects.select_related("equipment").order_by("-writeoff_date", "-id")[:12]
    inventory_rows = InventorySession.objects.prefetch_related("checks").order_by("-started_at", "-id")[:12]
    total_equipment = totals["total"] or 0
    max_category = max([row["count"] for row in queryset.values("category__name").annotate(count=Count("id"))] or [1]) or 1
    max_location = max([row["count"] for row in queryset.values("location__name", "location__room").annotate(count=Count("id"))] or [1]) or 1
    max_employee = max([row["count"] for row in queryset.values("employee__full_name", "employee__department").annotate(count=Count("id"))] or [1]) or 1
    expiring_domains = NetworkDomain.objects.filter(expires_at__isnull=False, expires_at__lte=today + timezone.timedelta(days=90)).order_by("expires_at", "name")[:20]
    return JsonResponse({
        "total": totals["total"] or 0,
        "value": float(totals["value"] or 0),
        "storage": queryset.filter(status=Equipment.Status.STORAGE).count(),
        "issues": queryset.filter(condition__in=[Equipment.Condition.SERVICE, Equipment.Condition.BROKEN, Equipment.Condition.LOST]).count(),
        "age": [{"name": name, "count": count, "percent": count / max_age * 100} for name, count in age_rows.items()],
        "warranty": [equipment_to_dict(row) for row in warranty[:100]],
        "status_rows": [
            {
                "name": status_labels.get(row["status"], row["status"]),
                "count": row["count"],
                "value": float(row["value"] or 0),
                "percent": (row["count"] / total_equipment * 100) if total_equipment else 0,
            }
            for row in queryset.values("status").annotate(count=Count("id"), value=Sum("price")).order_by("status")
        ],
        "condition_rows": [
            {
                "name": condition_labels.get(row["condition"], row["condition"]),
                "count": row["count"],
                "percent": (row["count"] / total_equipment * 100) if total_equipment else 0,
            }
            for row in queryset.values("condition").annotate(count=Count("id")).order_by("condition")
        ],
        "category_rows": [
            {
                "name": row["category__name"] or "Без категории",
                "count": row["count"],
                "value": float(row["value"] or 0),
                "percent": row["count"] / max_category * 100,
            }
            for row in queryset.values("category__name").annotate(count=Count("id"), value=Sum("price")).order_by("-count", "category__name")[:20]
        ],
        "location_rows": [
            {
                "name": " ".join(part for part in [row["location__name"], row["location__room"]] if part) or "Место не указано",
                "count": row["count"],
                "value": float(row["value"] or 0),
                "percent": row["count"] / max_location * 100,
            }
            for row in queryset.values("location__name", "location__room").annotate(count=Count("id"), value=Sum("price")).order_by("-count", "location__name")[:20]
        ],
        "employee_rows": [
            {
                "name": row["employee__full_name"] or "Не закреплено",
                "department": row["employee__department"] or "",
                "count": row["count"],
                "percent": row["count"] / max_employee * 100,
            }
            for row in queryset.values("employee__full_name", "employee__department").annotate(count=Count("id")).order_by("-count", "employee__full_name")[:20]
        ],
        "movement_status_rows": [
            {"name": MOVEMENT_STATUSES.get(row["status"], row["status"]), "count": row["count"]}
            for row in Movement.objects.values("status").annotate(count=Count("id")).order_by("status")
        ],
        "recent_movements": [movement_to_dict(row) for row in movement_rows],
        "writeoff_status_rows": [
            {"name": WRITEOFF_STATUSES.get(row["status"], row["status"]), "count": row["count"]}
            for row in WriteOff.objects.values("status").annotate(count=Count("id")).order_by("status")
        ],
        "recent_writeoffs": [writeoff_to_dict(row) for row in writeoff_rows],
        "inventory_rows": [inventory_session_to_dict(row) for row in inventory_rows],
        "network_summary": {
            "segments": InfrastructureSegment.objects.count(),
            "networks": Network.objects.count(),
            "vlans": NetworkVlan.objects.count(),
            "ip_total": NetworkIpAddress.objects.count(),
            "ip_used": NetworkIpAddress.objects.filter(status=NetworkIpAddress.Status.USED).count(),
            "ip_free": NetworkIpAddress.objects.filter(status=NetworkIpAddress.Status.FREE).count(),
            "ip_reserved": NetworkIpAddress.objects.filter(status=NetworkIpAddress.Status.RESERVED).count(),
            "domains": NetworkDomain.objects.count(),
            "internet_links": InternetLink.objects.count(),
            "telephony_lines": TelephonyLine.objects.count(),
        },
        "expiring_domains": [
            {"name": row.name, "registrar": row.registrar, "expires_at": row.expires_at.isoformat() if row.expires_at else ""}
            for row in expiring_domains
        ],
    })


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def notifications_collection(request):
    """Возвращает уведомления пользователя и обрабатывает массовые действия с ними."""
    denied = require_login(request)
    if denied:
        return denied
    if request.method == "DELETE":
        Notification.objects.filter(user=request.user).delete()
        return JsonResponse({"ok": True})
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({"ok": True})
    return JsonResponse(notification_rows(request.user), safe=False)


@require_http_methods(["GET"])
def notifications_stream(request):
    """Открывает SSE-поток для доставки новых уведомлений без перезагрузки страницы."""
    denied = require_login(request)
    if denied:
        return denied

    user_id = request.user.id

    def events():
        """Генерирует события SSE при изменении списка уведомлений пользователя."""
        last_signature = None
        yield "retry: 3000\n\n"
        for _ in range(600):
            rows = notification_rows(request.user)
            signature = (
                rows[0]["id"] if rows else 0,
                len(rows),
                sum(1 for row in rows if not row["is_read"]),
            )
            if signature != last_signature:
                last_signature = signature
                payload = json.dumps(rows, ensure_ascii=False)
                yield f"event: notifications\ndata: {payload}\n\n"
            time.sleep(1)
            if not User.objects.filter(id=user_id, is_active=True).exists():
                break

    response = StreamingHttpResponse(events(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def notification_read(request, pk):
    """Помечает конкретное уведомление пользователя как прочитанное."""
    denied = require_login(request)
    if denied:
        return denied
    Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def users_collection(request):
    """Возвращает список пользователей для административного раздела."""
    denied = require_permission(request, "users:manage")
    if denied:
        return denied
    rows = User.objects.select_related("employee").order_by("username", "id")
    return JsonResponse([user_to_dict(row) for row in rows], safe=False)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def user_detail(request, pk):
    """Обрабатывает изменение профиля, роли, пароля и удаление пользователя."""
    denied = require_permission(request, "users:manage")
    if denied:
        return denied
    user = User.objects.select_related("employee").filter(pk=pk).first()
    if not user:
        return error("Пользователь не найден", 404)
    if request.method == "DELETE":
        before = user_to_dict(user)
        user.delete()
        add_audit(request, "user.deleted", "user", pk, before=before)
        return JsonResponse({"ok": True})
    before = user_to_dict(user)
    data = json_body(request)
    if data.get("role") in ROLE_PERMISSIONS:
        user.role = data["role"]
    try:
        if "employee_id" in data:
            user.employee = parse_fk(Employee, data.get("employee_id"))
        apply_avatar_payload(user, data)
        if LOCAL_PROFILE_FIELDS.intersection(data):
            apply_local_profile_payload(user, data)
    except PermissionError as exc:
        return error(str(exc), 403)
    except ValueError as exc:
        return error(str(exc))
    if "two_factor_enabled" in data:
        user.two_factor_enabled = bool(data["two_factor_enabled"])
    password = data.get("password")
    if password:
        if len(password) < 6:
            return error("Пароль должен содержать не менее 6 символов")
        user.set_password(password)
    user.save()
    after = user_to_dict(user)
    add_audit(request, "user.updated", "user", user.id, before=before, after=after)
    return JsonResponse(after)


@require_http_methods(["GET"])
def audit_collection(request):
    """Возвращает последние записи журнала аудита."""
    denied = require_permission(request, "audit:view")
    if denied:
        return denied
    rows = AuditLog.objects.order_by("-created_at", "-id")[:300]
    return JsonResponse([audit_to_dict(row) for row in rows], safe=False)


def export_equipment_rows(request):
    """Готовит строки оборудования для экспорта в табличные форматы."""
    return [
        {
            "inventory_number": row.inventory_number,
            "name": row.name,
            "category": row.category.name if row.category else "",
            "location": str(row.location) if row.location else "",
            "employee": row.employee.full_name if row.employee else "",
            "status": row.get_status_display(),
            "condition": row.get_condition_display(),
        }
        for row in filtered_equipment_queryset(request).order_by("inventory_number", "name")
    ]


def export_equipment_xls(request):
    """Формирует HTML-таблицу, открываемую как Excel-файл."""
    columns = [
        ("inventory_number", "Инвентарный номер"),
        ("name", "Наименование"),
        ("category", "Категория"),
        ("location", "Место"),
        ("employee", "Сотрудник"),
        ("status", "Статус"),
        ("condition", "Состояние"),
    ]
    rows = export_equipment_rows(request)
    table_head = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    table_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row[key] or ''))}</td>" for key, _ in columns)
        table_rows.append(f"<tr>{cells}</tr>")
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>body{font-family:Arial,sans-serif}table{border-collapse:collapse}"
        "th,td{border:1px solid #999;padding:6px 8px}th{background:#eef3f8}</style>"
        "</head><body><table><thead><tr>"
        f"{table_head}</tr></thead><tbody>{''.join(table_rows)}</tbody></table></body></html>"
    )
    response = HttpResponse(html, content_type="application/vnd.ms-excel; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="equipment.xls"'
    return response


def export_equipment_pdf(request):
    """Формирует PDF-отчет по оборудованию средствами ReportLab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    except ImportError:
        return error("Для экспорта PDF установите зависимости из requirements.txt", 500)

    font_name = "Helvetica"
    for font_path in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ]:
        if font_path.exists():
            font_name = "EquipmentExportFont"
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            break

    columns = ["Инв. номер", "Наименование", "Категория", "Место", "Сотрудник", "Статус", "Состояние"]
    rows = export_equipment_rows(request)
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontName = font_name
    cell_style.fontSize = 8
    cell_style.leading = 10
    data = [[Paragraph(escape(value), cell_style) for value in columns]]
    for row in rows:
        data.append([
            Paragraph(escape(str(row["inventory_number"] or "")), cell_style),
            Paragraph(escape(str(row["name"] or "")), cell_style),
            Paragraph(escape(str(row["category"] or "")), cell_style),
            Paragraph(escape(str(row["location"] or "")), cell_style),
            Paragraph(escape(str(row["employee"] or "")), cell_style),
            Paragraph(escape(str(row["status"] or "")), cell_style),
            Paragraph(escape(str(row["condition"] or "")), cell_style),
        ])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    table = Table(data, repeatRows=1, colWidths=[74, 140, 110, 120, 120, 86, 86])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17202a")),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#9aa8b6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
    ]))
    doc.build([table])
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="equipment.pdf"'
    return response


@require_http_methods(["GET"])
def export_equipment(request, fmt):
    """Выбирает формат экспорта оборудования и возвращает готовый файл."""
    denied = require_permission(request, "reports:view")
    if denied:
        return denied
    try:
        if fmt == "xls":
            return export_equipment_xls(request)
        if fmt == "pdf":
            return export_equipment_pdf(request)
    except ValueError as exc:
        return error(str(exc))
    return error("Неподдерживаемый формат экспорта", 404)
