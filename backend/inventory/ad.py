"""Интеграция с Active Directory: проверка соединения, вход и синхронизация пользователя."""

import platform
import re
import socket
import subprocess
import ctypes
import locale
from datetime import datetime
from urllib.parse import urlparse

from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.utils import timezone

from .models import Employee, User

try:
    import ldap3
    from ldap3.core.exceptions import LDAPException
    from ldap3.utils.conv import escape_filter_chars
except ImportError:  # pragma: no cover - optional deployment package
    ldap3 = None
    LDAPException = Exception
    escape_filter_chars = lambda value: value


LDAP_ATTRIBUTES = [
    "sAMAccountName",
    "userPrincipalName",
    "displayName",
    "cn",
    "mail",
    "department",
    "telephoneNumber",
    "mobile",
    "givenName",
    "sn",
]


class ActiveDirectoryError(Exception):
    """Исключение для ошибок настройки, подключения и синхронизации Active Directory."""
    pass


def is_enabled(value):
    """Преобразует строковое значение настройки в логический признак включения."""
    return str(value).lower() in {"1", "true", "yes", "on"}


def normalize_settings(data):
    """Приводит настройки Active Directory к единому формату для подключения и проверки."""
    values = data or {}
    use_ssl = bool(values.get("use_ssl"))
    server = (values.get("server") or values.get("controller") or "").strip()
    domain = (values.get("domain") or "").strip()
    parsed_host, parsed_port, parsed_ssl = parse_target(server or domain, values.get("port"), use_ssl)
    use_ssl = parsed_ssl
    port = parsed_port
    return {
        "enabled": bool(values.get("enabled")),
        "domain": domain,
        "server": parsed_host if server else "",
        "controller": parsed_host if server else "",
        "port": port,
        "use_ssl": use_ssl,
        "base_dn": (values.get("base_dn") or "").strip(),
        "bind_user": (values.get("bind_user") or "").strip(),
    }


def parse_target(value, port=None, use_ssl=False):
    """Разбирает адрес контроллера домена, порт и признак LDAPS из введенной строки."""
    raw = (value or "").strip()
    default_port = 636 if use_ssl else 389
    parsed_port = int(port or default_port)
    if raw and "://" in raw:
        parsed = urlparse(raw)
        host = parsed.hostname or ""
        parsed_ssl = parsed.scheme.lower() == "ldaps"
        parsed_port = parsed.port or (636 if parsed_ssl else 389)
        return host, parsed_port, parsed_ssl
    if raw and ":" in raw and raw.rsplit(":", 1)[-1].isdigit():
        host, parsed_port = raw.rsplit(":", 1)
        return host.strip(), int(parsed_port), use_ssl
    return raw, parsed_port, use_ssl


def ad_connection_target(settings):
    """Определяет хост и порт Active Directory и проверяет корректность настроек."""
    host = (settings.get("server") or settings.get("controller") or settings.get("domain") or "").strip()
    use_ssl = bool(settings.get("use_ssl"))
    host, port, use_ssl = parse_target(host, settings.get("port"), use_ssl)
    if not host:
        raise ActiveDirectoryError("AD is not configured: specify a domain or domain controller")
    if port < 1 or port > 65535:
        raise ActiveDirectoryError("Invalid AD controller port")
    settings["use_ssl"] = use_ssl
    return host, port


def check_tcp_port(host, port, timeout=3):
    """Проверяет доступность TCP-порта контроллера домена и возвращает время ответа."""
    started = datetime.now()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((datetime.now() - started).total_seconds() * 1000, 2)
            return {"ok": True, "latency_ms": latency_ms, "message": f"TCP {host}:{port} is reachable"}
    except OSError as exc:
        return {"ok": False, "latency_ms": None, "message": f"TCP {host}:{port} is unreachable: {exc}"}


def windows_console_encoding():
    """Определяет кодировку консоли Windows для корректного чтения вывода команд."""
    if "windows" not in platform.system().lower():
        return locale.getpreferredencoding(False) or "utf-8"
    try:
        code_page = ctypes.windll.kernel32.GetOEMCP()
        return f"cp{code_page}"
    except Exception:
        return "cp866"


