"""Единая точка доступа к каталогу данных.

Корень данных задаётся переменной окружения ``WAVE2D_DATA_DIR``.
Если она не задана, используется ``<repo>/data`` (независимо от текущей
рабочей директории).

Структура (см. ``AGENTS.md`` и ``TODO.md``)::

    data/
    ├── wave2d/<run_id>/results.h5
    ├── elmfire/<run_id>/raw/*.dat
    ├── elmfire/<run_id>/converted/z1.h5
    └── derived/{plots,frames,video,coupling}/...
"""

from __future__ import annotations

import os
from pathlib import Path

# Корень репозитория: <repo>/src/common/paths.py -> parents[2] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Известные раны. Позже будут читаться из catalog.json (см. TODO.md).
WAVE2D_RUNS = ("Globus", "FT2")
ELMFIRE_RUNS = ("WagD",)


def data_root() -> Path:
    """Корень данных: ``WAVE2D_DATA_DIR`` или ``<repo>/data``."""
    env = os.environ.get("WAVE2D_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _REPO_ROOT / "data"


# --- Wave2D ---------------------------------------------------------------

def wave2d_dir(run_id: str) -> Path:
    return data_root() / "wave2d" / run_id


def wave2d_results(run_id: str, name: str = "results.h5") -> Path:
    return wave2d_dir(run_id) / name


# --- ELMFIRE --------------------------------------------------------------

def elmfire_dir(run_id: str) -> Path:
    return data_root() / "elmfire" / run_id


def elmfire_raw(run_id: str) -> Path:
    return elmfire_dir(run_id) / "raw"


def elmfire_converted(run_id: str, name: str = "z1.h5") -> Path:
    return elmfire_dir(run_id) / "converted" / name


# --- derived (всё, что генерирует код) -----------------------------------

def derived(*parts: str) -> Path:
    return data_root().joinpath("derived", *parts)


def plots_dir(run_id: str | None = None) -> Path:
    return derived("plots", run_id) if run_id else derived("plots")


def frames_dir(run_id: str) -> Path:
    return derived("frames", run_id)


def video_dir() -> Path:
    return derived("video")


def coupling_dir(*parts: str) -> Path:
    return derived("coupling", *parts)


def ensure_data_root() -> Path:
    """Создаёт базовую структуру каталогов данных, если её ещё нет."""
    root = data_root()
    for sub in (
        "wave2d",
        "elmfire",
        "derived/plots",
        "derived/frames",
        "derived/video",
        "derived/coupling",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


if __name__ == "__main__":
    root = ensure_data_root()
    print(f"data root: {root}")
