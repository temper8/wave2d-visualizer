"""Генератор иконки для ``w2d_app.py``.

Рисует три варианта (a/b/c) и сохраняет их в PNG. По умолчанию кладёт
превью в ``data/derived/icons/`` (вне git) — для выбора глазами. Выбранный
вариант затем рендерится прямо в ассет::

    uv run tools/make_icon.py                        # все три варианта (превью)
    uv run tools/make_icon.py --variant b --out src/wave2d/assets
    uv run tools/make_icon.py --variant a --out src/wave2d/assets --ico   # + .ico

Используется ``Agg`` — окно не создаётся, иконка рисуется молча.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tools/ запускается как скрипт (sys.path[0] = tools/): кладём корень
# репозитория на sys.path, чтобы импортировался пакет ``src``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from PIL import Image

from src.common.paths import derived

SIZE = 256  # сторона мастер-PNG в пикселях
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)  # размеры кадров внутри .ico

# Цвета вариантов
_BG = "#0d1b2a"
_TEAL = "#2a9d8f"
_GOLD = "#e9c46a"
_GRID = "#5c6f82"


def _figure():
    """Квадратная фигура ровно SIZE×SIZE без полей и осей."""
    fig = plt.figure(figsize=(SIZE / 100, SIZE / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _disc_clip(ax) -> Circle:
    """Круг-обрезка: всё outside r=1 прячется."""
    return Circle((0, 0), 1.0, transform=ax.transData)


def draw_a(ax) -> None:
    """Вариант A: полярная карта моды (заливка colormap внутри диска)."""
    n = 400
    x = np.linspace(-1, 1, n)
    xx, yy = np.meshgrid(x, x)
    rho = np.hypot(xx, yy)
    theta = np.arctan2(yy, xx)
    field = np.sin(3 * theta + 5.0 * (1.0 - rho)) * rho**1.3
    field = np.ma.masked_where(rho > 1.0, field)

    image = ax.imshow(field, extent=(-1, 1, -1, 1), origin="lower", cmap="RdBu_r")
    image.set_clip_path(_disc_clip(ax))
    ax.add_patch(Circle((0, 0), 1.0, fill=False, ec="white", lw=3, alpha=0.9))


def draw_b(ax) -> None:
    """Вариант B: тёмный диск, изолинии и золотая волна по θ."""
    ax.add_patch(Circle((0, 0), 1.0, fc=_BG, ec=_TEAL, lw=3))
    for rr in (0.25, 0.5, 0.75):
        ax.add_patch(
            Circle((0, 0), rr, fill=False, ec=_TEAL, lw=1.2, alpha=0.55)
        )
    theta = np.linspace(0, 2 * np.pi, 600)
    wave = 0.62 + 0.2 * np.sin(5 * theta)
    ax.plot(
        wave * np.cos(theta),
        wave * np.sin(theta),
        color=_GOLD,
        lw=3.5,
        solid_capstyle="round",
    )
    ax.plot([0], [0], marker="o", ms=6, color=_GOLD)


def draw_c(ax) -> None:
    """Вариант C: полярная сетка (ρ, θ) — лучи и окружности."""
    ax.add_patch(Circle((0, 0), 1.0, fc="#101820", ec="#8899aa", lw=2.5))
    for k in range(12):
        angle = k * np.pi / 6
        ax.plot(
            [0, np.cos(angle)],
            [0, np.sin(angle)],
            color=_GRID,
            lw=0.8,
            alpha=0.7,
        )
    for rr in (0.25, 0.5, 0.75, 1.0):
        ax.add_patch(
            Circle((0, 0), rr, fill=False, ec=_GRID, lw=1.0, alpha=0.85)
        )


VARIANTS = {"a": draw_a, "b": draw_b, "c": draw_c}


def render(variant: str, path: Path) -> None:
    """Рисует один вариант и сохраняет в PNG с прозрачным фоном."""
    fig, ax = _figure()
    VARIANTS[variant](ax)
    fig.savefig(path, transparent=True)
    plt.close(fig)


def _write_ico(master_png: Path, ico_path: Path) -> None:
    """Собирает многоразмерный ICO из мастер-PNG (Windows выберет нужный кадр)."""
    with Image.open(master_png) as image:
        image.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Генератор иконки w2d_app")
    parser.add_argument(
        "--variant",
        choices=[*VARIANTS, "all"],
        default="all",
        help="какой вариант рисовать (по умолчанию все три)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=derived("icons"),
        help="каталог для PNG (по умолчанию data/derived/icons)",
    )
    parser.add_argument(
        "--ico",
        action="store_true",
        help="вдобавок собрать многоразмерный .ico рядом с каждым PNG",
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    if args.variant == "all":
        targets = [(v, args.out / f"w2d_app_icon_{v}.png") for v in VARIANTS]
    else:
        # Одиночный вариант — это уже финальный ассет с каноническим именем.
        targets = [(args.variant, args.out / "w2d_app_icon.png")]

    for variant, path in targets:
        render(variant, path)
        print(f"{variant}: {path}")
        if args.ico:
            ico_path = path.with_suffix(".ico")
            _write_ico(path, ico_path)
            print(f"{variant}: {ico_path}")


if __name__ == "__main__":
    main()
