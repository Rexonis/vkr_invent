"""Модели предметной области: оборудование, сотрудники, заявки, инвентаризация и аудит."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Справочник категорий оборудования и нормативного срока службы."""
    name = models.CharField(max_length=160, unique=True)
    lifetime_months = models.PositiveIntegerField(default=60)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.name


class Location(models.Model):
    """Справочник мест размещения оборудования с кабинетом и ответственным лицом."""
    name = models.CharField(max_length=160)
    room = models.CharField(max_length=80, blank=True)
    responsible = models.CharField(max_length=160, blank=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["name", "room"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return f"{self.name} {self.room}".strip()


class Employee(models.Model):
    """Карточка сотрудника, к которому может быть закреплено оборудование."""
    full_name = models.CharField(max_length=180)
    department = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=80, blank=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["full_name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.full_name


class User(AbstractUser):
    """Пользователь системы с ролью, профилем сотрудника и параметрами авторизации."""
    class Role(models.TextChoices):
        """Перечисляет роли пользователей и их человекочитаемые названия для интерфейса."""
        IT_ADMIN = "it_admin", "ИТ-администратор"
        WAREHOUSE = "warehouse", "Заведующий складом"
        ACCOUNTANT = "accountant", "Бухгалтер"
        MANAGER = "manager", "Руководитель отдела"
        EMPLOYEE = "employee", "Сотрудник"

    full_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.EMPLOYEE)
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=128, blank=True)
    ad_login = models.CharField(max_length=160, blank=True)
    avatar = models.CharField(max_length=32, default="slate", blank=True)

    def display_name(self):
        """Возвращает имя пользователя, удобное для отображения в интерфейсе."""
        return self.full_name or self.get_full_name() or self.username


class Equipment(models.Model):
    """Основная карточка единицы оборудования с инвентарными, финансовыми и техническими данными."""
    class Status(models.TextChoices):
        """Перечисляет допустимые статусы бизнес-объекта."""
        IN_USE = "in_use", "В эксплуатации"
        STORAGE = "storage", "На складе"
        REPAIR = "repair", "В ремонте"
        WRITTEN_OFF = "written_off", "Списано"

    class Condition(models.TextChoices):
        """Перечисляет возможные технические состояния оборудования."""
        OK = "ok", "Исправно"
        SERVICE = "service", "Требует обслуживания"
        BROKEN = "broken", "Неисправно"
        LOST = "lost", "Утеряно"

    inventory_number = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=180)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    serial_number = models.CharField(max_length=120, blank=True)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL)
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    purchase_date = models.DateField(null=True, blank=True)
    warranty_until = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.IN_USE)
    condition = models.CharField(max_length=32, choices=Condition.choices, default=Condition.OK)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=32, blank=True)
    specs = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    qr_payload = models.JSONField(default=dict, blank=True)
    qr_svg = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["inventory_number"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return f"{self.inventory_number} - {self.name}"


class InventorySession(models.Model):
    """Описывает сессию инвентаризации и ее общий статус."""
    title = models.CharField(max_length=220)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=80, default="В работе")
    notes = models.TextField(blank=True)
    archived = models.BooleanField(default=False)


class InventoryCheck(models.Model):
    """Фиксирует результат проверки конкретной единицы оборудования в рамках инвентаризации."""
    session = models.ForeignKey(InventorySession, on_delete=models.CASCADE, related_name="checks")
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    checked_at = models.DateTimeField(default=timezone.now)
    result = models.CharField(max_length=80, default="Найдено")
    condition = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        unique_together = [("session", "equipment")]


class AppSetting(models.Model):
    """Хранит системные настройки приложения в формате ключ-значение."""
    key = models.CharField(max_length=180, primary_key=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class InfrastructureSegment(models.Model):
    """Описывает логический сегмент ИТ-инфраструктуры."""
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=80, blank=True)
    owner = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.name


