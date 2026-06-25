// Основной интерфейс системы учета: навигация, формы, таблицы и работа с API.
import { Component, useEffect, useMemo, useRef, useState } from "react";
import { Archive, Bell, Download, Moon, Pencil, RefreshCw, RotateCcw, Settings, Sun, X } from "lucide-react";

import { api } from "./api.js";

const emptyEquipment = {
  inventory_number: "",
  name: "",
  category_id: "",
  serial_number: "",
  location_id: "",
  employee_id: "",
  purchase_date: "",
  warranty_until: "",
  price: "",
  status: "in_use",
  condition: "ok",
  ip_address: "",
  mac_address: "",
  specs: "",
  notes: "",
};

const defaultAdSettings = {
  enabled: false,
  domain: "",
  server: "",
  controller: "",
  port: 389,
  base_dn: "",
  bind_user: "",
  bind_password: "",
};

// Набор аватаров хранит только ключ в базе, а внешний вид собирается на фронтенде.
const avatarOptions = [
  ["slate", "SL", "Сланцевый", "initials"],
  ["mint", "MT", "Мятный", "initials"],
  ["amber", "AM", "Янтарный", "initials"],
  ["rose", "RS", "Розовый", "initials"],
  ["violet", "VT", "Фиолетовый", "initials"],
  ["sky", "SK", "Небесный", "initials"],
  ["forest", "FR", "Лесной", "initials"],
  ["graphite", "GR", "Графитовый", "initials"],
  ["cat", "🐱", "Кот", "symbol"],
  ["dog", "🐶", "Собака", "symbol"],
  ["fox", "🦊", "Лиса", "symbol"],
  ["bear", "🐻", "Медведь", "symbol"],
  ["panda", "🐼", "Панда", "symbol"],
  ["owl", "🦉", "Сова", "symbol"],
  ["rabbit", "🐰", "Кролик", "symbol"],
  ["rocket", "🚀", "Ракета", "symbol"],
  ["star", "✦", "Звезда", "symbol"],
  ["shield", "🛡", "Щит", "symbol"],
  ["gem", "◆", "Кристалл", "symbol"],
  ["bolt", "⚡", "Молния", "symbol"],
  ["compass", "✧", "Компас", "symbol"],
];

const titles = {
  dashboard: ["Обзор", "Ролевая сводка по оборудованию, процессам и контрольным событиям"],
  cabinet: ["Настройки профиля", "Личные данные, закрепленная техника и заявки сотрудника"],
  equipment: ["Оборудование", "Реестр с фильтрами, карточками и доступом по роли"],
  movements: ["Перемещения", "Оформление передачи оборудования между локациями и сотрудниками"],
  writeoffs: ["Списание", "Подготовка актов и история списания оборудования"],
  inventory: ["Инвентаризация", "Сверка фактического наличия и расхождения"],
  reports: ["Отчеты", "Гарантии, складские остатки, финансовые и регламентные формы"],
  requests: ["Заявки", "Очередь обращений сотрудников, согласование и ответы по статусам"],
  users: ["Пользователи", "Учетные записи, роли и привязка к сотрудникам"],
  audit: ["Журнал аудита", "История действий с датой, инициатором и изменениями"],
};

const nav = [
  ["dashboard", "Обзор", "equipment:view"],
  ["equipment", "Оборудование", "equipment:view"],
  ["movements", "Перемещения", "lifecycle:manage"],
  ["writeoffs", "Списание", "lifecycle:manage"],
  ["inventory", "Инвентаризация", "inventory:write"],
  ["reports", "Отчеты", "reports:view"],
  ["requests", "Заявки", ["requests:approve", "requests:create"]],
  ["users", "Пользователи", "users:manage"],
  ["audit", "Журнал аудита", "audit:view"],
];

/**
 * Проверяет, есть ли у пользователя одно или несколько требуемых разрешений.
 */
function hasPermission(permissions, permission) {
  if (!permission) return true;
  if (Array.isArray(permission)) return permission.some((item) => permissions.includes(item));
  return permissions.includes(permission);
}

/**
 * Выбирает первый доступный раздел интерфейса по набору разрешений пользователя.
 */
function defaultView(permissions) {
  return nav.find((item) => hasPermission(permissions, item[2]))?.[0] || "cabinet";
}

const activeViewStorageKey = "vkr.activeView";
const themeStorageKey = "vkr.theme";

/**
 * Читает сохраненную пользователем тему из localStorage.
 */
function storedThemePreference() {
  try {
    const value = window.localStorage.getItem(themeStorageKey);
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null;
  }
}

/**
 * Определяет системную светлую или темную тему браузера.
 */
function systemThemePreference() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Выбирает начальную тему интерфейса с учетом сохраненных и системных настроек.
 */
function initialTheme() {
  return storedThemePreference() || systemThemePreference();
}

/**
 * Применяет тему к корневому элементу, чтобы CSS-переменные переключились глобально.
 */
function applyTheme(theme) {
  // Метка темы хранится на корневом элементе, чтобы CSS-переменные переключались одновременно.
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

/**
 * Восстанавливает последний открытый раздел приложения из localStorage.
 */
function storedActiveView() {
  try {
    const value = window.localStorage.getItem(activeViewStorageKey);
    return value && (value === "cabinet" || nav.some(([key]) => key === value)) ? value : "cabinet";
  } catch {
    return "cabinet";
  }
}

/**
 * Форматирует числовое значение как сумму в рублях.
 */
function money(value) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value || 0);
}

/**
 * Возвращает дату в коротком ISO-формате для таблиц и полей ввода.
 */