def decode_command_output(stdout=b"", stderr=b""):
    """Декодирует stdout и stderr внешней команды с учетом возможных кодировок Windows."""
    raw = (stdout or b"") + (stderr or b"")
    for encoding in [windows_console_encoding(), locale.getpreferredencoding(False), "utf-8", "cp866"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def windows_domain_controller_probe(domain):
    """Проверяет доступность контроллера домена штатной командой nltest на Windows."""
    if not domain or "windows" not in platform.system().lower():
        return {"ok": False, "message": "nltest check is available only on Windows when a domain is specified"}
    try:
        result = subprocess.run(["nltest", f"/dsgetdc:{domain}"], capture_output=True, text=False, timeout=6)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "message": str(exc)}
    output = decode_command_output(result.stdout, result.stderr)
    return {"ok": result.returncode == 0, "message": output[-1200:] or "nltest finished without output"}


def ldap_bind(settings, login, password):
    """Проверяет учетные данные через LDAP bind без сохранения пароля в системе."""
    if ldap3 is None:
        return {"ok": False, "available": False, "message": "Install ldap3 to use LDAP bind"}
    host, port = ad_connection_target(settings)
    try:
        server = ldap3.Server(host, port=port, use_ssl=bool(settings.get("use_ssl")), connect_timeout=5)
        conn = ldap3.Connection(server, user=login, password=password, auto_bind=True, receive_timeout=5)
        conn.unbind()
        return {"ok": True, "available": True, "message": "LDAP bind succeeded"}
    except Exception as exc:
        return {"ok": False, "available": True, "message": str(exc)}


def test_connection(data=None):
    """Выполняет диагностику подключения к Active Directory для экрана настроек."""
    settings = normalize_settings(data or {})
    host, port = ad_connection_target(settings)
    checks = {
        "dns": {"ok": False, "message": ""},
        "tcp": check_tcp_port(host, port),
        "nltest": windows_domain_controller_probe(settings.get("domain")),
        "bind": {"ok": False, "available": False, "message": "Bind user password is not specified"},
    }
    try:
        checks["dns"] = {"ok": True, "message": socket.gethostbyname(host)}
    except OSError as exc:
        checks["dns"] = {"ok": False, "message": str(exc)}

    bind_user = settings.get("bind_user") or ""
    bind_password = (data or {}).get("bind_password") or ""
    if bind_user and bind_password:
        checks["bind"] = ldap_bind(settings, bind_user, bind_password)

    ok = checks["tcp"]["ok"] and (not bind_user or checks["bind"]["ok"] or not bind_password)
    return {
        "ok": ok,
        "message": "AD connection check completed" if ok else "AD connection check failed",
        "settings": public_settings(settings),
        "checks": checks,
        "checked_at": timezone.now().isoformat(),
    }


def public_settings(settings):
    """Возвращает настройки Active Directory в безопасном виде без секретных полей."""
    values = normalize_settings(settings)
    values.pop("bind_password", None)
    return values


def normalize_ad_username(username):
    """Удаляет доменную часть и лишние пробелы из имени пользователя Active Directory."""
    value = (username or "").strip()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return re.sub(r"\s+", "", value)


def ad_login_candidates(username, settings):
    """Формирует варианты LDAP-логина для разных доменных форматов входа."""
    raw = (username or "").strip()
    normalized = normalize_ad_username(raw)
    domain = (settings.get("domain") or "").strip()
    candidates = [raw]
    if normalized and normalized != raw:
        candidates.append(normalized)
    if normalized and domain:
        candidates.extend([f"{domain}\\{normalized}", f"{normalized}@{domain}"])
        if "." in domain:
            candidates.append(f"{domain.split('.', 1)[0].upper()}\\{normalized}")
    return list(dict.fromkeys([item for item in candidates if item]))


def ad_base_dn(settings):
    """Строит базовый DN для LDAP-поиска из доменного имени, если он не задан вручную."""
    if settings.get("base_dn"):
        return settings["base_dn"]
    domain = (settings.get("domain") or "").strip()
    return ",".join(f"DC={part}" for part in domain.split(".") if part)


def first_ad_value(values):
    """Извлекает первое строковое значение из LDAP-атрибута, который может быть списком."""
    if isinstance(values, (list, tuple)):
        value = values[0] if values else ""
    else:
        value = values or ""
    return str(value).strip()


