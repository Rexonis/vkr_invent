"""Тесты защиты API от SQL-инъекций и небезопасного доступа к базе."""

import ast
from pathlib import Path
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from .models import User
from .views import filtered_equipment_queryset


class SqlInjectionProtectionTests(SimpleTestCase):
    """Проверяет, что фильтры оборудования не формируют небезопасные SQL-запросы."""
    def request(self, params):
        """Создает тестовый HTTP-запрос с ролью администратора для проверки queryset-фильтров."""
        request = RequestFactory().get("/api/equipment", params)
        request.user = SimpleNamespace(role=User.Role.IT_ADMIN, employee_id=None)
        return request

    def test_equipment_search_uses_query_parameters(self):
        """Проверяет, что поисковая строка передается в SQL как параметр."""
        payload = "' OR 1=1 --"
        queryset = filtered_equipment_queryset(self.request({"q": payload}))

        sql, params = queryset.query.sql_with_params()

        self.assertNotIn(payload, sql)
        self.assertIn(f"%{payload}%", params)

    def test_equipment_filters_reject_sql_payloads(self):
        """Проверяет отклонение SQL-подобных значений в фильтрах."""
        with self.assertRaises(ValueError):
            filtered_equipment_queryset(self.request({"employee_id": "1 OR 1=1"}))
        with self.assertRaises(ValueError):
            filtered_equipment_queryset(self.request({"status": "in_use' OR '1'='1"}))

    def test_backend_does_not_use_raw_sql_apis(self):
        """Проверяет, что backend не использует raw SQL API в прикладном коде."""
        forbidden_calls = {"raw", "extra", "cursor", "execute", "executemany"}
        forbidden_names = {"RawSQL"}
        inventory_dir = Path(__file__).resolve().parent
        offenders = []

        for path in inventory_dir.rglob("*.py"):
            if path.name == "tests.py" or "migrations" in path.parts or "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = getattr(func, "attr", None) or getattr(func, "id", None)
                    if name in forbidden_calls:
                        offenders.append(f"{path.name}:{node.lineno}:{name}")
                elif isinstance(node, ast.Name) and node.id in forbidden_names:
                    offenders.append(f"{path.name}:{node.lineno}:{node.id}")

        self.assertEqual([], offenders)
