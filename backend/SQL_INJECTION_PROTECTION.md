# SQL Injection Protection

В backend не используется ручная склейка SQL-строк. Все обращения к базе данных выполняются через Django ORM, который передает пользовательские значения в SQL как параметры запроса.

Дополнительные меры:

- raw SQL API (`raw`, `extra`, `cursor`, `execute`, `executemany`, `RawSQL`) запрещены тестом `SqlInjectionProtectionTests`;
- строка поиска ограничена по длине и используется только в ORM `icontains`;
- id-фильтры приводятся к положительным целым числам;
- `status` и `condition` проверяются по whitelist значений Django `TextChoices`;
- некорректные фильтры возвращают HTTP 400, а не попадают в SQL.

Проверка:

```powershell
cd C:\Users\admin\Desktop\VKR\backend
..\.venv\Scripts\python.exe manage.py test inventory.tests.SqlInjectionProtectionTests
```
