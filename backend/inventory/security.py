"""Валидация пользовательских фильтров для безопасной работы ORM-запросов."""

MAX_SEARCH_QUERY_LENGTH = 120


def normalize_search_query(value):
    """Очищает поисковую строку и ограничивает ее длину для безопасной фильтрации."""
    query = str(value or "").strip()
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise ValueError("Слишком длинная строка поиска")
    return query


def parse_positive_int_filter(value, field_name):
    """Проверяет числовой фильтр и защищает ORM-запрос от некорректного ввода."""
    if value in ("", None):
        return None
    try:
        parsed = int(str(value), 10)
    except (TypeError, ValueError):
        raise ValueError(f"Некорректное значение фильтра {field_name}")
    if parsed < 1:
        raise ValueError(f"Некорректное значение фильтра {field_name}")
    return parsed


def parse_choice_filter(value, allowed_values, field_name):
    """Проверяет фильтр по перечислению и пропускает только разрешенные значения."""
    if value in ("", None):
        return None
    parsed = str(value)
    if parsed not in set(allowed_values):
        raise ValueError(f"Некорректное значение фильтра {field_name}")
    return parsed