class Network(models.Model):
    """Хранит сведения о сети, ее CIDR-диапазоне, шлюзе и назначении."""
    segment = models.ForeignKey(InfrastructureSegment, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=160)
    cidr = models.CharField(max_length=64)
    gateway = models.GenericIPAddressField(null=True, blank=True)
    purpose = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["cidr", "name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return f"{self.name} {self.cidr}".strip()


class NetworkVlan(models.Model):
    """Хранит VLAN и связь с сетью или инфраструктурным сегментом."""
    segment = models.ForeignKey(InfrastructureSegment, null=True, blank=True, on_delete=models.SET_NULL)
    network = models.ForeignKey(Network, null=True, blank=True, on_delete=models.SET_NULL)
    vlan_id = models.PositiveIntegerField()
    name = models.CharField(max_length=160)
    purpose = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["vlan_id", "name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return f"VLAN {self.vlan_id} - {self.name}"


class NetworkIpAddress(models.Model):
    """Учитывает IP-адреса, их владельцев, статусы и результаты сетевого сканирования."""
    class Status(models.TextChoices):
        """Перечисляет допустимые статусы бизнес-объекта."""
        FREE = "free", "Свободен"
        RESERVED = "reserved", "Зарезервирован"
        USED = "used", "Используется"

    network = models.ForeignKey(Network, null=True, blank=True, on_delete=models.SET_NULL)
    vlan = models.ForeignKey(NetworkVlan, null=True, blank=True, on_delete=models.SET_NULL)
    address = models.GenericIPAddressField()
    hostname = models.CharField(max_length=180, blank=True)
    owner = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.USED)
    scan_source = models.CharField(max_length=80, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["address"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return str(self.address)


class NetworkDomain(models.Model):
    """Хранит доменные имена, регистраторов и сроки продления."""
    name = models.CharField(max_length=180)
    registrar = models.CharField(max_length=180, blank=True)
    dns_servers = models.TextField(blank=True)
    owner = models.CharField(max_length=160, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["name"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.name


class InternetLink(models.Model):
    """Описывает договоры и параметры подключений к интернет-провайдерам."""
    provider = models.CharField(max_length=180)
    contract_number = models.CharField(max_length=120, blank=True)
    speed_mbps = models.PositiveIntegerField(default=0)
    external_ip = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=80, default="Активен")
    contacts = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["provider", "location"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.provider


class TelephonyLine(models.Model):
    """Учитывает телефонные линии, номера, владельцев и текущее состояние."""
    provider = models.CharField(max_length=180)
    number = models.CharField(max_length=80)
    line_type = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=180, blank=True)
    employee = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=80, default="Активна")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["number"]

    def __str__(self):
        """Возвращает человекочитаемое представление объекта для админ-панели и журналов."""
        return self.number


class ServiceRequest(models.Model):
    """Описывает заявку сотрудника на оборудование или ИТ-услугу."""
    class Status(models.TextChoices):
        """Перечисляет допустимые статусы бизнес-объекта."""
        REVIEW = "review", "На рассмотрении"
        APPROVED = "approved", "В работе"
        REJECTED = "rejected", "Отклонено"
        DONE = "done", "Выполнено"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="service_requests")
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=220)
    requested_specs = models.TextField(blank=True)
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.REVIEW)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="decisions")
    archived_by_requester = models.BooleanField(default=False)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["-created_at"]


class Notification(models.Model):
    """Хранит пользовательские уведомления, показываемые в интерфейсе."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=220, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["-created_at"]


class Movement(models.Model):
    """Фиксирует передачу оборудования между локациями или сотрудниками."""
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    inventory_number = models.CharField(max_length=80)
    equipment_name = models.CharField(max_length=180)
    from_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="outgoing_movements")
    to_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="incoming_movements")
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    moved_at = models.DateTimeField()
    status = models.CharField(max_length=80, default="Запланировано")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    archived = models.BooleanField(default=False)


class WriteOff(models.Model):
    """Описывает процедуру списания оборудования и ее согласование."""
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    inventory_number = models.CharField(max_length=80)
    equipment_name = models.CharField(max_length=180)
    reason = models.TextField(blank=True)
    writeoff_date = models.DateField()
    commission = models.TextField(blank=True)
    status = models.CharField(max_length=80, default="Подготовлено")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    archived = models.BooleanField(default=False)


class AuditLog(models.Model):
    """Журналирует значимые действия пользователей и изменения данных."""
    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=220)
    entity = models.CharField(max_length=120, blank=True)
    entity_id = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)

    class Meta:
        """Описывает сущность Meta в структуре приложения."""
        ordering = ["-created_at"]
