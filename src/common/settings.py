"""Пользовательские настройки GUI (кросс-платформенный JSON).

Файл конфигурации лежит в стандартном пользовательском каталоге:
Windows — ``%APPDATA%\\wave2d-visualizer\\settings.json``,
остальные — ``$XDG_CONFIG_HOME/wave2d-visualizer/settings.json`` или
``~/.config/wave2d-visualizer/settings.json``. В репозиторий и ``data/``
ничего не пишется.

Хранит последнюю открытую папку **каждого навигатора** (``wave2d``,
``elmfire``, ``derived``) — у каждого слоя данных своя папка — и историю
открытых папок (``navigator_history``; сейчас пишется только для ``wave2d``).
Общий корень (``WAVE2D_DATA_DIR``) используется только как значение по
умолчанию, пока настройка не задана (условный «первый запуск»).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_APP_NAME = "wave2d-visualizer"
_SETTINGS_NAME = "settings.json"

_NAVIGATOR_ROOTS = "navigator_roots"
_NAVIGATOR_HISTORY = "navigator_history"

HISTORY_LIMIT = 10


def config_dir() -> Path:
    """Каталог конфигов приложения в пользовательской области."""
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"
    return root / _APP_NAME


def settings_path() -> Path:
    """Путь к файлу настроек."""
    return config_dir() / _SETTINGS_NAME


def load_settings() -> dict:
    """Читает настройки; при отсутствии/повреждении файла — пустой словарь."""
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(values: dict) -> None:
    """Сохраняет настройки, создавая каталог при необходимости."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_navigator_root(name: str) -> Path | None:
    """Последняя открытая папка навигатора ``name`` или ``None``."""
    roots = load_settings().get(_NAVIGATOR_ROOTS)
    if not isinstance(roots, dict):
        return None
    value = roots.get(name)
    if isinstance(value, str) and value:
        return Path(value).expanduser()
    return None


def set_navigator_root(name: str, path: str | Path) -> None:
    """Запоминает папку навигатора ``name``."""
    data = load_settings()
    roots = data.get(_NAVIGATOR_ROOTS)
    if not isinstance(roots, dict):
        roots = {}
    roots[name] = str(Path(path).expanduser().resolve())
    data[_NAVIGATOR_ROOTS] = roots
    save_settings(data)


def get_navigator_history(name: str) -> list[Path]:
    """История папок навигатора ``name`` (от новых к старым)."""
    history = load_settings().get(_NAVIGATOR_HISTORY)
    if not isinstance(history, dict):
        return []
    values = history.get(name)
    if not isinstance(values, list):
        return []
    return [Path(v).expanduser() for v in values if isinstance(v, str) and v]


def push_navigator_history(
    name: str, path: str | Path, limit: int = HISTORY_LIMIT
) -> list[Path]:
    """Добавляет папку в историю навигатора (свежие сверху, без дублей)."""
    new = Path(path).expanduser().resolve()
    history = [p for p in get_navigator_history(name) if p != new]
    history.insert(0, new)
    del history[limit:]
    data = load_settings()
    store = data.get(_NAVIGATOR_HISTORY)
    if not isinstance(store, dict):
        store = {}
    store[name] = [str(p) for p in history]
    data[_NAVIGATOR_HISTORY] = store
    save_settings(data)
    return history