function shortDate(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

/**
 * Создает начальное состояние формы перемещения оборудования.
 */
function initialMovementForm() {
  return { equipment_id: "", from_location_id: "", to_location_id: "", employee_id: "", moved_at: shortDate(new Date().toISOString()), status: "planned" };
}

/**
 * Создает начальное состояние формы списания оборудования.
 */
function initialWriteoffForm() {
  return { equipment_id: "", writeoff_date: shortDate(new Date().toISOString()), reason: "", commission: "", status: "prepared" };
}

/**
 * Преобразует существующее перемещение в состояние формы редактирования.
 */
function movementFormFromRow(row) {
  return {
    equipment_id: row.equipment_id || "",
    from_location_id: row.from_location_id || "",
    to_location_id: row.to_location_id || "",
    employee_id: row.employee_id || "",
    moved_at: shortDate(row.moved_at),
    status: row.status || "planned",
  };
}

/**
 * Преобразует существующее списание в состояние формы редактирования.
 */
function writeoffFormFromRow(row) {
  return {
    equipment_id: row.equipment_id || "",
    writeoff_date: shortDate(row.writeoff_date),
    reason: row.reason || "",
    commission: row.commission || "",
    status: row.status || "prepared",
  };
}

/**
 * Определяет CSS-класс бейджа по статусу или состоянию записи.
 */
function badgeClass(value) {
  if (["broken", "lost", "written_off", "rejected"].includes(value)) return "danger";
  if (["service", "storage", "repair", "review"].includes(value)) return "warn";
  return "";
}

/**
 * Строит инициалы пользователя для текстового аватара.
 */
function initials(name) {
  return (name || "IT").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

/**
 * Проверяет ключ аватара и подставляет безопасное значение по умолчанию.
 */
function avatarValue(value) {
  return avatarOptions.some(([key]) => key === value) ? value : "slate";
}

/**
 * Возвращает полное описание выбранного варианта аватара.
 */
function avatarOption(value) {
  return avatarOptions.find(([key]) => key === avatarValue(value)) || avatarOptions[0];
}

/**
 * Сокращает ФИО до фамилии и инициала для компактных списков.
 */
function shortPersonName(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return name || "";
  return `${parts[0]} ${parts[1][0]}.`;
}

/**
 * Гарантирует, что значение будет массивом перед рендерингом списков.
 */
function asArray(value) {
  return Array.isArray(value) ? value : [];
}

/**
 * Гарантирует, что значение будет объектом перед чтением полей.
 */
function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

/**
 * Приводит настройки Active Directory из API к форме, удобной для редактирования.
 */
function normalizeAdSettings(value) {
  const raw = asObject(value);
  const source = { ...defaultAdSettings, ...raw };
  const server = raw.controller !== undefined ? raw.controller : (raw.server || "");
  const port = Number(source.port || 389);
  return {
    ...source,
    enabled: !!source.enabled,
    server,
    controller: server,
    port: port === 636 ? 389 : port,
    use_ssl: false,
    bind_password: "",
  };
}

/**
 * Нормализует справочники API, чтобы компоненты получали массивы.
 */
function normalizeDictionaries(value) {
  const source = asObject(value);
  return {
    categories: asArray(source.categories),
    locations: asArray(source.locations),
    employees: asArray(source.employees),
    statuses: asArray(source.statuses),
    conditions: asArray(source.conditions),
  };
}

/**
 * Определяет ошибку неавторизованного доступа по HTTP-статусу.
 */
function isUnauthorized(err) {
  return err?.status === 401;
}

const requestTitleKeywords = [
  "ноутбук", "компьютер", "пк", "монитор", "принтер", "мфу", "сканер",
  "клавиатур", "мыш", "телефон", "гарнитур", "проектор", "планшет",
  "сервер", "роутер", "кабель", "картридж", "оборуд", "техник",
  "доступ", "аккаунт", "учет", "парол", "права", "почт", "сеть",
  "интернет", "лицензи", "программ", "софт", "установ", "настро",
  "ремонт", "замен", "выдать", "требу", "рабоч", "мест",
];

/**
 * Проверяет тему заявки на клиенте до отправки на backend.
 */
function validateRequestTitle(value) {
  const title = String(value || "").replace(/\s+/g, " ").trim();
  if (title.length < 8) return "Тема заявки должна содержать не менее 8 символов";
  if (title.length > 120) return "Тема заявки должна быть не длиннее 120 символов";
  const letters = title.match(/[A-Za-zА-Яа-яЁё]/g) || [];
  if (letters.length < 6) return "Тема заявки должна содержать понятное описание, а не набор символов";
  const words = title.match(/[A-Za-zА-Яа-яЁё0-9]{2,}/g) || [];
  if (words.length < 2) return "Укажите тему заявки минимум из двух слов, например: Замена клавиатуры";
  const compact = title.toLowerCase().replace(/[^a-zа-яё0-9]/gi, "");
  if (/([a-zа-яё])\1{3,}/i.test(compact)) return "Тема заявки похожа на случайный набор букв";
  if (/(qwerty|asdf|zxcv|йцу|фыв|ячс|апрол)/i.test(compact)) return "Тема заявки похожа на случайный набор букв";
  if (!requestTitleKeywords.some((keyword) => compact.includes(keyword))) {
    return "Укажите конкретный предмет заявки: ноутбук, монитор, принтер, доступ, ремонт и т.д.";
  }
  return "";
}

/**
 * Главный компонент приложения: хранит состояние сессии, разделов, форм и загрузки данных.
 */
export default function App() {
  const [session, setSession] = useState({ user: null, roles: {} });
  const [authMode, setAuthMode] = useState("login");
  const [auth, setAuth] = useState({ username: "", password: "", full_name: "", email: "", code: "", ad: false });
  const [activeView, setActiveView] = useState(storedActiveView);
  const [theme, setTheme] = useState(initialTheme);
  const [summary, setSummary] = useState(null);
  const [dictionaries, setDictionaries] = useState({ categories: [], locations: [], employees: [], statuses: [], conditions: [] });
  const [equipment, setEquipment] = useState([]);
  const [requests, setRequests] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [selectedRequestId, setSelectedRequestId] = useState(null);
  const [movements, setMovements] = useState([]);
  const [writeoffs, setWriteoffs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [inventoryReport, setInventoryReport] = useState(null);
  const [reports, setReports] = useState(null);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [cabinet, setCabinet] = useState(null);
  const [adSettings, setAdSettings] = useState(defaultAdSettings);
  const [adTest, setAdTest] = useState(null);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [filters, setFilters] = useState({ search: "", status: "", category_id: "", location_id: "" });
  const [equipmentForm, setEquipmentForm] = useState(emptyEquipment);
  const [editingEquipment, setEditingEquipment] = useState(null);
  const [equipmentDialogOpen, setEquipmentDialogOpen] = useState(false);
  const [requestForm, setRequestForm] = useState({ title: "", category_id: "", requested_specs: "", justification: "" });
  const [movementForm, setMovementForm] = useState(initialMovementForm);
  const [editingMovementId, setEditingMovementId] = useState(null);
  const [writeoffForm, setWriteoffForm] = useState(initialWriteoffForm);
  const [editingWriteoffId, setEditingWriteoffId] = useState(null);
  const [inventoryForm, setInventoryForm] = useState({ equipment_id: "", result: "found", condition: "ok" });
  const [busy, setBusy] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const user = session.user;
  const permissions = user?.permissions || [];
  const title = titles[activeView] || titles[defaultView(permissions)] || titles.cabinet;
  const selectedMovementEquipment = equipment.find((item) => item.id === Number(movementForm.equipment_id));
  const selectedWriteoffEquipment = equipment.find((item) => item.id === Number(writeoffForm.equipment_id));
  const visibleTheme = user ? theme : "light";

  const can = useMemo(() => (permission) => hasPermission(permissions, permission), [permissions]);

  useEffect(() => {
    try {
      window.localStorage.setItem(activeViewStorageKey, activeView);
    } catch {
      // Если хранилище браузера отключено, навигация все равно работает в текущей сессии.
    }
  }, [activeView]);

  useEffect(() => {
    applyTheme(visibleTheme);
  }, [visibleTheme]);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!media) return undefined;
    const syncSystemTheme = (event) => {
      // Следуем системной теме, пока пользователь не выбрал тему вручную.
      if (!storedThemePreference()) setTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener?.("change", syncSystemTheme);
    return () => media.removeEventListener?.("change", syncSystemTheme);
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    try {
      window.localStorage.setItem(themeStorageKey, nextTheme);
    } catch {
      // Даже без хранилища браузера тема меняется до перезагрузки страницы.
    }
  }

  function showToast(message) {
    setToast(message);
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => setToast(""), 2600);
  }

  async function runAction(action) {
    try {
      setError("");
      await action();
    } catch (err) {
      const message = err?.message || "Action failed";
      setError(message);
      showToast(message);
    }
  }

  async function loadSession() {
    const data = await api.get("/api/auth/me");
    setSession({ user: data.user || null, roles: asObject(data.roles) });
    if (data.user) await loadWorkspace(data.user.permissions || []);
  }

  async function loadWorkspace(nextPermissions = permissions) {
    const tasks = [
      api.get("/api/dictionaries").then((data) => setDictionaries(normalizeDictionaries(data))),
      api.get("/api/requests").then((data) => setRequests(asArray(data))),
      api.get("/api/notifications").then((data) => setNotifications(asArray(data))).catch((err) => {
        if (isUnauthorized(err)) setNotifications([]);
        else throw err;
      }),
      api.get("/api/cabinet").then(setCabinet),
    ];
    if (nextPermissions.includes("equipment:view")) {
      tasks.push(api.get("/api/summary").then(setSummary));
      tasks.push(loadEquipment(filters));
    } else {
      setSummary(null);
      setEquipment([]);
    }
    if (nextPermissions.includes("lifecycle:manage")) {
      tasks.push(api.get("/api/movements").then((data) => setMovements(asArray(data))));
      tasks.push(api.get("/api/writeoffs").then((data) => setWriteoffs(asArray(data))));
    }
    if (nextPermissions.includes("inventory:write")) tasks.push(loadInventory());
    if (nextPermissions.includes("reports:view")) tasks.push(api.get("/api/reports").then(setReports));
    if (nextPermissions.includes("users:manage")) {
      tasks.push(api.get("/api/users").then((data) => setUsers(asArray(data))));
      tasks.push(api.get("/api/ad/settings").then((data) => setAdSettings(normalizeAdSettings(data))));
    }
    if (nextPermissions.includes("audit:view")) tasks.push(loadAudit());
    const results = await Promise.allSettled(tasks);
    const failed = results
      .filter((result) => result.status === "rejected")
      .map((result) => result.reason)
      .filter((reason) => ![401, 403].includes(reason?.status));
    if (failed.length) {
      showToast(`Часть данных не загрузилась: ${failed[0]?.message || "проверьте backend"}`);
    }
    const savedView = storedActiveView();
    const nextView = hasPermission(nextPermissions, nav.find(([key]) => key === savedView)?.[2])
      ? savedView
      : defaultView(nextPermissions);
    if (nextView !== activeView) {
      setActiveView(nextView);
    }
  }

  async function loadEquipment(nextFilters = filters) {
    const params = new URLSearchParams();
    Object.entries(asObject(nextFilters)).forEach(([key, value]) => {
      if (value) params.set(key === "search" ? "q" : key, value);
    });
    setEquipment(asArray(await api.get(`/api/equipment?${params.toString()}`)));
  }

  async function loadInventory() {
    const rows = await api.get("/api/inventory/sessions");
    const sessionRows = asArray(rows);
    setSessions(sessionRows);
    const current = sessionRows.find((session) => session.id === activeSessionId);
    const sessionId = current?.id || sessionRows.find((session) => !session.archived)?.id || sessionRows[0]?.id || null;
    setActiveSessionId(sessionId);
    if (sessionId) {
      setInventoryReport(await api.get(`/api/inventory/sessions/${sessionId}/report`));
    } else {
      setInventoryReport(null);
    }
  }

  async function loadAudit() {
    const rows = await api.get("/api/audit");
    setAudit(asArray(rows));
  }

  useEffect(() => {
    loadSession()
      .catch(() => setSession({ user: null, roles: {} }))
      .finally(() => setSessionReady(true));
  }, []);

  useEffect(() => {
    function handleUnhandled(event) {
      const message = event.reason?.message || event.message || "Ошибка интерфейса";
      event.preventDefault?.();
      setError(message);
      showToast(message);
    }
    window.addEventListener("unhandledrejection", handleUnhandled);
    window.addEventListener("error", handleUnhandled);
    return () => {
      window.removeEventListener("unhandledrejection", handleUnhandled);
      window.removeEventListener("error", handleUnhandled);
    };
  }, []);

  useEffect(() => {
    if (!activeSessionId || !user) return;
    api.get(`/api/inventory/sessions/${activeSessionId}/report`).then(setInventoryReport).catch(() => {});
  }, [activeSessionId, user]);

  useEffect(() => {
    if (!user || activeView !== "audit" || !permissions.includes("audit:view")) return;
    loadAudit().catch(() => {});
  }, [activeView, user]);

  useEffect(() => {
    if (!user) return;
    let source = null;
    if ("EventSource" in window) {
      source = new EventSource("/api/notifications/stream");
      source.addEventListener("notifications", (event) => {
        try {
          setNotifications(asArray(JSON.parse(event.data)));
        } catch {
          setNotifications([]);
        }
      });
      source.onerror = () => {};
    }
    const timer = window.setInterval(() => {
      api.get("/api/notifications")
        .then((data) => setNotifications(asArray(data)))
        .catch((err) => {
          if (isUnauthorized(err)) {
            setSession({ user: null, roles: {} });
            setNotifications([]);
          }
        });
    }, 5000);
    return () => {
      if (source) source.close();
      window.clearInterval(timer);
    };
  }, [user]);

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
      const data = await api.send(endpoint, "POST", auth);
      if (authMode === "register") {
        setAuthMode("login");
        setAuth((current) => ({ ...current, password: "" }));
        showToast("Учетная запись создана. Теперь можно войти.");
      } else {
        const nextUser = data.user || null;
        setSession({ user: nextUser, roles: asObject(data.roles) });
        if (nextUser) await loadWorkspace(nextUser.permissions || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await runAction(async () => {
      await api.send("/api/auth/logout", "POST");
      setSession({ user: null, roles: {} });
      setActiveView("dashboard");
    });
  }

  async function saveEquipment(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const url = editingEquipment ? `/api/equipment/${editingEquipment.id}` : "/api/equipment";
      const method = editingEquipment ? "PUT" : "POST";
      await api.send(url, method, equipmentForm);
      setEquipmentDialogOpen(false);
      setEditingEquipment(null);
      setEquipmentForm(emptyEquipment);
      await loadWorkspace();
      showToast("Карточка сохранена");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteEquipment() {
    if (!editingEquipment) return;
    await runAction(async () => {
      await api.send(`/api/equipment/${editingEquipment.id}`, "DELETE");
      setEquipmentDialogOpen(false);
      setEditingEquipment(null);
      await loadWorkspace();
      showToast("Карточка удалена");
    });
  }

  async function submitRequest(event) {
    event.preventDefault();
    const validationError = validateRequestTitle(requestForm.title);
    if (validationError) {
      setError(validationError);
      showToast(validationError);
      return;
    }
    await runAction(async () => {
      await api.send("/api/requests", "POST", requestForm);
      setRequestForm({ title: "", category_id: "", requested_specs: "", justification: "" });
      await Promise.all([
        api.get("/api/requests").then((data) => setRequests(asArray(data))),
        api.get("/api/notifications").then((data) => setNotifications(asArray(data))),
        api.get("/api/cabinet").then(setCabinet),
      ]);
      showToast("Заявка отправлена");
    });
  }

  async function updateRequestStatus(item, patch) {
    await runAction(async () => {
      const saved = await api.send(`/api/requests/${item.id}`, "PUT", patch);
      setRequests(asArray(requests).map((row) => row.id === saved.id ? saved : row));
      await Promise.all([
        api.get("/api/requests").then((data) => setRequests(asArray(data))),
        api.get("/api/notifications").then((data) => setNotifications(asArray(data))),
      ]);
      showToast("Заявка сохранена");
    });
  }

  async function openNotification(item) {
    await runAction(async () => {
      await api.send(`/api/notifications/${item.id}/read`, "POST");
      setNotifications(asArray(notifications).map((row) => row.id === item.id ? { ...row, is_read: true } : row));
      setNotificationsOpen(false);
      if (item.link === "cabinet") setActiveView("cabinet");
      if (item.link === "requests" || String(item.link || "").startsWith("requests:")) {
        const requestId = Number(String(item.link || "").split(":")[1] || "");
        setSelectedRequestId(Number.isFinite(requestId) ? requestId : null);
        setActiveView("requests");
      }
    });
  }

  async function markAllNotificationsRead() {
    await runAction(async () => {
      await api.send("/api/notifications", "POST");
      setNotifications(asArray(notifications).map((row) => ({ ...row, is_read: true })));
    });
  }

  async function clearNotifications() {
    await runAction(async () => {
      await api.send("/api/notifications", "DELETE");
      setNotifications([]);
      setNotificationsOpen(false);
    });
  }

  async function saveProfile(profile) {
    await runAction(async () => {
      const saved = await api.send("/api/cabinet", "PUT", profile);
      setCabinet(saved);
      if (saved?.user?.id) {
        setUsers((rows) => asArray(rows).map((row) => row.id === saved.user.id ? { ...row, ...saved.user } : row));
      }
      const sessionData = await api.get("/api/auth/me");
      setSession({ user: sessionData.user || null, roles: asObject(sessionData.roles) });
      showToast("Профиль сохранен");
    });
  }

  async function saveAdSettings(event) {
    event.preventDefault();
    await runAction(async () => {
      const saved = await api.send("/api/ad/settings", "PUT", { ...normalizeAdSettings(adSettings), use_ssl: false });
      setAdSettings(normalizeAdSettings(saved));
      setAdTest(null);
      showToast("Настройки AD сохранены");
    });
  }

  async function testAdConnection() {
    await runAction(async () => {
      const result = await api.send("/api/ad/test", "POST", normalizeAdSettings(adSettings));
      setAdTest(result);
      showToast(result.message || "Подключение к AD проверено");
    });
  }

  async function submitMovement(event) {
    event.preventDefault();
    await runAction(async () => {
      const url = editingMovementId ? `/api/movements/${editingMovementId}` : "/api/movements";
      await api.send(url, editingMovementId ? "PATCH" : "POST", movementForm);
      setEditingMovementId(null);
      setMovementForm(initialMovementForm());
      await loadWorkspace();
      showToast(editingMovementId ? "Перемещение обновлено" : "Перемещение сохранено");
    });
  }

  function editMovement(item) {
    setEditingMovementId(item.id);
    setMovementForm(movementFormFromRow(item));
  }

  function resetMovementForm() {
    setEditingMovementId(null);
    setMovementForm(initialMovementForm());
  }

  async function archiveMovement(item, archived) {
    await runAction(async () => {
      await api.send(`/api/movements/${item.id}`, "PATCH", { archived });
      if (editingMovementId === item.id) resetMovementForm();
      await loadWorkspace();
      showToast(archived ? "Перемещение перенесено в архив" : "Перемещение возвращено из архива");
    });
  }

  async function submitWriteoff(event) {
    event.preventDefault();
    await runAction(async () => {
      const url = editingWriteoffId ? `/api/writeoffs/${editingWriteoffId}` : "/api/writeoffs";
      await api.send(url, editingWriteoffId ? "PATCH" : "POST", writeoffForm);
      setEditingWriteoffId(null);
      setWriteoffForm(initialWriteoffForm());
      await loadWorkspace();
      showToast(editingWriteoffId ? "Списание обновлено" : "Списание сохранено");
    });
  }

  function editWriteoff(item) {
    setEditingWriteoffId(item.id);
    setWriteoffForm(writeoffFormFromRow(item));
  }

  function resetWriteoffForm() {
    setEditingWriteoffId(null);
    setWriteoffForm(initialWriteoffForm());
  }

  async function archiveWriteoff(item, archived) {
    await runAction(async () => {
      await api.send(`/api/writeoffs/${item.id}`, "PATCH", { archived });
      if (editingWriteoffId === item.id) resetWriteoffForm();
      await loadWorkspace();
      showToast(archived ? "Списание перенесено в архив" : "Списание возвращено из архива");
    });
  }

  async function createInventorySession() {
    const name = window.prompt("Название инвентаризации", `Инвентаризация от ${new Date().toLocaleDateString("ru-RU")}`);
    if (!name) return;
    await runAction(async () => {
      const row = await api.send("/api/inventory/sessions", "POST", { title: name });
      setActiveSessionId(row.id);
      await loadInventory();
      showToast("Сессия создана");
    });
  }

  async function submitInventoryCheck() {
    if (!activeSessionId || !inventoryForm.equipment_id) return;
    await runAction(async () => {
      await api.send(`/api/inventory/sessions/${activeSessionId}/checks`, "POST", inventoryForm);
      await loadInventory();
      showToast("Проверка записана");
    });
  }

  async function archiveInventorySession(session, archived) {
    await runAction(async () => {
      const saved = await api.send(`/api/inventory/sessions/${session.id}`, "PATCH", { archived });
      setActiveSessionId(saved.id);
      await loadInventory();
      showToast(archived ? "Инвентаризация добавлена в архив" : "Инвентаризация возвращена из архива");
    });
  }

  function openEquipment(item = null) {
    setError("");
    setEditingEquipment(item);
    setEquipmentForm(item ? { ...emptyEquipment, ...item } : emptyEquipment);
    setEquipmentDialogOpen(true);
  }

  if (!sessionReady) {
    return (
      <section className="auth-shell session-loading">
        <div className="brand auth-brand">
          <div className="brand-mark">IT</div>
          <div>
            <strong>ИТ-Инвентаризация</strong>
            <span>Проверяем сессию</span>
          </div>
        </div>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="auth-shell">
        <div className="auth-card">
          <div className="auth-aside">
            <div className="brand auth-brand">
              <div className="brand-mark">IT</div>
              <div>
                <strong>ИТ-Инвентаризация</strong>
                <span>Контроль доступа и оборудования</span>
              </div>
            </div>
            <div className="auth-copy">
              <span className="auth-kicker">Единая точка входа</span>
              <h1>Рабочее пространство ИТ-отдела</h1>
              <p>Войдите в систему или создайте учетную запись сотрудника. Расширенные права назначает ИТ-администратор.</p>
            </div>
            <div className="auth-points" aria-label="Возможности системы">
              <span>Учет техники</span>
              <span>Заявки сотрудников</span>
              <span>Ролевой доступ</span>
            </div>
          </div>
          <div className="auth-main">
            <div className="auth-heading">
              <span className="auth-kicker">Авторизация</span>
              <h2>Добро пожаловать</h2>
            </div>
            <div className="auth-tabs">
              <button className={`auth-tab ${authMode === "login" ? "active" : ""}`} type="button" onClick={() => setAuthMode("login")}>Вход</button>
              <button className={`auth-tab ${authMode === "register" ? "active" : ""}`} type="button" onClick={() => setAuthMode("register")}>Регистрация</button>
            </div>
            <form className="auth-form active" onSubmit={submitAuth}>
              {authMode === "register" && (
                <>
                  <label>ФИО<input value={auth.full_name} onChange={(event) => setAuth({ ...auth, full_name: event.target.value })} required placeholder="Иванов Иван Иванович" /></label>
                  <label>Email<input value={auth.email} onChange={(event) => setAuth({ ...auth, email: event.target.value })} type="email" placeholder="user@company.ru" /></label>
                </>
              )}
              <label>Логин<input value={auth.username} onChange={(event) => setAuth({ ...auth, username: event.target.value })} required placeholder="Введите логин" /></label>
              <label>Пароль<input value={auth.password} onChange={(event) => setAuth({ ...auth, password: event.target.value })} type="password" required placeholder="Введите пароль" /></label>
              {authMode === "login" && (
                <>
                  <label className="checkline"><input checked={auth.ad} onChange={(event) => setAuth({ ...auth, ad: event.target.checked })} type="checkbox" /> Использовать вход через Active Directory</label>
                  <button className="text-button forgot-password" type="button" onClick={() => showToast("Для восстановления пароля обратитесь к ИТ-администратору.")}>Забыли пароль?</button>
                </>
              )}
              {error && <p className="auth-notice error">{error}</p>}
              <button className="primary-button auth-submit" disabled={busy} type="submit">{authMode === "login" ? "Войти" : "Создать учетную запись"}</button>
            </form>
          </div>
        </div>
        <Toast message={toast} />
      </section>
    );
  }

  return (
    <ErrorBoundary resetKey={activeView}>
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">IT</div>
          <div>
            <strong>ИТ-Инвентаризация</strong>
            <span>Учет оборудования</span>
          </div>
        </div>
        <nav className="nav" aria-label="Основные разделы">
          {nav.filter((item) => can(item[2])).map(([key, label]) => (
            <button className={`nav-item ${activeView === key ? "active" : ""}`} type="button" key={key} onClick={() => setActiveView(key)}>{label}</button>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{title[0]}</h1>
            <p>{title[1]}</p>
          </div>
          <div className="userbox">
            <NotificationBell
              items={notifications}
              open={notificationsOpen}
              setOpen={setNotificationsOpen}
              onOpen={openNotification}
              onClear={clearNotifications}
              onReadAll={markAllNotificationsRead}
            />
            <Avatar user={user} />
            <div className="user-meta">
              <strong>{user.full_name}</strong>
              <span>{asObject(session.roles)[user.role]?.name || user.role}</span>
            </div>
            <div className="user-actions">
              <ThemeToggle theme={theme} onToggle={toggleTheme} compact />
              <button className="settings-button" type="button" onClick={() => setActiveView("cabinet")} title="Настройки профиля">
                <Settings size={19} strokeWidth={2.2} aria-hidden="true" />
              </button>
              <button className="logout-button" type="button" onClick={logout}>Выйти</button>
            </div>
          </div>
        </header>

        {activeView === "dashboard" && can("equipment:view") && <Dashboard user={user} summary={summary} />}
        {activeView === "cabinet" && (
          <Cabinet
            cabinet={cabinet}
            canManageAd={can("users:manage")}
            adSettings={adSettings}
            setAdSettings={setAdSettings}
            adTest={adTest}
            onSaveProfile={saveProfile}
            onSaveAd={saveAdSettings}
            onTestAd={testAdConnection}
          />
        )}
        {activeView === "equipment" && (
          <EquipmentView
            canDownload={can("reports:view")}
            canWrite={can("equipment:write")}
            dictionaries={dictionaries}
            equipment={equipment}
            filters={filters}
            setFilters={setFilters}
            loadEquipment={loadEquipment}
            openEquipment={openEquipment}
            showToast={showToast}
          />
        )}
        {activeView === "movements" && can("lifecycle:manage") && (
          <MovementsView
            dictionaries={dictionaries}
            equipment={equipment}
            form={movementForm}
            setForm={setMovementForm}
            editingId={editingMovementId}
            selected={selectedMovementEquipment}
            movements={movements}
            onSubmit={submitMovement}
            onEdit={editMovement}
            onCancelEdit={resetMovementForm}
            onArchive={archiveMovement}
          />
        )}
        {activeView === "writeoffs" && can("lifecycle:manage") && (
          <WriteoffsView
            equipment={equipment}
            form={writeoffForm}
            setForm={setWriteoffForm}
            editingId={editingWriteoffId}
            selected={selectedWriteoffEquipment}
            writeoffs={writeoffs}
            onSubmit={submitWriteoff}
            onEdit={editWriteoff}
            onCancelEdit={resetWriteoffForm}
            onArchive={archiveWriteoff}
          />
        )}
        {activeView === "inventory" && can("inventory:write") && (
          <InventoryView
            dictionaries={dictionaries}
            equipment={equipment}
            sessions={sessions}
            activeSessionId={activeSessionId}
            setActiveSessionId={setActiveSessionId}
            report={inventoryReport}
            form={inventoryForm}
            setForm={setInventoryForm}
            createSession={createInventorySession}
            submitCheck={submitInventoryCheck}
            archiveSession={archiveInventorySession}
          />
        )}
        {activeView === "reports" && can("reports:view") && <ReportsView reports={reports} />}
        {activeView === "requests" && can(["requests:approve", "requests:create"]) && (
          <RequestsView
            canApprove={can("requests:approve")}
            canCreate={can("requests:create")}
            dictionaries={dictionaries}
            form={requestForm}
            requests={requests}
            selectedRequestId={selectedRequestId}
            setForm={setRequestForm}
            user={user}
            onCreate={submitRequest}
            onUpdate={updateRequestStatus}
          />
        )}
        {activeView === "users" && can("users:manage") && <UsersView users={users} setUsers={setUsers} dictionaries={dictionaries} roles={asObject(session.roles)} canManage={can("users:manage")} showToast={showToast} />}
        {activeView === "audit" && can("audit:view") && <AuditView rows={audit} reload={loadAudit} />}
      </main>

      {equipmentDialogOpen && (
        <EquipmentDialog
          dictionaries={dictionaries}
          form={equipmentForm}
          setForm={setEquipmentForm}
          editing={editingEquipment}
          error={error}
          busy={busy}
          onSave={saveEquipment}
          onClose={() => {
            setEquipmentDialogOpen(false);
            setEditingEquipment(null);
          }}
          onDelete={deleteEquipment}
          canDelete={can("equipment:delete")}
        />
      )}
      <Toast message={toast} />
    </div>
    </ErrorBoundary>
  );
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <main className="auth-shell">
          <section className="auth-main" style={{ maxWidth: 620 }}>
            <div className="auth-heading">
              <span className="auth-kicker">Ошибка интерфейса</span>
              <h2>Экран восстановлен</h2>
              <p>{this.state.error.message}</p>
            </div>
            <button className="primary-button" type="button" onClick={() => window.location.reload()}>Перезагрузить</button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}

/**
 * Показывает временное уведомление о результате действия или ошибке.
 */
function Toast({ message }) {
  return <div className={`toast ${message ? "visible" : ""}`}>{message}</div>;
}

/**
 * Кнопка переключения светлой и темной темы интерфейса.
 */
function ThemeToggle({ theme, onToggle, compact = false }) {
  const isDark = theme === "dark";
  const title = isDark ? "Переключить на светлую тему" : "Переключить на темную тему";
  if (compact) {
    return (
      <button className="theme-toggle topbar-theme-toggle" type="button" aria-pressed={isDark} onClick={onToggle} title={title} aria-label={title}>
        <span className="theme-toggle-icon" aria-hidden="true">
          {isDark ? <Moon size={17} strokeWidth={2.2} /> : <Sun size={17} strokeWidth={2.2} />}
        </span>
      </button>
    );
  }
  return (
    <button className="theme-toggle" type="button" aria-pressed={isDark} onClick={onToggle}>
      <span className="theme-toggle-icon" aria-hidden="true">
        {isDark ? <Moon size={16} strokeWidth={2.2} /> : <Sun size={16} strokeWidth={2.2} />}
      </span>
      <span>
        <strong>{isDark ? "Темная тема" : "Светлая тема"}</strong>
        <small>{isDark ? "Включена" : "Включена"}</small>
      </span>
      <span className="theme-toggle-track" aria-hidden="true">
        <span />
      </span>
    </button>
  );
}

/**
 * Отображает стартовую сводку по оборудованию и активным процессам.
 */
function Dashboard({ user, summary }) {
  const categories = asArray(summary?.by_category);
  const max = Math.max(...categories.map((item) => item.count), 1);
  const statuses = asArray(summary?.by_status);
  return (
    <section className="view active">
      <section className="overview-hero">
        <div>
          <span className="field-label">{user.role === "employee" ? "Личный режим" : "Рабочая панель"}</span>
          <h2>{user.role === "employee" ? "Личный кабинет сотрудника" : "Контроль ИТ-инвентаризации"}</h2>
          <p>{user.role === "employee" ? "Показана закрепленная техника и ваши заявки." : "Сводка по парку, гарантиям, состоянию и последним изменениям."}</p>
        </div>
        <div className="overview-status">
          {statuses.length ? statuses.map((item) => (
            <span key={item.name}>{item.label || item.name}: <strong>{item.count}</strong></span>
          )) : <span>Статусы появятся после загрузки оборудования</span>}
        </div>
      </section>
      <div className="metrics-grid">
        <Metric label={user.role === "employee" ? "Закреплено за мной" : "Всего единиц"} value={summary?.total || 0} />
        <Metric label="Балансовая стоимость" value={user.role === "employee" ? "скрыто" : money(summary?.value)} />
        <Metric label="Требует внимания" value={summary?.issues || 0} />
        <Metric label="Гарантия под контролем" value={summary?.warranty || 0} />
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head"><h2>Оборудование по категориям</h2></div>
          <div className="bar-list">
            {categories.length ? categories.map((item) => (
              <div className="bar-row" key={item.name}>
                <span>{item.name}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} /></div>
                <strong>{item.count}</strong>
              </div>
            )) : <Empty text="Нет данных" />}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>Недавние изменения</h2></div>
          <div className="equipment-card-list compact">
            {asArray(summary?.recent).length ? summary.recent.map((item) => <SmallEquipment item={item} key={item.id} />) : <Empty text="Нет изменений" />}
          </div>
        </section>
      </div>
    </section>
  );
}

/**
 * Показывает уведомления пользователя и действия массового прочтения или очистки.
 */
function NotificationBell({ items, open, setOpen, onOpen, onClear, onReadAll }) {
  const rows = asArray(items);
  const unread = rows.filter((item) => !item.is_read).length;
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open, setOpen]);

  return (
    <div className="notification-wrap" ref={wrapRef}>
      <button className={`notification-button ${unread ? "has-unread" : ""}`} type="button" onClick={() => setOpen(!open)} title="Уведомления">
        <Bell size={19} strokeWidth={2.2} aria-hidden="true" />
        {unread > 0 && <strong>{unread}</strong>}
      </button>
      {open && (
        <div className="notification-popover">
          <div className="notification-head">
            <strong>Уведомления</strong>
            <div className="notification-actions">
              <button className="text-button" disabled={!unread} type="button" onClick={onReadAll}>Прочитать все</button>
              <button className="text-button" disabled={!rows.length} type="button" onClick={onClear}>Очистить</button>
            </div>
          </div>
          <div className="notification-list">
            {rows.length ? rows.map((item) => (
              <button className={`notification-item ${item.is_read ? "" : "unread"}`} type="button" key={item.id} onClick={() => onOpen(item)}>
                <strong>{item.title}</strong>
                <span>{item.message}</span>
                <small>{shortDate(item.created_at)}</small>
              </button>
            )) : <Empty text="Новых уведомлений нет" />}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Отображает личный кабинет, профиль сотрудника, аватар и закрепленное оборудование.
 */
function Cabinet({
  cabinet,
  canManageAd,
  adSettings,
  setAdSettings,
  adTest,
  onSaveProfile,
  onSaveAd,
  onTestAd,
}) {
  const cabinetEquipment = asArray(cabinet?.equipment);
  const safeAdSettings = normalizeAdSettings(adSettings);
  const adChecks = asObject(adTest?.checks);
  const profileUser = asObject(cabinet?.user);
  const profileEmployee = asObject(cabinet?.employee);
  const canEditProfile = !!profileUser.can_edit_profile;
  const [profileDraft, setProfileDraft] = useState({ full_name: "", email: "", department: "", phone: "", avatar: "slate" });
  const [profileSaving, setProfileSaving] = useState(false);

  useEffect(() => {
    setProfileDraft({
      full_name: profileUser.profile_full_name || profileUser.full_name || "",
      email: profileUser.email || profileEmployee.email || "",
      department: profileEmployee.department || "",
      phone: profileEmployee.phone || "",
      avatar: avatarValue(profileUser.avatar),
    });
  }, [profileUser.id, profileUser.profile_full_name, profileUser.full_name, profileUser.email, profileUser.avatar, profileEmployee.email, profileEmployee.department, profileEmployee.phone]);

  async function submitProfile(event) {
    event.preventDefault();
    setProfileSaving(true);
    try {
      await onSaveProfile(profileDraft);
    } finally {
      setProfileSaving(false);
    }
  }

  return (
    <section className="view active">
      <section className="profile-hero">
        <div className="profile-person">
          <Avatar user={profileUser} className="profile-avatar" />
          <div>
            <span className="field-label">Профиль</span>
            <h2>{profileUser.full_name || profileUser.username || "Пользователь"}</h2>
            <p>{profileUser.email || "email не указан"} · {profileUser.role_name || profileUser.role || "роль не указана"}</p>
          </div>
        </div>
        <div className="profile-stats">
          <Metric label="Закреплено" value={cabinetEquipment.length} />
        </div>
      </section>

      <div className="profile-grid-layout">
        <section className="panel profile-card">
          <div className="panel-head"><h2>Личные данные</h2></div>
          <div className="avatar-settings">
            <span className="field-label">Аватар</span>
            <AvatarPicker value={profileUser.avatar} onChange={(avatar) => onSaveProfile({ avatar })} />
          </div>
          {canEditProfile ? (
            <form className="profile-edit-form" onSubmit={submitProfile}>
              <dl className="profile-grid readonly-profile-grid">
                <div><dt>Учетная запись</dt><dd>{profileUser.username || "не указана"}</dd></div>
                <div><dt>Роль</dt><dd>{profileUser.role_name || profileUser.role || "не указана"}</dd></div>
              </dl>
              <div className="profile-edit-grid">
                <label>ФИО<input value={profileDraft.full_name} onChange={(event) => setProfileDraft({ ...profileDraft, full_name: event.target.value })} required /></label>
                <label>Email<input value={profileDraft.email} onChange={(event) => setProfileDraft({ ...profileDraft, email: event.target.value })} type="email" /></label>
                <label>Отдел<input value={profileDraft.department} onChange={(event) => setProfileDraft({ ...profileDraft, department: event.target.value })} /></label>
                <label>Телефон<input value={profileDraft.phone} onChange={(event) => setProfileDraft({ ...profileDraft, phone: event.target.value })} /></label>
              </div>
              <div className="form-actions">
                <button className="primary-button" disabled={profileSaving} type="submit">Сохранить профиль</button>
              </div>
            </form>
          ) : (
            <dl className="profile-grid">
              <div><dt>Учетная запись</dt><dd>{profileUser.username || "не указана"}</dd></div>
              <div><dt>Email</dt><dd>{profileUser.email || "не указан"}</dd></div>
              <div><dt>Роль</dt><dd>{profileUser.role_name || profileUser.role || "не указана"}</dd></div>
              <div><dt>Сотрудник</dt><dd>{profileEmployee.full_name || "не привязан"}</dd></div>
              <div><dt>Отдел</dt><dd>{profileEmployee.department || "не указан"}</dd></div>
              <div><dt>Телефон</dt><dd>{profileEmployee.phone || "не указан"}</dd></div>
              {profileUser.ad_login && <div><dt>Источник</dt><dd>Active Directory</dd></div>}
            </dl>
          )}
        </section>
        <section className="panel profile-card">
          <div className="panel-head row-head"><h2>Закрепленное имущество</h2></div>
          <div className="equipment-card-list compact">{cabinetEquipment.length ? cabinetEquipment.map((item) => <SmallEquipment item={item} key={item.id} />) : <Empty text="Нет закрепленного имущества" />}</div>
        </section>
      </div>

      {canManageAd && (
        <section className="panel ad-panel">
          <div className="panel-head">
            <h2>Active Directory</h2>
            <p>Настройки входа через доменную учетную запись.</p>
          </div>
          <form className="ad-form" onSubmit={onSaveAd}>
            <label className="checkline ad-toggle">
              <input checked={!!safeAdSettings.enabled} onChange={(event) => setAdSettings({ ...safeAdSettings, enabled: event.target.checked })} type="checkbox" />
              Разрешить вход через AD
            </label>
            <div className="ad-connection-row">
              <label>Домен<input value={safeAdSettings.domain} onChange={(event) => setAdSettings({ ...safeAdSettings, domain: event.target.value })} placeholder="company.local" /></label>
              <label>Контроллер домена<input value={safeAdSettings.controller} onChange={(event) => setAdSettings({ ...safeAdSettings, controller: event.target.value, server: event.target.value })} placeholder="dc01.company.local или ldap://dc01.company.local:389" /></label>
              <label>Порт<input value={safeAdSettings.port} onChange={(event) => setAdSettings({ ...safeAdSettings, port: event.target.value })} type="number" min="1" max="65535" placeholder="389" /></label>
            </div>
            {adTest && (
              <div className={`auth-notice ${adTest.ok ? "success" : "error"}`}>
                <strong>{adTest.message}</strong>
                {Object.entries(adChecks).length > 0 && (
                  <div className="compact-list ad-test-list">
                    {Object.entries(adChecks).map(([name, check]) => (
                      <article className="list-item" key={name}>
                        <strong>{name.toUpperCase()} - {check.ok ? "OK" : "Ошибка"}</strong>
                        <span>{check.message || ""}</span>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={onTestAd}>Проверить подключение</button>
              <button className="primary-button" type="submit">Сохранить настройки</button>
            </div>
          </form>
        </section>
      )}
    </section>
  );
}

/**
 * Отображает реестр оборудования с фильтрами, экспортом и открытием карточки.
 */
function EquipmentView({ canDownload, canWrite, dictionaries, equipment, filters, setFilters, loadEquipment, openEquipment, showToast }) {
  const dict = normalizeDictionaries(dictionaries);
  const rows = asArray(equipment);
  const safeFilters = asObject(filters);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const downloadRef = useRef(null);
  function equipmentExportUrl(format) {
    const params = new URLSearchParams();
    Object.entries(safeFilters).forEach(([key, value]) => {
      if (value) params.set(key === "search" ? "q" : key, value);
    });
    const query = params.toString();
    return `/api/export/equipment.${format}${query ? `?${query}` : ""}`;
  }
  useEffect(() => {
    if (!downloadOpen) return undefined;
    function closeOnOutsideClick(event) {
      if (!downloadRef.current?.contains(event.target)) {
        setDownloadOpen(false);
      }
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [downloadOpen]);
  async function downloadEquipment(format) {
    setDownloadOpen(false);
    try {
      const response = await fetch(equipmentExportUrl(format), { credentials: "include" });
      if (!response.ok) {
        const text = await response.text();
        let detail = "";
        try {
          detail = JSON.parse(text)?.error || "";
        } catch {
          detail = text.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
        }
        throw new Error(detail || "Файл не удалось сформировать");
      }
      const blob = await response.blob();
      const fileBlob = new Blob([blob], { type: response.headers.get("content-type") || blob.type || "application/octet-stream" });
      const url = URL.createObjectURL(fileBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `equipment.${format}`;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      showToast?.(err.message || "Не удалось скачать файл");
    }
  }
  function applyFilterPatch(patch) {
    const next = { ...safeFilters, ...patch };
    setFilters(next);
    loadEquipment(next);
  }
  async function applyFilters(event) {
    event.preventDefault();
    await loadEquipment(safeFilters);
  }
  return (
    <section className="view active">
      <section className="panel filter-panel">
        <form className="toolbar" onSubmit={applyFilters}>
          <input value={safeFilters.search || ""} onChange={(event) => applyFilterPatch({ search: event.target.value })} type="search" placeholder="Поиск по номеру, названию, серийному номеру или сотруднику" />
          <Select value={safeFilters.status || ""} onChange={(value) => applyFilterPatch({ status: value })} items={dict.statuses} placeholder="Все статусы" />
          <Select value={safeFilters.category_id || ""} onChange={(value) => applyFilterPatch({ category_id: value })} items={dict.categories} placeholder="Все категории" />
          <Select value={safeFilters.location_id || ""} onChange={(value) => applyFilterPatch({ location_id: value })} items={dict.locations} placeholder="Все места" label={(item) => `${item.name}${item.room ? `, каб. ${item.room}` : ""}`} />
          <button className="ghost-button" type="button" onClick={() => { const next = { search: "", status: "", category_id: "", location_id: "" }; setFilters(next); loadEquipment(next); }}>Сбросить</button>
          {canDownload && (
            <details className="download-menu" open={downloadOpen} ref={downloadRef} onToggle={(event) => setDownloadOpen(event.currentTarget.open)}>
              <summary className="secondary-button toolbar-link" onClick={(event) => { event.preventDefault(); setDownloadOpen((open) => !open); }}>
                <Download size={16} aria-hidden="true" />
                <span>Скачать</span>
              </summary>
              <div className="download-menu-list">
                <button type="button" onClick={() => downloadEquipment("xls")}>Excel</button>
                <button type="button" onClick={() => downloadEquipment("pdf")}>PDF</button>
              </div>
            </details>
          )}
          {canWrite && <button className="primary-button" type="button" onClick={() => openEquipment(null)}>Добавить оборудование</button>}
        </form>
      </section>
      <div className="equipment-grid">
        {rows.length ? rows.map((item) => (
          <article className="equipment-card" key={item.id}>
            <div className="equipment-card-head">
              <div>
                <span className="field-label">{item.inventory_number}</span>
                <h3>{item.name}</h3>
              </div>
              <span className={`badge ${badgeClass(item.condition)}`}>{item.condition_label}</span>
            </div>
            <div className="equipment-card-meta">
              <span>{item.category_name || "Без категории"}</span>
              <span>{item.serial_number || "Серийный номер не указан"}</span>
            </div>
            <dl className="mini-details">
              <div><dt>Место</dt><dd>{item.location_name || "Не указано"}</dd></div>
              <div><dt>Сотрудник</dt><dd>{shortPersonName(item.employee_name) || "Не закреплено"}</dd></div>
              <div><dt>Статус</dt><dd>{item.status_label}</dd></div>
              <div><dt>IP / MAC</dt><dd>{[item.ip_address, item.mac_address].filter(Boolean).join(" / ") || "Не указано"}</dd></div>
            </dl>
            {item.specs && <p className="equipment-specs">{item.specs}</p>}
            <div className="equipment-card-actions">
              <button className="secondary-button" type="button" onClick={() => openEquipment(item)}>{canWrite ? "Открыть карточку" : "Просмотр"}</button>
            </div>
          </article>
        )) : <Empty text="Оборудование не найдено" />}
      </div>
    </section>
  );
}

/**
 * Отображает перемещения оборудования и форму создания или редактирования записи.
 */
function MovementsView({ dictionaries, equipment, form, setForm, editingId, selected, movements, onSubmit, onEdit, onCancelEdit, onArchive }) {
  const dict = normalizeDictionaries(dictionaries);
  const equipmentRows = asArray(equipment);
  const movementRows = asArray(movements);
  const [scope, setScope] = useState("active");
  const activeRows = movementRows.filter((item) => !item.archived);
  const archiveRows = movementRows.filter((item) => item.archived);
  const visibleRows = scope === "archive" ? archiveRows : activeRows;
  return (
    <section className="view active">
      <div className="lifecycle-layout">
        <section className="panel">
          <div className="panel-head row-head">
            <h2>{editingId ? "Редактирование перемещения" : "Новое перемещение"}</h2>
            {editingId && (
              <button className="ghost-button compact-action" type="button" onClick={onCancelEdit}>
                <X size={16} aria-hidden="true" />
                Отменить
              </button>
            )}
          </div>
          <form className="movement-form stacked" onSubmit={onSubmit}>
            <label>Инвентарный номер<Select value={form.equipment_id} onChange={(value) => setForm({ ...form, equipment_id: value, from_location_id: equipmentRows.find((item) => item.id === Number(value))?.location_id || "", employee_id: equipmentRows.find((item) => item.id === Number(value))?.employee_id || "" })} items={equipmentRows} placeholder="Выберите номер" label={(item) => `${item.inventory_number} · ${item.name}`} /></label>
            <label>Название оборудования<input value={selected?.name || ""} readOnly /></label>
            <label>Откуда<Select value={form.from_location_id} onChange={(value) => setForm({ ...form, from_location_id: value })} items={dict.locations} placeholder="Выберите место" /></label>
            <label>Куда<Select value={form.to_location_id} onChange={(value) => setForm({ ...form, to_location_id: value })} items={dict.locations} placeholder="Выберите место" /></label>
            <label>Сотрудник<Select value={form.employee_id} onChange={(value) => setForm({ ...form, employee_id: value })} items={dict.employees} placeholder="Не закреплять" label={(item) => `${item.full_name} (${item.department || "без отдела"})`} /></label>
            <label>Дата перемещения<input value={form.moved_at} onChange={(event) => setForm({ ...form, moved_at: event.target.value })} type="date" required /></label>
            <label>Статус<Select value={form.status} onChange={(value) => setForm({ ...form, status: value })} items={[["planned", "Запланировано"], ["done", "Выполнено"], ["cancelled", "Отменено"]]} /></label>
            <div className="form-actions"><button className="primary-button" type="submit">{editingId ? "Сохранить изменения" : "Сохранить"}</button></div>
          </form>
        </section>
        <section className="panel">
          <div className="panel-head row-head">
            <h2>История перемещений</h2>
            <div className="request-tabs lifecycle-tabs">
              <button className={`request-tab ${scope === "active" ? "active" : ""}`} type="button" onClick={() => setScope("active")}>Актуальные ({activeRows.length})</button>
              <button className={`request-tab ${scope === "archive" ? "active" : ""}`} type="button" onClick={() => setScope("archive")}>Архив ({archiveRows.length})</button>
            </div>
          </div>
          <div className="timeline-list">
            {visibleRows.length ? visibleRows.map((item) => (
              <article className="timeline-item" key={item.id}>
                <div className="timeline-date"><strong>{shortDate(item.moved_at)}</strong><span>{item.status_label || item.status}</span></div>
                <div>
                  <strong>{item.inventory_number} · {item.equipment_name}</strong>
                  <span>{item.from_location_name || "Не указано"} → {item.to_location_name || "Не указано"}</span>
                  <span>{item.employee_name || "Не закреплено"}</span>
                  <div className="timeline-actions">
                    <button className="secondary-button compact-action" type="button" onClick={() => onEdit(item)}>
                      <Pencil size={16} aria-hidden="true" />
                      Изменить
                    </button>
                    {(item.status === "done" || item.archived) && (
                      <button className="ghost-button compact-action" type="button" onClick={async () => { await onArchive(item, !item.archived); setScope(item.archived ? "active" : "archive"); }}>
                        {item.archived ? <RotateCcw size={16} aria-hidden="true" /> : <Archive size={16} aria-hidden="true" />}
                        {item.archived ? "Вернуть из архива" : "Добавить в архив"}
                      </button>
                    )}
                  </div>
                </div>
              </article>
            )) : <Empty text={scope === "archive" ? "Архив перемещений пуст" : "Перемещений пока нет"} />}
          </div>
        </section>
      </div>
    </section>
  );
}

/**
 * Отображает списания оборудования и форму подготовки акта списания.
 */
function WriteoffsView({ equipment, form, setForm, editingId, selected, writeoffs, onSubmit, onEdit, onCancelEdit, onArchive }) {
  const equipmentRows = asArray(equipment);
  const writeoffRows = asArray(writeoffs);
  const [scope, setScope] = useState("active");
  const activeRows = writeoffRows.filter((item) => !item.archived);
  const archiveRows = writeoffRows.filter((item) => item.archived);
  const visibleRows = scope === "archive" ? archiveRows : activeRows;
  return (
    <section className="view active">
      <div className="lifecycle-layout">
        <section className="panel">
          <div className="panel-head row-head">
            <h2>{editingId ? "Редактирование списания" : "Новое списание"}</h2>
            {editingId && (
              <button className="ghost-button compact-action" type="button" onClick={onCancelEdit}>
                <X size={16} aria-hidden="true" />
                Отменить
              </button>
            )}
          </div>
          <form className="movement-form stacked" onSubmit={onSubmit}>
            <label>Инвентарный номер<Select value={form.equipment_id} onChange={(value) => setForm({ ...form, equipment_id: value })} items={equipmentRows} placeholder="Выберите номер" label={(item) => `${item.inventory_number} · ${item.name}`} /></label>
            <label>Название оборудования<input value={selected?.name || ""} readOnly /></label>
            <label>Дата списания<input value={form.writeoff_date} onChange={(event) => setForm({ ...form, writeoff_date: event.target.value })} type="date" required /></label>
            <label>Статус<Select value={form.status} onChange={(value) => setForm({ ...form, status: value })} items={[["prepared", "Подготовлено"], ["review", "На согласовании"], ["written_off", "Списано"], ["rejected", "Отклонено"]]} /></label>
            <label className="wide">Причина списания<textarea value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} rows="3" required /></label>
            <label className="wide">Комиссия / ответственный<textarea value={form.commission} onChange={(event) => setForm({ ...form, commission: event.target.value })} rows="2" /></label>
            <div className="form-actions"><button className="primary-button" type="submit">{editingId ? "Сохранить изменения" : "Сохранить"}</button></div>
          </form>
        </section>
        <section className="panel">
          <div className="panel-head row-head">
            <h2>История списаний</h2>
            <div className="request-tabs lifecycle-tabs">
              <button className={`request-tab ${scope === "active" ? "active" : ""}`} type="button" onClick={() => setScope("active")}>Актуальные ({activeRows.length})</button>
              <button className={`request-tab ${scope === "archive" ? "active" : ""}`} type="button" onClick={() => setScope("archive")}>Архив ({archiveRows.length})</button>
            </div>
          </div>
          <div className="timeline-list">
            {visibleRows.length ? visibleRows.map((item) => (
              <article className="timeline-item" key={item.id}>
                <div className="timeline-date"><strong>{shortDate(item.writeoff_date)}</strong><span>{item.status_label || item.status}</span></div>
                <div>
                  <strong>{item.inventory_number} · {item.equipment_name}</strong>
                  <span>{item.reason || "Причина не указана"}</span>
                  <span>{item.commission || "Комиссия не указана"}</span>
                  <div className="timeline-actions">
                    <button className="secondary-button compact-action" type="button" onClick={() => onEdit(item)}>
                      <Pencil size={16} aria-hidden="true" />
                      Изменить
                    </button>
                    {(item.status === "written_off" || item.archived) && (
                      <button className="ghost-button compact-action" type="button" onClick={async () => { await onArchive(item, !item.archived); setScope(item.archived ? "active" : "archive"); }}>
                        {item.archived ? <RotateCcw size={16} aria-hidden="true" /> : <Archive size={16} aria-hidden="true" />}
                        {item.archived ? "Вернуть из архива" : "Добавить в архив"}
                      </button>
                    )}
                  </div>
                </div>
              </article>
            )) : <Empty text={scope === "archive" ? "Архив списаний пуст" : "Списаний пока нет"} />}
          </div>
        </section>
      </div>
    </section>
  );
}

/**
 * Отображает инвентаризации, форму проверки и отчет по выбранной сессии.
 */
function InventoryView({ dictionaries, equipment, sessions, activeSessionId, setActiveSessionId, report, form, setForm, createSession, submitCheck, archiveSession }) {
  const dict = normalizeDictionaries(dictionaries);
  const equipmentRows = asArray(equipment);
  const sessionRows = asArray(sessions);
  const [scope, setScope] = useState("active");
  const activeRows = sessionRows.filter((session) => !session.archived);
  const archiveRows = sessionRows.filter((session) => session.archived);
  const visibleRows = scope === "archive" ? archiveRows : activeRows;
  const selectedSession = report?.session || sessionRows.find((session) => session.id === activeSessionId);
  return (
    <section className="view active">
      <div className="inventory-layout inventory-board">
        <section className="panel">
          <div className="panel-head row-head">
            <h2>Сессии инвентаризации</h2>
            <button className="secondary-button" type="button" onClick={createSession}>Новая</button>
          </div>
          <div className="request-tabs lifecycle-tabs">
            <button className={`request-tab ${scope === "active" ? "active" : ""}`} type="button" onClick={() => setScope("active")}>Актуальные ({activeRows.length})</button>
            <button className={`request-tab ${scope === "archive" ? "active" : ""}`} type="button" onClick={() => setScope("archive")}>Архив ({archiveRows.length})</button>
          </div>
          <div className="compact-list">{visibleRows.length ? visibleRows.map((session) => (
            <article className={`list-item session-item ${session.id === activeSessionId ? "active" : ""}`} key={session.id} onClick={() => setActiveSessionId(session.id)}>
              <strong>{session.title}</strong><span>{session.status_label || session.status} · {session.checked_count}/{session.total_count} проверено · {shortDate(session.started_at)}</span>
            </article>
          )) : <Empty text={scope === "archive" ? "Архив инвентаризаций пуст" : "Сессий пока нет"} />}</div>
        </section>
        <section className="panel">
          <div className="panel-head row-head">
            <h2>{selectedSession?.title || "Проверка оборудования"}</h2>
            {selectedSession && (
              <button
                className="ghost-button compact-action"
                type="button"
                onClick={async () => {
                  await archiveSession(selectedSession, !selectedSession.archived);
                  setScope(selectedSession.archived ? "active" : "archive");
                }}
              >
                {selectedSession.archived ? <RotateCcw size={16} aria-hidden="true" /> : <Archive size={16} aria-hidden="true" />}
                {selectedSession.archived ? "Вернуть из архива" : "Добавить в архив"}
              </button>
            )}
          </div>
          <div className="inventory-actions">
            <Select value={form.equipment_id} onChange={(value) => setForm({ ...form, equipment_id: value })} items={equipmentRows} placeholder="Выберите оборудование" label={(item) => `${item.inventory_number} · ${item.name}`} disabled={selectedSession?.archived} />
            <Select value={form.result} onChange={(value) => setForm({ ...form, result: value })} items={[["found", "Найдено"], ["missing", "Не найдено"], ["moved", "Перемещено"]]} disabled={selectedSession?.archived} />
            <Select value={form.condition} onChange={(value) => setForm({ ...form, condition: value })} items={dict.conditions} disabled={selectedSession?.archived} />
            <button className="primary-button" type="button" onClick={submitCheck} disabled={selectedSession?.archived}>Отметить</button>
          </div>
          <div className="split-lists">
            <div className="inventory-column"><h3>Проверено</h3><div className="equipment-card-list compact">{asArray(report?.checked).length ? report.checked.map((item) => <SmallEquipment item={item} key={item.id} extra={`${item.result_label || item.result} · ${item.condition_label || item.condition}`} />) : <Empty text="Пока ничего не проверено" />}</div></div>
            <div className="inventory-column"><h3>Осталось проверить</h3><div className="equipment-card-list compact">{asArray(report?.missing).length ? report.missing.map((item) => <SmallEquipment item={item} key={item.id} />) : <Empty text="Все оборудование проверено" />}</div></div>
          </div>
        </section>
      </div>
    </section>
  );
}

/**
 * Отображает аналитические отчеты по стоимости, состояниям, гарантиям и инфраструктуре.
 */
function ReportsView({ reports }) {
  const [tab, setTab] = useState("main");
  const ageRows = asArray(reports?.age);
  const warrantyRows = asArray(reports?.warranty);
  const movementRows = asArray(reports?.recent_movements);
  const writeoffRows = asArray(reports?.recent_writeoffs);
  const inventoryRows = asArray(reports?.inventory_rows);
  const categoryRows = asArray(reports?.category_rows);
  const locationRows = asArray(reports?.location_rows);
  const employeeRows = asArray(reports?.employee_rows);
  const statusRows = asArray(reports?.status_rows);
  const conditionRows = asArray(reports?.condition_rows);
  const network = asObject(reports?.network_summary);
  const expiringDomains = asArray(reports?.expiring_domains);
  return (
    <section className="view active">
      <div className="report-tabs">
        <button className={`report-tab ${tab === "main" ? "active" : ""}`} type="button" onClick={() => setTab("main")}>Основное</button>
        <button className={`report-tab ${tab === "other" ? "active" : ""}`} type="button" onClick={() => setTab("other")}>Прочее</button>
      </div>

      {tab === "main" && (
        <div className="reports-grid">
          <section className="panel report-card">
            <div className="panel-head"><h2>Возрастная структура парка</h2></div>
            <div className="bar-list">{ageRows.length ? ageRows.map((item) => <Bar item={item} key={item.name} />) : <Empty text="Нет данных" />}</div>
          </section>
          <section className="panel report-card">
            <div className="panel-head"><h2>Гарантийные риски</h2></div>
            <div className="equipment-card-list compact">{warrantyRows.length ? warrantyRows.map((item) => <SmallEquipment item={item} key={item.id} extra={`${item.warranty_until ? `гарантия до ${shortDate(item.warranty_until)}` : "гарантия не указана"} · ${item.location_name || "место не указано"}`} />) : <Empty text="Нет рисков по гарантии" />}</div>
          </section>
          <section className="panel report-card">
            <div className="panel-head"><h2>Статусы жизненного цикла</h2></div>
            <div className="report-summary">
              <div><span>Перемещения</span><strong>{asArray(reports?.movement_status_rows).reduce((sum, item) => sum + Number(item.count || 0), 0)}</strong></div>
              <div><span>Списания</span><strong>{asArray(reports?.writeoff_status_rows).reduce((sum, item) => sum + Number(item.count || 0), 0)}</strong></div>
              <div><span>Инвентаризаций</span><strong>{inventoryRows.length}</strong></div>
            </div>
          </section>
          <SimpleTable
            title="Последние перемещения"
            columns={["Дата", "Оборудование", "Маршрут", "Статус"]}
            rows={movementRows.map((item) => [shortDate(item.moved_at), `${item.inventory_number} · ${item.equipment_name}`, `${item.from_location_name || "Не указано"} → ${item.to_location_name || "Не указано"}`, item.status_label || item.status])}
            emptyText="Перемещений нет"
          />
          <SimpleTable
            title="Последние списания"
            columns={["Дата", "Оборудование", "Причина", "Статус"]}
            rows={writeoffRows.map((item) => [shortDate(item.writeoff_date), `${item.inventory_number} · ${item.equipment_name}`, item.reason || "Не указана", item.status_label || item.status])}
            emptyText="Списаний нет"
          />
          <SimpleTable
            title="Инвентаризация"
            columns={["Сессия", "Статус", "Проверено", "Архив"]}
            rows={inventoryRows.map((item) => [item.title, item.status_label || item.status, `${item.checked_count}/${item.total_count}`, item.archived ? "Да" : "Нет"])}
            emptyText="Сессий инвентаризации нет"
          />
        </div>
      )}

      {tab === "other" && (
        <div className="reports-grid">
          <section className="panel report-card">
            <div className="panel-head"><h2>Категории оборудования</h2></div>
            <div className="bar-list">{categoryRows.length ? categoryRows.map((item) => <Bar item={item} key={item.name} />) : <Empty text="Нет данных" />}</div>
          </section>
          <section className="panel report-card">
            <div className="panel-head"><h2>Состояние оборудования</h2></div>
            <div className="bar-list">{conditionRows.length ? conditionRows.map((item) => <Bar item={item} key={item.name} />) : <Empty text="Нет данных" />}</div>
          </section>
          <section className="panel report-card">
            <div className="panel-head"><h2>Инфраструктура</h2></div>
            <div className="report-summary">
              <div><span>Сети / VLAN</span><strong>{network.networks || 0} / {network.vlans || 0}</strong></div>
              <div><span>IP занято / свободно</span><strong>{network.ip_used || 0} / {network.ip_free || 0}</strong></div>
              <div><span>Домены / каналы / телефония</span><strong>{network.domains || 0} / {network.internet_links || 0} / {network.telephony_lines || 0}</strong></div>
            </div>
          </section>
          <SimpleTable
            title="Распределение по локациям"
            columns={["Локация", "Кол-во", "Стоимость"]}
            rows={locationRows.map((item) => [item.name, item.count, money(item.value)])}
            emptyText="Нет данных по локациям"
          />
          <SimpleTable
            title="Закрепление за сотрудниками"
            columns={["Сотрудник", "Отдел", "Кол-во"]}
            rows={employeeRows.map((item) => [item.name, item.department || "не указан", item.count])}
            emptyText="Нет закрепленного оборудования"
          />
          <SimpleTable
            title="Стоимость по статусам"
            columns={["Статус", "Кол-во", "Стоимость"]}
            rows={statusRows.map((item) => [item.name, item.count, money(item.value)])}
            emptyText="Нет данных по статусам"
          />
          <SimpleTable
            title="Домены с истекающим сроком"
            columns={["Домен", "Регистратор", "Истекает"]}
            rows={expiringDomains.map((item) => [item.name, item.registrar || "не указан", shortDate(item.expires_at)])}
            emptyText="Нет доменов с истекающим сроком"
          />
        </div>
      )}
    </section>
  );
}

const requestStatusOptions = [
  ["review", "На рассмотрении"],
  ["approved", "В работе"],
  ["rejected", "Отклонено"],
  ["done", "Выполнено"],
];

/**
 * Возвращает человекочитаемый статус заявки.
 */
function requestStatusLabel(item) {
  return requestStatusOptions.find(([value]) => value === item.status)?.[1] || item.status_label || item.status;
}

/**
 * Отображает заявки сотрудников, форму создания и блок принятия решения.
 */
function RequestsView({ requests, dictionaries, form, selectedRequestId, setForm, user, canApprove, canCreate, onCreate, onUpdate }) {
  const rows = asArray(requests);
  const dict = normalizeDictionaries(dictionaries);
  const [drafts, setDrafts] = useState({});
  const [expandedId, setExpandedId] = useState(null);
  const [requestScope, setRequestScope] = useState("active");
  const showArchiveTabs = canCreate && !canApprove;
  const visibleRows = showArchiveTabs
    ? rows.filter((item) => requestScope === "archive" ? item.archived_by_requester : !item.archived_by_requester)
    : rows;
  const activeCount = rows.filter((item) => !item.archived_by_requester).length;
  const archiveCount = rows.filter((item) => item.archived_by_requester).length;

  useEffect(() => {
    const selected = rows.find((item) => item.id === selectedRequestId);
    if (selected) {
      if (showArchiveTabs) setRequestScope(selected.archived_by_requester ? "archive" : "active");
      setExpandedId(selectedRequestId);
    }
  }, [selectedRequestId, rows, showArchiveTabs]);

  function draftFor(item) {
    return drafts[item.id] || {
      title: item.title || "",
      category_id: item.category_id || "",
      requested_specs: item.requested_specs || "",
      justification: item.justification || "",
      status: item.status || "review",
      decision_reason: item.decision_reason || "",
    };
  }

  function setDraft(item, patch) {
    setDrafts({ ...drafts, [item.id]: { ...draftFor(item), ...patch } });
  }

  async function submitApproval(item) {
    const draft = draftFor(item);
    await onUpdate(item, { status: draft.status, decision_reason: draft.decision_reason });
    setDrafts({ ...drafts, [item.id]: { status: draft.status, decision_reason: draft.decision_reason } });
  }

  async function takeInWork(item) {
    await onUpdate(item, { take_in_work: true });
    setDrafts({ ...drafts, [item.id]: { ...draftFor(item), status: "approved" } });
  }

  async function submitOwn(item) {
    const draft = draftFor(item);
    await onUpdate(item, {
      title: draft.title,
      category_id: draft.category_id,
      requested_specs: draft.requested_specs,
      justification: draft.justification,
    });
    setExpandedId(null);
  }

  async function archiveRequest(item, archived) {
    await onUpdate(item, { archived_by_requester: archived });
    setExpandedId(null);
    setRequestScope(archived ? "archive" : "active");
  }

  return (
    <section className="view active">
      {canCreate && (
        <section className="panel">
          <div className="panel-head"><h2>Новая заявка</h2></div>
          <form className="request-form" onSubmit={onCreate}>
            <label>Тема заявки<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required minLength="8" maxLength="120" placeholder="Например: требуется ноутбук" /></label>
            <label>Категория оборудования<Select value={form.category_id} onChange={(value) => setForm({ ...form, category_id: value })} items={dict.categories} placeholder="Не выбрана" /></label>
            <label>Описание<textarea value={form.requested_specs} onChange={(event) => setForm({ ...form, requested_specs: event.target.value })} rows="3" /></label>
            <label>Обоснование<textarea value={form.justification} onChange={(event) => setForm({ ...form, justification: event.target.value })} rows="3" /></label>
            <button className="primary-button" type="submit">Отправить заявку</button>
          </form>
        </section>
      )}
      <section className="panel">
        <div className="panel-head row-head">
          <div>
            <h2>{canApprove ? "Заявки сотрудников" : "Мои заявки"}</h2>
          </div>
          {showArchiveTabs && (
            <div className="request-tabs">
              <button className={`request-tab ${requestScope === "active" ? "active" : ""}`} type="button" onClick={() => setRequestScope("active")}>Актуальные ({activeCount})</button>
              <button className={`request-tab ${requestScope === "archive" ? "active" : ""}`} type="button" onClick={() => setRequestScope("archive")}>Архив ({archiveCount})</button>
            </div>
          )}
        </div>
        <div className="request-worklist">
          {visibleRows.length ? visibleRows.map((item) => {
            const draft = draftFor(item);
            const isOwner = item.user_id === user?.id;
            const canEditOwn = canCreate && isOwner;
            const isExpanded = expandedId === item.id;
            const canArchive = canEditOwn && item.status === "done";
            const canTakeInWork = canApprove && !item.decided_by_id && !["done", "rejected"].includes(item.status);
            return (
              <article className={`request-card ${selectedRequestId === item.id ? "selected" : ""}`} key={item.id}>
                <div className="request-card-main">
                  <div>
                    <span className={`badge ${badgeClass(item.status)}`}>{requestStatusLabel(item)}</span>
                    <h3>{item.title}</h3>
                    <p>{item.justification || "Обоснование не указано"}</p>
                  </div>
                  <dl className="request-meta">
                    <div><dt>Автор</dt><dd>{item.requester_name || item.employee_name || "не указан"}</dd></div>
                    <div><dt>Отдел</dt><dd>{item.employee_department || "не указан"}</dd></div>
                    <div><dt>Категория</dt><dd>{item.category_name || "без категории"}</dd></div>
                    <div><dt>Принял заявку</dt><dd>{item.decided_by_name || "не назначен"}</dd></div>
                    <div><dt>Создана</dt><dd>{shortDate(item.created_at)}</dd></div>
                  </dl>
                  {canTakeInWork && (
                    <div className="equipment-card-actions">
                      <button className="secondary-button" type="button" onClick={() => takeInWork(item)}>
                        Взять в работу
                      </button>
                    </div>
                  )}
                  <div className="request-description">
                    <div className="request-note request-note-description">
                      <span className="field-label">Описание</span>
                      <p>{item.requested_specs || "Не указано"}</p>
                    </div>
                    {item.decision_reason && (
                      <div className="request-note request-answer">
                        <span className="field-label">Ответ принявшего заявку</span>
                        <p>{item.decision_reason}</p>
                      </div>
                    )}
                  </div>
                  {canEditOwn && (
                    <div className="equipment-card-actions">
                      <button className="secondary-button" type="button" onClick={() => setExpandedId(isExpanded ? null : item.id)}>
                        {isExpanded ? "Закрыть" : "Открыть"}
                      </button>
                      {canArchive && (
                        <button className="ghost-button" type="button" onClick={() => archiveRequest(item, !item.archived_by_requester)}>
                          {item.archived_by_requester ? "Вернуть" : "В архив"}
                        </button>
                      )}
                    </div>
                  )}
                </div>
                {isExpanded && canEditOwn && (
                  <div className="request-response">
                    <label>Тема заявки<input value={draft.title} onChange={(event) => setDraft(item, { title: event.target.value })} required minLength="8" maxLength="120" /></label>
                    <label>Категория оборудования<Select value={draft.category_id || ""} onChange={(value) => setDraft(item, { category_id: value })} items={dict.categories} placeholder="Не выбрана" /></label>
                    <label>Описание<textarea value={draft.requested_specs} onChange={(event) => setDraft(item, { requested_specs: event.target.value })} rows="3" /></label>
                    <label>Обоснование<textarea value={draft.justification} onChange={(event) => setDraft(item, { justification: event.target.value })} rows="3" /></label>
                    <button className="primary-button" type="button" onClick={() => submitOwn(item)}>Сохранить заявку</button>
                  </div>
                )}
                {canApprove && (
                  <div className="request-response">
                    <label>Статус<Select value={draft.status} onChange={(value) => setDraft(item, { status: value })} items={requestStatusOptions} /></label>
                    <label>Принял заявку<input value={item.decided_by_name || "не назначен"} disabled /></label>
                    <label>Ответ заявителю<textarea value={draft.decision_reason} onChange={(event) => setDraft(item, { decision_reason: event.target.value })} rows="3" placeholder="Комментарий, причина отказа или что будет сделано" /></label>
                    <button className="primary-button" type="button" onClick={() => submitApproval(item)}>Сохранить ответ</button>
                  </div>
                )}
              </article>
            );
          }) : <Empty text={showArchiveTabs && requestScope === "archive" ? "Архив пуст" : "Заявок пока нет"} />}
        </div>
      </section>
    </section>
  );
}

/**
 * Отображает пользователей, роли, профильные данные и административные действия.
 */
function UsersView({ users, setUsers, dictionaries, roles, canManage, showToast }) {
  const [expandedId, setExpandedId] = useState(null);
  const [passwords, setPasswords] = useState({});
  const [profileDrafts, setProfileDrafts] = useState({});
  const dict = normalizeDictionaries(dictionaries);
  const userRows = asArray(users);
  const roleRows = Object.entries(asObject(roles)).map(([id, item]) => [id, asObject(item).name || id]);
  const adCount = userRows.filter((row) => row.ad_login).length;
  function localProfileDraft(user) {
    return profileDrafts[user.id] || {
      full_name: user.profile_full_name || user.full_name || "",
      email: user.email || user.employee_email || "",
      department: user.employee_department || "",
      phone: user.employee_phone || "",
    };
  }
  function setLocalProfileDraft(user, patch) {
    setProfileDrafts({ ...profileDrafts, [user.id]: { ...localProfileDraft(user), ...patch } });
  }
  async function save(user, patch) {
    if (!canManage) return;
    const saved = await api.send(`/api/users/${user.id}`, "PUT", patch);
    setUsers(userRows.map((item) => item.id === saved.id ? saved : item));
  }
  async function saveLocalProfile(user) {
    if (!canManage) return;
    const draft = localProfileDraft(user);
    const saved = await api.send(`/api/users/${user.id}`, "PUT", draft);
    setUsers(userRows.map((item) => item.id === saved.id ? saved : item));
    setProfileDrafts({ ...profileDrafts, [user.id]: {
      full_name: saved.profile_full_name || saved.full_name || "",
      email: saved.email || saved.employee_email || "",
      department: saved.employee_department || "",
      phone: saved.employee_phone || "",
    } });
  }
  async function changePassword(user) {
    if (!canManage) return;
    const password = (passwords[user.id] || "").trim();
    if (password.length < 6) {
      showToast?.("Пароль должен содержать не менее 6 символов");
      return;
    }
    const saved = await api.send(`/api/users/${user.id}`, "PUT", { password });
    setUsers(userRows.map((item) => item.id === saved.id ? saved : item));
    setPasswords({ ...passwords, [user.id]: "" });
    showToast?.("Пароль пользователя изменен");
  }
  return (
    <section className="view active">
      <section className="panel">
        <div className="panel-head row-head">
          <div>
            <h2>Учетные записи и роли</h2>
            <p>{userRows.length} пользователей · {adCount} через AD · {userRows.length - adCount} локально</p>
          </div>
        </div>
        <div className="user-admin-list">
          {userRows.map((row) => (
            <article className={`user-admin-item ${expandedId === row.id ? "expanded" : ""}`} key={row.id}>
              <div className="user-admin-main">
                <div className="user-identity">
                  <Avatar user={row} className="small" />
                  <div>
                    <strong>{row.full_name || row.username}</strong>
                    <span>{row.username} · {row.email || "email не указан"}</span>
                  </div>
                </div>
                {canManage ? (
                  <label className="user-control">Роль<Select value={row.role} onChange={(value) => save(row, { role: value })} items={roleRows} /></label>
                ) : (
                  <div className="user-info-block"><span className="field-label">Роль</span><strong>{row.role_name || row.role}</strong><span>{row.is_superuser ? "суперпользователь" : row.is_staff ? "staff" : "обычная учетная запись"}</span></div>
                )}
                {canManage ? (
                  <label className="user-control">Сотрудник<Select value={row.employee_id || ""} onChange={(value) => save(row, { employee_id: value })} items={dict.employees} placeholder="Не привязан" label={(item) => item.full_name} /></label>
                ) : (
                  <div className="user-info-block"><span className="field-label">Сотрудник</span><strong>{row.employee_name || "Не привязан"}</strong><span>{row.employee_email || "email сотрудника не указан"}</span></div>
                )}
                <div className="user-info-block">
                  <span className="field-label">Отдел</span>
                  <strong>{row.employee_department || "Не указан"}</strong>
                  <span>{row.employee_phone || "номер не указан"}</span>
                </div>
                <div className="user-info-block">
                  <span className={`badge ${row.ad_login ? "" : "warn"}`}>{row.ad_login ? "AD" : "локально"}</span>
                  <strong>{row.ad_login || "без AD-логина"}</strong>
                  <span>{row.last_login ? `вход ${shortDate(row.last_login)}` : "еще не входил"}</span>
                </div>
                <div className="user-admin-actions">
                  <span className={`badge ${row.is_active ? "" : "danger"}`}>{row.is_active ? "активен" : "отключен"}</span>
                  <span className={`badge ${row.two_factor_enabled ? "" : "warn"}`}>{row.two_factor_enabled ? "2FA включено" : "2FA выключено"}</span>
                  <div>
                    {canManage && <button className="text-button" type="button" onClick={() => save(row, { two_factor_enabled: !row.two_factor_enabled })}>2FA</button>}
                    <button className="text-button" type="button" onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}>{expandedId === row.id ? "Скрыть" : canManage ? "Пароль" : "Подробнее"}</button>
                  </div>
                </div>
              </div>
              {expandedId === row.id && (
                <div className={`user-admin-details ${canManage && row.can_edit_profile ? "with-profile-edit" : ""}`}>
                  {canManage && row.can_edit_profile && (
                    <form className="user-profile-edit" onSubmit={(event) => { event.preventDefault(); saveLocalProfile(row); }}>
                      <label>ФИО<input value={localProfileDraft(row).full_name} onChange={(event) => setLocalProfileDraft(row, { full_name: event.target.value })} required /></label>
                      <label>Email<input value={localProfileDraft(row).email} onChange={(event) => setLocalProfileDraft(row, { email: event.target.value })} type="email" /></label>
                      <label>Отдел<input value={localProfileDraft(row).department} onChange={(event) => setLocalProfileDraft(row, { department: event.target.value })} /></label>
                      <label>Телефон<input value={localProfileDraft(row).phone} onChange={(event) => setLocalProfileDraft(row, { phone: event.target.value })} /></label>
                      <button className="primary-button" type="submit">Сохранить данные</button>
                    </form>
                  )}
                  {canManage && (
                    <div className="avatar-settings">
                      <span className="field-label">Аватар</span>
                      <AvatarPicker value={row.avatar} onChange={(avatar) => save(row, { avatar })} />
                    </div>
                  )}
                  <div>
                    <span className="field-label">Контакты сотрудника</span>
                    <strong>{row.employee_phone || "Телефон не указан"}</strong>
                    <span>{row.employee_email || row.email || "email не указан"}</span>
                  </div>
                  {canManage && (
                    <div className="password-card">
                      <div>
                        <span className="field-label">Смена пароля</span>
                        <span> Минимум 6 символов</span>
                      </div>
                      <div className="password-edit">
                        <input value={passwords[row.id] || ""} onChange={(event) => setPasswords({ ...passwords, [row.id]: event.target.value })} type="password" placeholder="Новый пароль" minLength="6" />
                        <button className="secondary-button" type="button" onClick={() => changePassword(row)}>Сменить пароль</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </article>
          ))}
          {!userRows.length && <Empty text="Пользователи не найдены" />}
        </div>
      </section>
    </section>
  );
}

const auditActionLabels = {
  "auth.login": "Вход в систему",
  "auth.logout": "Выход из системы",
  "auth.register": "Создана локальная учетная запись",
  "ad.settings.updated": "Настройки Active Directory обновлены",
  "ad.connection.tested": "Проверка подключения Active Directory",
  "auth.ad_login": "Вход через Active Directory",
  "auth.ad_login.created": "Создан пользователь из Active Directory",
  "equipment.created": "Создана карточка оборудования",
  "equipment.updated": "Обновлена карточка оборудования",
  "equipment.deleted": "Удалена карточка оборудования",
  "movement.created": "Создано перемещение",
  "movement.updated": "Обновлено перемещение",
  "writeoff.created": "Создано списание",
  "writeoff.updated": "Обновлено списание",
  "inventory_session.created": "Создана сессия инвентаризации",
  "inventory_session.updated": "Обновлена сессия инвентаризации",
  "inventory_check.saved": "Сохранена проверка инвентаризации",
  "request.created": "Создана заявка",
  "request.updated": "Обновлен ответ по заявке",
  "user.updated": "Обновлена учетная запись",
  "user.deleted": "Удалена учетная запись",
};

const auditEntityLabels = {
  app_setting: "Настройки приложения",
  user: "Пользователь",
  equipment: "Оборудование",
  movement: "Перемещение",
  writeoff: "Списание",
  inventory_session: "Инвентаризация",
  inventory_check: "Проверка инвентаризации",
  service_request: "Заявка",
};

/**
 * Преобразует технический код действия аудита в понятный текст.
 */
function auditActionText(action) {
  return auditActionLabels[action] || String(action || "Событие").replaceAll("_", " ");
}

/**
 * Преобразует технический код сущности аудита в понятный текст.
 */
function auditEntityText(entity) {
  return auditEntityLabels[entity] || String(entity || "Система").replaceAll("_", " ");
}

/**
 * Извлекает время события из ISO-строки даты.
 */
function eventTime(value) {
  return value ? String(value).slice(11, 16) : "";
}

/**
 * Отображает журнал аудита операций пользователей.
 */
function AuditView({ rows, reload }) {
  const auditRows = asArray(rows);
  return (
    <section className="view active">
      <section className="panel">
        <div className="panel-head row-head">
          <div>
            <h2>Журнал аудита операций</h2>
            <p>{auditRows.length} последних событий системы</p>
          </div>
          <button className="secondary-button audit-refresh-button" type="button" onClick={reload}>
            <RefreshCw size={16} strokeWidth={2.2} aria-hidden="true" />
            Обновить
          </button>
        </div>
        <div className="audit-list">
          {auditRows.length ? auditRows.map((row) => (
            <article className="audit-item" key={row.id}>
              <div className="audit-date">
                <strong>{shortDate(row.created_at)}</strong>
                <span>{eventTime(row.created_at)}</span>
              </div>
              <div className="audit-event">
                <strong>{auditActionText(row.action)}</strong>
                <span>{row.username || "система"} · {auditEntityText(row.entity)}{row.entity_id ? ` #${row.entity_id}` : ""}</span>
              </div>
              <span className="badge">{auditEntityText(row.entity)}</span>
            </article>
          )) : <Empty text="Событий пока нет" />}
        </div>
      </section>
    </section>
  );
}

/**
 * Модальное окно создания и редактирования карточки оборудования.
 */
function EquipmentDialog({ dictionaries, form, setForm, editing, error, busy, onSave, onClose, onDelete, canDelete }) {
  const dict = normalizeDictionaries(dictionaries);
  const data = { ...emptyEquipment, ...asObject(form) };
  const qrPayload = asObject(data.qr_payload);
  return (
    <dialog open>
      <form className="dialog-card" onSubmit={onSave}>
        <div className="dialog-head">
          <div><h2>{editing ? "Карточка оборудования" : "Новое оборудование"}</h2><p>Инвентарный номер и наименование обязательны.</p></div>
          <button className="text-button" type="button" onClick={onClose}>Закрыть</button>
        </div>
        <div className="equipment-dialog-layout">
          <aside className="qr-panel">
            <div className="panel-head"><h2>QR-код</h2></div>
            {data.qr_svg ? <div className="qr-preview" dangerouslySetInnerHTML={{ __html: data.qr_svg }} /> : <Empty text="QR появится после сохранения карточки" />}
            <dl className="mini-details">
              <div><dt>Инв. номер</dt><dd>{qrPayload.inventory_number || data.inventory_number || "Не указан"}</dd></div>
              <div><dt>Сотрудник</dt><dd>{qrPayload.employee || data.employee_name || "Не закреплено"}</dd></div>
              <div><dt>Место</dt><dd>{qrPayload.location || data.location_name || "Не указано"}</dd></div>
            </dl>
          </aside>
          <div className="equipment-form">
            <label>Инвентарный номер<input value={data.inventory_number} onChange={(event) => setForm({ ...data, inventory_number: event.target.value })} required /></label>
            <label>Наименование<input value={data.name} onChange={(event) => setForm({ ...data, name: event.target.value })} required /></label>
            <label>Категория<Select value={data.category_id || ""} onChange={(value) => setForm({ ...data, category_id: value })} items={dict.categories} placeholder="Не выбрана" /></label>
            <label>Серийный номер<input value={data.serial_number || ""} onChange={(event) => setForm({ ...data, serial_number: event.target.value })} /></label>
            <label>Место<Select value={data.location_id || ""} onChange={(value) => setForm({ ...data, location_id: value })} items={dict.locations} placeholder="Не выбрано" label={(item) => `${item.name}${item.room ? `, каб. ${item.room}` : ""}`} /></label>
            <label>Сотрудник<Select value={data.employee_id || ""} onChange={(value) => setForm({ ...data, employee_id: value })} items={dict.employees} placeholder="Не закреплено" label={(item) => item.full_name} /></label>
            <label className="equipment-date-label">Дата ввода в эксплуатацию<input value={data.purchase_date || ""} onChange={(event) => setForm({ ...data, purchase_date: event.target.value })} type="date" /></label>
            <label>Гарантия до<input value={data.warranty_until || ""} onChange={(event) => setForm({ ...data, warranty_until: event.target.value })} type="date" /></label>
            <label>Стоимость<input value={data.price || ""} onChange={(event) => setForm({ ...data, price: event.target.value })} type="number" min="0" /></label>
            <label>Статус<Select value={data.status} onChange={(value) => setForm({ ...data, status: value })} items={dict.statuses} /></label>
            <label>Состояние<Select value={data.condition} onChange={(value) => setForm({ ...data, condition: value })} items={dict.conditions} /></label>
            <label>IP<input value={data.ip_address || ""} onChange={(event) => setForm({ ...data, ip_address: event.target.value })} /></label>
            <label>MAC<input value={data.mac_address || ""} onChange={(event) => setForm({ ...data, mac_address: event.target.value })} /></label>
            <label className="wide">Характеристики<textarea value={data.specs || ""} onChange={(event) => setForm({ ...data, specs: event.target.value })} rows="3" /></label>
            <label className="wide">Примечания<textarea value={data.notes || ""} onChange={(event) => setForm({ ...data, notes: event.target.value })} rows="3" /></label>
          </div>
        </div>
        {error && <p className="auth-notice error">{error}</p>}
        <div className="dialog-actions">
          {editing && canDelete && <button className="danger-button" type="button" onClick={onDelete}>Удалить</button>}
          <button className="ghost-button" type="button" onClick={onClose}>Отмена</button>
          <button className="primary-button" disabled={busy} type="submit">Сохранить</button>
        </div>
      </form>
    </dialog>
  );
}

/**
 * Универсальный выпадающий список для справочников и статусов.
 */
function Select({ value, onChange, items, placeholder = "", label = (item) => item.name, getValue = (item) => item.id, disabled = false }) {
  return (
    <select value={value ?? ""} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
      {placeholder && <option value="">{placeholder}</option>}
      {asArray(items).map((item) => {
        const optionValue = Array.isArray(item) ? item[0] : getValue(item);
        const optionLabel = Array.isArray(item) ? item[1] : label(item);
        return <option value={optionValue} key={optionValue}>{optionLabel}</option>;
      })}
    </select>
  );
}

/**
 * Отображает выбранный аватар пользователя.
 */
function Avatar({ user, className = "" }) {
  const safeUser = asObject(user);
  const [key, symbol, _title, mode] = avatarOption(safeUser.avatar);
  const text = mode === "symbol" ? symbol : initials(safeUser.full_name || safeUser.username);
  return (
    <div className={`user-avatar avatar-${key} ${mode === "symbol" ? "avatar-symbol" : ""} ${className}`} aria-hidden="true">
      {text}
    </div>
  );
}

/**
 * Позволяет выбрать аватар из допустимого набора вариантов.
 */
function AvatarPicker({ value, onChange }) {
  const selected = avatarValue(value);
  return (
    <div className="avatar-picker">
      {avatarOptions.map(([key, label, title, mode]) => (
        <button className={`avatar-choice ${selected === key ? "active" : ""}`} type="button" key={key} onClick={() => onChange(key)} title={`Аватар: ${title}`}>
          <span className={`user-avatar avatar-${key} ${mode === "symbol" ? "avatar-symbol" : ""} small`} aria-hidden="true">{label}</span>
        </button>
      ))}
    </div>
  );
}

/**
 * Компактная карточка числового показателя.
 */
function Metric({ label, value }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong></article>;
}

/**
 * Универсальное состояние пустого списка или отсутствующих данных.
 */
function Empty({ text }) {
  return <div className="empty">{text}</div>;
}

/**
 * Компактная строка оборудования для отчетов и связанных списков.
 */
function SmallEquipment({ item, extra }) {
  return (
    <article className="list-item">
      <strong>{item.inventory_number} · {item.name}</strong>
      <span>{extra || `${item.status_label || item.status || ""} · ${item.condition_label || item.condition || ""} · ${item.location_name || "Место не указано"}`}</span>
    </article>
  );
}

/**
 * Компактная строка заявки с ее статусом и решением.
 */
function RequestItem({ item }) {
  const acceptedBy = item.decided_by_name ? ` · принял: ${item.decided_by_name}` : "";
  return (
    <article className="list-item request-list-item">
      <div>
        <strong>{item.title}</strong>
        <span>{requestStatusLabel(item)} · {item.category_name || "без категории"} · {shortDate(item.created_at)}{acceptedBy}</span>
      </div>
      {item.decision_reason && <p>{item.decision_reason}</p>}
    </article>
  );
}

/**
 * Универсальная таблица для отчетных блоков.
 */
function SimpleTable({ title, columns, rows, emptyText }) {
  const safeColumns = asArray(columns);
  const safeRows = asArray(rows);
  return (
    <section className="panel">
      <div className="panel-head"><h2>{title}</h2></div>
      <div className="table-wrap">
        <table>
          <thead><tr>{safeColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>{safeRows.length ? safeRows.map((row, index) => <tr key={index}>{asArray(row).map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>) : <tr><td colSpan={safeColumns.length || 1}><Empty text={emptyText} /></td></tr>}</tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Горизонтальная диаграмма для относительных показателей.
 */
function Bar({ item }) {
  return (
    <div className="bar-row">
      <span>{item.name}</span>
      <div className="bar-track"><div className="bar-fill" style={{ width: `${item.percent || 0}%` }} /></div>
      <strong>{item.count}</strong>
    </div>
  );
}
