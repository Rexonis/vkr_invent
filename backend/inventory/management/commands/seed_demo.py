"""Команда заполнения базы демонстрационными данными для показа проекта."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import (
    AuditLog,
    Category,
    Employee,
    Equipment,
    InventoryCheck,
    InventorySession,
    Location,
    Movement,
    ServiceRequest,
    User,
    WriteOff,
)


class Command(BaseCommand):
    """Команда Django для заполнения базы демонстрационными данными."""
    help = "Creates demo records for the inventory system."

    def handle(self, *args, **options):
        """Создает демонстрационные справочники, пользователей, оборудование и связанные процессы."""
        today = timezone.localdate()
        now = timezone.now()

        categories = {
            name: Category.objects.update_or_create(name=name, defaults={"lifetime_months": lifetime})[0]
            for name, lifetime in [
                ("Ноутбуки", 48),
                ("Мониторы", 60),
                ("Сетевое оборудование", 72),
                ("Периферия", 36),
                ("Серверы", 84),
                ("Принтеры", 48),
            ]
        }

        locations = {}
        for name, room, responsible in [
            ("Главный офис", "204", "ИТ-отдел"),
            ("Главный офис", "305", "Бухгалтерия"),
            ("Склад", "1", "Заведующий складом"),
            ("Серверная", "001", "Системный администратор"),
            ("Отдел продаж", "212", "Руководитель отдела продаж"),
        ]:
            locations[f"{name}-{room}"] = Location.objects.update_or_create(
                name=name,
                room=room,
                defaults={"responsible": responsible},
            )[0]

        employees = {}
        for full_name, department, email, phone in [
            ("Иванов Иван Иванович", "Бухгалтерия", "ivanov@example.local", "+7 000 000-00-01"),
            ("Петров Алексей Сергеевич", "ИТ-отдел", "petrov@example.local", "+7 000 000-00-02"),
            ("Соколова Елена Викторовна", "Бухгалтерия", "sokolova@example.local", "+7 000 000-00-03"),
            ("Ким Николай Романович", "Отдел продаж", "kim@example.local", "+7 000 000-00-04"),
            ("Орлова Мария Андреевна", "Склад", "orlova@example.local", "+7 000 000-00-05"),
        ]:
            employees[full_name] = Employee.objects.update_or_create(
                full_name=full_name,
                defaults={"department": department, "email": email, "phone": phone},
            )[0]

        admin = self.upsert_user("admin", "admin123", "ИТ-администратор", User.Role.IT_ADMIN, employees["Петров Алексей Сергеевич"], True)
        warehouse = self.upsert_user("warehouse", "warehouse123", "Орлова Мария Андреевна", User.Role.WAREHOUSE, employees["Орлова Мария Андреевна"])
        accountant = self.upsert_user("accountant", "accountant123", "Соколова Елена Викторовна", User.Role.ACCOUNTANT, employees["Соколова Елена Викторовна"])
        manager = self.upsert_user("manager", "manager123", "Ким Николай Романович", User.Role.MANAGER, employees["Ким Николай Романович"])
        employee_user = self.upsert_user("employee", "employee123", "Иванов Иван Иванович", User.Role.EMPLOYEE, employees["Иванов Иван Иванович"])

        equipment = {}
        for item in [
            {
                "inventory_number": "NB-0001",
                "name": "Ноутбук Lenovo ThinkPad E15",
                "category": categories["Ноутбуки"],
                "serial_number": "PF3ABCD1",
                "location": locations["Главный офис-305"],
                "employee": employees["Иванов Иван Иванович"],
                "purchase_date": today - timedelta(days=420),
                "warranty_until": today + timedelta(days=520),
                "price": 95000,
                "status": Equipment.Status.IN_USE,
                "condition": Equipment.Condition.OK,
                "ip_address": "192.168.157.41",
                "mac_address": "A0:B1:C2:D3:E4:F1",
                "specs": "Intel Core i5, 16 ГБ RAM, SSD 512 ГБ",
            },
            {
                "inventory_number": "NB-0002",
                "name": "Ноутбук HP ProBook 450",
                "category": categories["Ноутбуки"],
                "serial_number": "HP450-2025",
                "location": locations["Отдел продаж-212"],
                "employee": employees["Ким Николай Романович"],
                "purchase_date": today - timedelta(days=230),
                "warranty_until": today + timedelta(days=870),
                "price": 88000,
                "status": Equipment.Status.IN_USE,
                "condition": Equipment.Condition.SERVICE,
                "ip_address": "192.168.157.42",
                "mac_address": "A0:B1:C2:D3:E4:F2",
                "specs": "Intel Core i7, 16 ГБ RAM, SSD 1 ТБ",
            },
            {
                "inventory_number": "MON-0001",
                "name": "Монитор Dell P2422H",
                "category": categories["Мониторы"],
                "serial_number": "DL2422-001",
                "location": locations["Главный офис-305"],
                "employee": employees["Соколова Елена Викторовна"],
                "purchase_date": today - timedelta(days=680),
                "warranty_until": today + timedelta(days=120),
                "price": 26000,
                "status": Equipment.Status.IN_USE,
                "condition": Equipment.Condition.OK,
                "specs": "24 дюйма, IPS, Full HD",
            },
            {
                "inventory_number": "SW-0001",
                "name": "Коммутатор TP-Link JetStream",
                "category": categories["Сетевое оборудование"],
                "serial_number": "SN-SW-001",
                "location": locations["Склад-1"],
                "employee": None,
                "purchase_date": today - timedelta(days=900),
                "warranty_until": today - timedelta(days=20),
                "price": 14000,
                "status": Equipment.Status.STORAGE,
                "condition": Equipment.Condition.OK,
                "ip_address": "192.168.157.10",
                "mac_address": "00:11:22:33:44:55",
                "specs": "24 порта, управляемый",
            },
            {
                "inventory_number": "SRV-0001",
                "name": "Сервер Dell PowerEdge",
                "category": categories["Серверы"],
                "serial_number": "DELL-SRV-01",
                "location": locations["Серверная-001"],
                "employee": employees["Петров Алексей Сергеевич"],
                "purchase_date": today - timedelta(days=1300),
                "warranty_until": today + timedelta(days=45),
                "price": 480000,
                "status": Equipment.Status.IN_USE,
                "condition": Equipment.Condition.OK,
                "ip_address": "192.168.157.5",
                "mac_address": "00:AA:BB:CC:DD:01",
                "specs": "Xeon Silver, 64 ГБ RAM, RAID 10",
            },
            {
                "inventory_number": "PRN-0001",
                "name": "Принтер Canon i-SENSYS",
                "category": categories["Принтеры"],
                "serial_number": "CAN-PRN-001",
                "location": locations["Главный офис-204"],
                "employee": None,
                "purchase_date": today - timedelta(days=1500),
                "warranty_until": today - timedelta(days=400),
                "price": 32000,
                "status": Equipment.Status.REPAIR,
                "condition": Equipment.Condition.BROKEN,
                "specs": "Лазерный МФУ, требуется замена узла подачи",
            },
        ]:
            inventory_number = item.pop("inventory_number")
            equipment[inventory_number] = Equipment.objects.update_or_create(inventory_number=inventory_number, defaults=item)[0]

        self.seed_requests(employee_user, manager, admin, employees, categories)
        self.seed_movements(equipment, locations, employees, warehouse, now)
        self.seed_writeoffs(equipment, admin, today)
        self.seed_inventory(equipment, admin, now)
        self.seed_audit(admin, equipment)

        self.stdout.write(self.style.SUCCESS("Demo data created. Admin login: admin / admin123"))

    def upsert_user(self, username, password, full_name, role, employee=None, staff=False):
        """Создает или обновляет демонстрационного пользователя с заданной ролью."""
        user, created = User.objects.get_or_create(username=username)
        user.full_name = full_name
        user.email = employee.email if employee else ""
        user.role = role
        user.employee = employee
        user.is_staff = staff
        user.is_superuser = staff
        if created or not user.has_usable_password():
            user.set_password(password)
        user.save()
        return user

    def seed_requests(self, employee_user, manager, admin, employees, categories):
        """Создает демонстрационные заявки сотрудников."""
        rows = [
            {
                "user": employee_user,
                "employee": employees["Иванов Иван Иванович"],
                "category": categories["Ноутбуки"],
                "title": "Требуется ноутбук для выездной работы",
                "requested_specs": "Легкий ноутбук, 16 ГБ RAM, автономность от 6 часов",
                "justification": "Частые выезды на сверки и инвентаризации.",
                "status": ServiceRequest.Status.REVIEW,
            },
            {
                "user": manager,
                "employee": employees["Ким Николай Романович"],
                "category": categories["Мониторы"],
                "title": "Второй монитор для отдела продаж",
                "requested_specs": "24-27 дюймов, HDMI/DisplayPort",
                "justification": "Одновременная работа с CRM и отчетностью.",
                "status": ServiceRequest.Status.APPROVED,
                "decision_reason": "Принято в работу руководителем ИТ.",
                "decided_by": admin,
            },
            {
                "user": employee_user,
                "employee": employees["Иванов Иван Иванович"],
                "category": categories["Периферия"],
                "title": "Замена клавиатуры",
                "requested_specs": "Проводная клавиатура",
                "justification": "Текущая клавиатура работает нестабильно.",
                "status": ServiceRequest.Status.DONE,
                "decision_reason": "Выдано со склада.",
                "decided_by": admin,
            },
        ]
        for row in rows:
            ServiceRequest.objects.update_or_create(title=row["title"], defaults=row)

    def seed_movements(self, equipment, locations, employees, warehouse, now):
        """Создает демонстрационные перемещения оборудования."""
        rows = [
            (equipment["NB-0002"], locations["Склад-1"], locations["Отдел продаж-212"], employees["Ким Николай Романович"], now - timedelta(days=12), "done"),
            (equipment["MON-0001"], locations["Склад-1"], locations["Главный офис-305"], employees["Соколова Елена Викторовна"], now - timedelta(days=8), "done"),
            (equipment["SW-0001"], locations["Склад-1"], locations["Серверная-001"], None, now + timedelta(days=3), "planned"),
        ]
        for item, from_location, to_location, employee, moved_at, status in rows:
            Movement.objects.update_or_create(
                equipment=item,
                moved_at=moved_at,
                defaults={
                    "inventory_number": item.inventory_number,
                    "equipment_name": item.name,
                    "from_location": from_location,
                    "to_location": to_location,
                    "employee": employee,
                    "status": status,
                    "created_by": warehouse,
                },
            )

    def seed_writeoffs(self, equipment, admin, today):
        """Создает демонстрационные записи списания оборудования."""
        rows = [
            (equipment["PRN-0001"], today - timedelta(days=2), "Неисправен узел подачи бумаги, ремонт экономически нецелесообразен.", "Петров А.С., Орлова М.А.", "review"),
            (equipment["SW-0001"], today + timedelta(days=10), "Плановая замена после окончания гарантии.", "Петров А.С., Ким Н.Р.", "prepared"),
        ]
        for item, writeoff_date, reason, commission, status in rows:
            WriteOff.objects.update_or_create(
                equipment=item,
                writeoff_date=writeoff_date,
                defaults={
                    "inventory_number": item.inventory_number,
                    "equipment_name": item.name,
                    "reason": reason,
                    "commission": commission,
                    "status": status,
                    "created_by": admin,
                },
            )

    def seed_inventory(self, equipment, admin, now):
        """Создает демонстрационную сессию инвентаризации и проверки."""
        session, _ = InventorySession.objects.update_or_create(
            title="Плановая инвентаризация ИТ-активов",
            defaults={"started_at": now - timedelta(days=5), "status": "В работе"},
        )
        checks = [
            (equipment["NB-0001"], "found", Equipment.Condition.OK),
            (equipment["MON-0001"], "found", Equipment.Condition.OK),
            (equipment["PRN-0001"], "missing", Equipment.Condition.BROKEN),
        ]
        for item, result, condition in checks:
            InventoryCheck.objects.update_or_create(
                session=session,
                equipment=item,
                defaults={"result": result, "condition": condition, "checked_at": now - timedelta(days=1)},
            )

    def seed_audit(self, admin, equipment):
        """Создает демонстрационные записи журнала аудита."""
        rows = [
            ("equipment.created", "equipment", equipment["NB-0001"].id),
            ("movement.created", "movement", "demo-move"),
            ("writeoff.created", "writeoff", "demo-writeoff"),
            ("inventory_session.created", "inventory_session", "demo-inventory"),
            ("ad.connection.tested", "app_setting", "ad"),
        ]
        for action, entity, entity_id in rows:
            exists = AuditLog.objects.filter(
                action=action,
                entity=entity,
                entity_id=str(entity_id),
                username=admin.username,
            ).exists()
            if not exists:
                AuditLog.objects.create(
                    action=action,
                    entity=entity,
                    entity_id=str(entity_id),
                    user=admin,
                    username=admin.username,
                    after_json={"demo": True},
                )
