# ИТ-инвентаризация

Проект для ВКР на стеке:

- Django - backend и API;
- React + Vite - frontend;
- PostgreSQL - база данных.

## Структура

```text
backend/        Django-проект
frontend/       React-приложение
requirements.txt
```

## PostgreSQL

PostgreSQL 18 работает на порту `5433`.

Создайте базу данных `vkr_inventory` через pgAdmin или `psql`.

В папке `backend` создайте файл `.env` по примеру `.env.example`:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.157.249,vkrinvent

DB_NAME=vkr_inventory
DB_USER=postgres
DB_PASSWORD=ваш_пароль_PostgreSQL
DB_HOST=127.0.0.1
DB_PORT=5433
```

Пароль лучше хранить только в `backend/.env`. Этот файл уже добавлен в `.gitignore`.

## Запуск backend

Откройте PowerShell в папке, где находится `VKR`, и выполните:

```powershell
cd VKR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:5500
```

Если виртуальная среда уже создана и зависимости установлены, для повторного запуска backend достаточно:

```powershell
cd C:\Users\admin\Desktop\VKR\backend
..\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:5500
```

## Запуск frontend

Откройте второе окно PowerShell:

```powershell
cd VKR\frontend
npm.cmd install
npm.cmd run dev:https
```

Или через готовый PowerShell-скрипт из корня проекта:

```powershell
.\scripts\dev-frontend-https.ps1
```

Если `node_modules` уже установлен, для повторного запуска frontend достаточно:

```powershell
cd C:\Users\admin\Desktop\VKR\frontend
npm.cmd run dev:https
```

Откройте приложение:

```text
https://vkrinvent:5173
```

Если ссылка `vkrinvent` не открывается, запустите PowerShell от имени администратора и выполните:

```powershell
.\scripts\register-vkr-host.ps1
```

Frontend проксирует API-запросы на Django:

```text
http://vkrinvent:5500
```

## Проверка

Backend:

```powershell
cd VKR\backend
..\.venv\Scripts\python.exe manage.py check
```

Frontend:

```powershell
cd VKR\frontend
npm.cmd run build
```
