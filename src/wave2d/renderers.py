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


def draw_1d(ax: Axes, data: np.ndarray, *, title: str) -> None:
    """Рисует 1D-датасет одной линией (против индекса).

    Расширение (оси, подписи, несколько кривых) — отдельная задача F1.
    """
    ax.plot(data)
    ax.set_title(title, fontsize=8)
