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

from collections.abc import Sequence

import numpy as np
from matplotlib.axes import Axes
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure
from mpl_toolkits.axes_grid1 import make_axes_locatable


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
    # Цветовая шкала — на собственной оси справа от картинки. Через
    # ``fig.colorbar(ax=...)`` нельзя: он выставляет ``anchor=(1, 0.5)`` и при
    # ``aspect="equal"`` прижимает узкую картинку к правому краю. ``append_axes``
    # держит шкалу вплотную к осям, где бы те ни оказались (size/pad — в дюймах).
    cax = make_axes_locatable(ax).append_axes("right", size=0.22, pad=0.08)
    return fig.colorbar(mesh, cax=cax)


Curve = tuple[np.ndarray | None, np.ndarray, str, str | None]
"""1D-ряд для :func:`draw_curves`: ``(x, y, label, color)``.

``x`` — ось (``None`` или несовпадающая длина → индекс), ``label`` —
подпись в легенде, ``color`` — цвет (``None`` — цвет из цикла matplotlib).
"""


def draw_curves(
    ax: Axes,
    series: Sequence[Curve],
    *,
    title: str = "",
    xlabel: str = "index",
    ylabel: str = "",
) -> None:
    """Рисует несколько 1D-рядов на одной оси с общей легендой.

    Общий слой наложения: используется :class:`DatasetView` (несколько
    выбранных 1D-датасетов) и MultiView (одноимённые ряды из разных
    прогонов). Ось ``x`` применяется, только если она задана и совпадает по
    длине **у всех** рядов; иначе ряды строятся против индекса, а ``xlabel``
    заменяется на ``"index"``. Легенда показывается при двух рядах и более.
    Пропорции сбрасываются в ``auto``: предыдущий 2D-вид мог оставить
    ``aspect="equal"``, а ``Axes.clear()`` его не сбрасывает.
    """
    ax.set_aspect("auto")
    use_x = bool(series) and all(
        x is not None and len(x) == len(y) for x, y, _label, _color in series
    )
    for x, y, label, color in series:
        kwargs = {"color": color} if color is not None else {}
        if use_x:
            ax.plot(x, y, label=label, **kwargs)
        else:
            ax.plot(y, label=label, **kwargs)
    if not use_x:
        xlabel = "index"
    if title:
        ax.set_title(title, fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if len(series) > 1:
        ax.legend(fontsize=7)


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
    draw_curves(ax, [(x, y, "", None)], title=title, xlabel=xlabel, ylabel=ylabel)


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
    """Рисует комплексный 1D-датасет одной составляющей.

    Выводится ``component(data, comp)`` (по умолчанию ``abs``). Наложение
    ``real``/``imag``/``abs`` несколькими линиями — через :func:`draw_curves`.
    """
    draw_curves(
        ax,
        [(x, component(data, comp), "", None)],
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )
