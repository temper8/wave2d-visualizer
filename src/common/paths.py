"""Единая точка доступа к каталогу данных.

Корень данных задаётся переменной окружения ``WAVE2D_DATA_DIR``
(по умолчанию ``<repo>/data``). Разрешение корня и навигация по Wave2D живут
в :mod:`src.common.navigator`; здесь они реэкспортируются для совместимости,
а также лежат функции ELMFIRE и ``derived``.

Раскладка::

    data/
    ├── wave2d/<case_id>/<stamp>/results.h5            # run-level данные (<= 0.95)
    ├── wave2d/<case_id>/<stamp>/report.h5             # run-level отчёт (>= 0.96)
    ├── wave2d/<case_id>/<stamp>/tasks/<task>/results.h5
    ├── wave2d/<case_id>/results.h5                    # legacy-плоско
    ├── elmfire/<run_id>/raw/*.dat
    ├── elmfire/<run_id>/converted/z1.h5
    └── derived/{runs,plots,frames,video,coupling}/...

``derived/runs/<case_id>/<stamp>/`` — папка производных артефактов прогона
(напр. ``nphi_merged.h5``) — см. :func:`run_derived` / :func:`merged_results`.

Wave2D-навигацию выполняет :class:`~src.common.navigator.Navigator`.
ELMFIRE и ``derived`` пока живут модульными функциями — см. ``TODO/``.
"""

from __future__ import annotations

from pathlib import Path

# Реэкспорт Wave2D-навигации: раньше всё это было в текущем модуле.
from src.common.navigator import (  # noqa: F401
    DataNavigator,
    DerivedNavigator,
    ElmfireNavigator,
    Navigator,
    Wave2DNavigator,
    data_root,
    default_navigator,
    split_run_id,
    wave2d_cases,
    wave2d_dir,
    wave2d_latest,
    wave2d_primary_results,
    wave2d_results,
    wave2d_run_artifacts,
    wave2d_run_report,
    wave2d_runs,
    wave2d_task_results,
    wave2d_tasks,
    wave2d_viewable,
)

__all__ = [
    "Navigator",
    "Wave2DNavigator",
    "ElmfireNavigator",
    "DerivedNavigator",
    "DataNavigator",
    "data_root",
    "default_navigator",
    "split_run_id",
    "wave2d_cases",
    "wave2d_dir",
    "wave2d_latest",
    "wave2d_primary_results",
    "wave2d_results",
    "wave2d_run_artifacts",
    "wave2d_run_report",
    "wave2d_runs",
    "wave2d_task_results",
    "wave2d_tasks",
    "wave2d_viewable",
    "ELMFIRE_RUNS",
    "elmfire_dir",
    "elmfire_raw",
    "elmfire_converted",
    "derived",
    "run_derived",
    "merged_results",
    "plots_dir",
    "frames_dir",
    "video_dir",
    "coupling_dir",
    "ensure_data_root",
]

ELMFIRE_RUNS = ("WagD",)


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


def run_derived(run_id: str, *parts: str) -> Path:
    """Папка производных артефактов прогона: ``derived/runs/<case>/<stamp>``.

    Сюда пишутся любые результаты, посчитанные viewer'ом по конкретному
    прогону (слияние по ``nphi``, картинки, интегралы и т.п.).
    """
    return derived("runs", *run_id.split("/"), *parts)


def merged_results(run_id: str, name: str = "nphi_merged.h5") -> Path:
    """Объединённый по ``nphi`` файл прогона (собирает viewer)."""
    return run_derived(run_id, name)


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
        "derived/runs",
        "derived/frames",
        "derived/video",
        "derived/coupling",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


if __name__ == "__main__":
    root = ensure_data_root()
    print(f"data root: {root}")