def find_profile(settings, login, password, username):
    """Ищет профиль пользователя в Active Directory после успешной проверки пароля."""
    if ldap3 is None:
        raise ActiveDirectoryError("Install ldap3 to use Active Directory login")
    base_dn = ad_base_dn(settings)
    if not base_dn:
        return {"username": normalize_ad_username(username), "ad_login": login}

    host, port = ad_connection_target(settings)
    normalized = normalize_ad_username(username)
    domain = (settings.get("domain") or "").strip()
    filters = [
        f"(sAMAccountName={escape_filter_chars(normalized)})",
        f"(userPrincipalName={escape_filter_chars((username or '').strip())})",
    ]
    if domain and normalized:
        filters.append(f"(userPrincipalName={escape_filter_chars(f'{normalized}@{domain}')})")
    search_filter = f"(&(objectClass=user)(|{''.join(filters)}))"

    try:
        server = ldap3.Server(host, port=port, use_ssl=bool(settings.get("use_ssl")), connect_timeout=5)
        conn = ldap3.Connection(server, user=login, password=password, auto_bind=True, receive_timeout=5)
        conn.search(base_dn, search_filter, attributes=LDAP_ATTRIBUTES, size_limit=1)
        if not conn.entries:
            conn.unbind()
            return {"username": normalized, "ad_login": login}
        raw = conn.entries[0].entry_attributes_as_dict
        conn.unbind()
    except LDAPException as exc:
        raise ActiveDirectoryError(str(exc)) from exc

    full_name = first_ad_value(raw.get("displayName")) or first_ad_value(raw.get("cn"))
    if not full_name:
        full_name = " ".join(part for part in [first_ad_value(raw.get("sn")), first_ad_value(raw.get("givenName"))] if part)
    return {
        "username": first_ad_value(raw.get("sAMAccountName")) or normalized,
        "ad_login": first_ad_value(raw.get("userPrincipalName")) or login,
        "user_principal_name": first_ad_value(raw.get("userPrincipalName")),
        "full_name": full_name,
        "email": first_ad_value(raw.get("mail")) or first_ad_value(raw.get("userPrincipalName")),
        "department": first_ad_value(raw.get("department")),
        "phone": first_ad_value(raw.get("telephoneNumber")) or first_ad_value(raw.get("mobile")),
    }


def authenticate(settings, username, password):
    """Проверяет пользователя через Active Directory и возвращает нормализованный профиль."""
    settings = normalize_settings(settings)
    if not settings.get("enabled"):
        raise ActiveDirectoryError("Active Directory login is disabled")
    if ldap3 is None:
        raise ActiveDirectoryError("Install ldap3 to use Active Directory login")
    if not password:
        raise ActiveDirectoryError("Enter password")

    normalized = normalize_ad_username(username)
    existing = User.objects.filter(
        Q(username__iexact=username)
        | Q(username__iexact=normalized)
        | Q(ad_login__iexact=username)
        | Q(ad_login__iexact=normalized)
    ).first()
    login_source = existing.ad_login if existing and existing.ad_login else username
    last_result = {"available": True, "ok": False, "message": "AD rejected login or password"}
    bound_login = login_source
    for login_name in ad_login_candidates(login_source, settings):
        last_result = ldap_bind(settings, login_name, password)
        bound_login = login_name
        if not last_result["available"] or last_result["ok"]:
            break

    if not last_result["available"]:
        raise ActiveDirectoryError(last_result["message"])
    if not last_result["ok"]:
        raise ActiveDirectoryError("AD rejected login or password")
    profile = find_profile(settings, bound_login, password, username)
    profile["ad_login"] = profile.get("ad_login") or bound_login
    return profile


def sync_user(profile):
    """Создает или обновляет локального пользователя и сотрудника по данным Active Directory."""
    username = (profile.get("username") or "").strip()[:150]
    ad_login = (profile.get("ad_login") or profile.get("user_principal_name") or username).strip()
    email = (profile.get("email") or "").strip()
    if not username:
        raise ActiveDirectoryError("AD did not return a username")

    query = Q(username__iexact=username) | Q(ad_login__iexact=ad_login)
    if email:
        query |= Q(email__iexact=email)
    user = User.objects.filter(query).select_related("employee").first()
    created = user is None
    if created:
        user = User(username=username, role=User.Role.EMPLOYEE, password=make_password(None))
    if not user.is_active:
        raise ActiveDirectoryError("User account is disabled")

    if profile.get("full_name"):
        user.full_name = profile["full_name"][:180]
    if email:
        user.email = email[:254]
    user.ad_login = ad_login[:160]

    employee = user.employee
    if not employee and email:
        employee = Employee.objects.filter(email__iexact=email).first()
    if not employee and profile.get("full_name"):
        employee = Employee.objects.filter(full_name__iexact=profile["full_name"]).first()
    if not employee:
        employee = Employee(full_name=profile.get("full_name") or username)

    if profile.get("full_name"):
        employee.full_name = profile["full_name"][:180]
    if email:
        employee.email = email[:254]
    if profile.get("phone"):
        employee.phone = profile["phone"][:80]
    if profile.get("department"):
        employee.department = profile["department"][:160]
    employee.save()

    user.employee = employee
    user.save()
    return user, created
