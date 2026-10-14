"""Отрисовка датасетов Wave2D в matplotlib (без Tk).

Функции вынесены из :class:`~src.wave2d.datasetview.DatasetView`, чтобы
рендеринг можно было проверять без графического интерфейса и переиспользовать
(например, в ``w2d_render.py``). Модуль не выбирает backend и не импортирует
Tk — работает с готовыми ``Axes``/``Figure``, а colorbar возвращает
вызывающему (чтобы тот мог его снять перед следующей отрисовкой).

Составляющая комплексных данных (``real``/``imag``/``abs``) — здесь же, в
:func:`component`.
"""

from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure


def component(data: np.ndarray, mode: str) -> np.ndarray:
    """Для комплексных данных — выбранная составляющая.

    ``mode`` — ``"real"``/``"imag"``/``"abs"``; неизвестное значение даёт
    ``abs``. Вещественные данные возвращаются как есть.
    """
    if np.iscomplexobj(data):
        if mode == "real":
            return data.real
        if mode == "imag":
            return data.imag
        return np.abs(data)
    return data


def draw_2d(
    ax: Axes,
    fig: Figure,
    data: np.ndarray,
    *,
    title: str,
    view: str = "rho",
    R: np.ndarray | None = None,
    Z: np.ndarray | None = None,
    comp: str = "abs",
) -> Colorbar:
    """Рисует 2D-датасет и возвращает созданный colorbar.

    Вид ``(R,Z)`` используется, только если он запрошен (``view == "rz"``) и
    координаты ``R``/``Z`` совпадают по форме с данными; иначе — ``(rho,theta)``.
    """
    arr = component(data, comp)
    use_rz = view == "rz" and R is not None and R.shape == data.shape
    if use_rz:
        mesh = ax.pcolormesh(R, Z, arr, shading="gouraud")
        ax.set_aspect("equal")
        ax.set_title(f"{title} (R,Z)", fontsize=8)
    else:
        mesh = ax.imshow(arr, origin="lower", aspect="equal", interpolation="none")
        ax.set_title(f"{title} (rho,theta)", fontsize=8)
    return fig.colorbar(mesh, ax=ax, pad=0.02)


def _draw_line(
    ax: Axes,
    y: np.ndarray,
    *,
    title: str,
    x: np.ndarray | None,
    xlabel: str,
    ylabel: str,
) -> None:
    """Общая отрисовка 1D-линии: ось ``x`` (или индекс) и подписи.

    ``x`` используется, только если его длина совпадает с ``len(y)``; иначе
    линия строится против индекса, а ``xlabel`` заменяется на ``"index"``.
    """
    if x is not None and len(x) == len(y):
        ax.plot(x, y)
    else:
        ax.plot(y)
        xlabel = "index"
    ax.set_title(title, fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)


def draw_1d(
    ax: Axes,
    data: np.ndarray,
    *,
    title: str,
    x: np.ndarray | None = None,
    xlabel: str = "index",
    ylabel: str = "",
) -> None:
    """Рисует вещественный 1D-датасет одной линией.

    ``x`` — выбранная ось (``rho``/``psi``); если её длина не совпадает с
    ``len(data)``, линия строится против индекса. ``xlabel`` (ось) и
    ``ylabel`` (имя датасета + ``units``) — готовые подписи от вызывающего.
    """
    y = np.real(data) if np.iscomplexobj(data) else data
    _draw_line(ax, y, title=title, x=x, xlabel=xlabel, ylabel=ylabel)


def draw_1d_complex(
    ax: Axes,
    data: np.ndarray,
    *,
    title: str,
    x: np.ndarray | None = None,
    xlabel: str = "index",
    ylabel: str = "",
    comp: str = "abs",
) -> None:
    """Рисует комплексный 1D-датасет — **заглушка**: одна составляющая.

    Пока выводится только ``component(data, comp)`` (по умолчанию ``abs``).
    Полноценный режим (``real``/``imag``/``abs`` линиями + легенда) —
    отдельный шаг задачи
    ``TODO/p3-extend-1d-dataset-view-with-axes-and-multiple-curves.md``.
    """
    _draw_line(
        ax,
        component(data, comp),
        title=title,
        x=x,
        xlabel=xlabel,
        ylabel=ylabel,
    )
