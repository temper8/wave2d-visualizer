"""Пользовательские настройки GUI (кросс-платформенный JSON).

Файл конфигурации лежит в стандартном пользовательском каталоге:
Windows — ``%APPDATA%\\wave2d-visualizer\\settings.json``,
остальные — ``$XDG_CONFIG_HOME/wave2d-visualizer/settings.json`` или
``~/.config/wave2d-visualizer/settings.json``. В репозиторий и ``data/``
ничего не пишется.

Пока единственная настройка — последняя открытая папка данных
(``last_data_root``), которую использует
:class:`~src.wave2d.app.W2DNavigatorApp`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_APP_NAME = "wave2d-visualizer"
_SETTINGS_NAME = "settings.json"

LAST_DATA_ROOT = "last_data_root"


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


def get_last_data_root() -> Path | None:
    """Последняя открытая папка данных или ``None``, если её нет."""
    value = load_settings().get(LAST_DATA_ROOT)
    if isinstance(value, str) and value:
        return Path(value).expanduser()
    return None


def set_last_data_root(path: str | Path) -> None:
    """Запоминает папку данных как последнюю открытую."""
    data = load_settings()
    data[LAST_DATA_ROOT] = str(Path(path).expanduser().resolve())
    save_settings(data)
