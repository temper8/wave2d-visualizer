"""Реестр сравнения графиков (MultiView) — данные без GUI.

Окно просмотра показывает один датасет за раз; чтобы сравнить одноимённые
датасеты из **разных** расчётов, их складывают в общий набор
:class:`ComparisonSet`. Элементы группируются по **имени** датасета (лист
пути): одна группа — одна будущая вкладка MultiView. Реальная отрисовка —
отдельный этап, здесь только модель данных и группировка.

Модуль не импортирует Tk и matplotlib: его можно проверять без графического
интерфейса. GUI-окно живёт в этом же модуле ниже (добавляется отдельным шагом).

См. ``TODO/p2-multiview-compare-runs.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


@dataclass
class PlotItem:
    """Один график, добавленный в сравнение.

    ``data``/``attrs`` — **снимок** значений на момент добавления (не ссылка
    на файл): элемент самодостаточен и не зависит от жизни :class:`H5Reader`
    или доступности сетевой шары. ``view``/``comp`` фиксируют, как датасет
    был показан в исходном окне (вид ``(R,Z)/(rho,theta)`` и составляющая
    ``real/imag/abs``).
    """

    source: str
    """Человекочитаемая метка источника (прогон/задача), напр. ``FT2/<stamp>``."""

    file_path: str
    """Путь к ``results.h5``, откуда взят датасет."""

    node_path: str
    """Путь узла внутри файла, напр. ``/fields/nphi+122/Ea``."""

    data: np.ndarray | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    view: str = "rho"
    comp: str = "abs"
    color: str | None = None

    @property
    def name(self) -> str:
        """Имя датасета (лист ``node_path``) — ключ группы."""
        return self.node_path.rsplit("/", 1)[-1]

    @property
    def key(self) -> tuple[str, str]:
        """Идентичность элемента: ``(файл, узел)``.

        Два разных элемента с одинаковым именем (коллизия веток) различимы по
        ``node_path``; повторное добавление того же узла заменяет элемент.
        """
        return (self.file_path, self.node_path)

    @property
    def ndim(self) -> int:
        """Размерность данных (``0``, если данных нет) — для проверки типа."""
        return self.data.ndim if self.data is not None else 0


class AddResult(Enum):
    """Итог :meth:`ComparisonSet.add`."""

    CREATED = "created"
    """Создана новая группа (имени ещё не было)."""

    ADDED = "added"
    """Элемент добавлен в существующую группу."""

    REPLACED = "replaced"
    """Тот же узел уже был — элемент заменён на месте."""

    CONFLICT = "conflict"
    """Конфликт типов: в группе 1D, а добавляется 2D (или наоборот)."""


class ComparisonSet:
    """Набор сравниваемых графиков, сгруппированных по имени датасета.

    Группы хранятся в порядке первого появления имени; слушатели
    (:meth:`subscribe`) уведомляются при любом изменении, чтобы окно MultiView
    могло перерисоваться.
    """

    def __init__(self) -> None:
        self._groups: dict[str, list[PlotItem]] = {}
        self._listeners: list[Callable[[], None]] = []

    # --- чтение ----------------------------------------------------------

    def groups(self) -> list[str]:
        """Имена групп в порядке первого появления."""
        return list(self._groups)

    def items(self, name: str) -> list[PlotItem]:
        """Копия списка элементов группы (пустая, если группы нет)."""
        return list(self._groups.get(name, ()))

    def __len__(self) -> int:
        """Общее число элементов во всех группах."""
        return sum(len(items) for items in self._groups.values())

    def is_empty(self) -> bool:
        """``True``, если набор пуст."""
        return not self._groups

    # --- изменение -------------------------------------------------------

    def add(self, item: PlotItem) -> AddResult:
        """Добавляет элемент в группу по имени (при необходимости создаёт её).

        Повторное добавление того же узла (по :attr:`PlotItem.key`) заменяет
        элемент. Элемент другой размерности, чем уже накопленные в группе,
        не добавляется — возвращается :attr:`AddResult.CONFLICT`.
        """
        items = self._groups.get(item.name)
        if items is None:
            self._groups[item.name] = [item]
            self._notify()
            return AddResult.CREATED

        for i, existing in enumerate(items):
            if existing.key == item.key:
                items[i] = item
                self._notify()
                return AddResult.REPLACED

        if items and items[0].ndim != item.ndim:
            return AddResult.CONFLICT

        items.append(item)
        self._notify()
        return AddResult.ADDED

    def remove(self, item: PlotItem) -> bool:
        """Удаляет элемент по :attr:`PlotItem.key`; пустую группу убирает.

        Возвращает ``True``, если элемент был найден и удалён.
        """
        items = self._groups.get(item.name)
        if not items:
            return False
        for i, existing in enumerate(items):
            if existing.key == item.key:
                del items[i]
                if not items:
                    del self._groups[item.name]
                self._notify()
                return True
        return False

    def clear(self) -> None:
        """Убирает все группы и элементы."""
        if not self._groups:
            return
        self._groups.clear()
        self._notify()

    # --- слушатели -------------------------------------------------------

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Регистрирует колбэк, вызываемый при изменении набора."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        """Снимает колбэк (отсутствующий игнорируется)."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()


_default_comparison: ComparisonSet | None = None


def default_comparison() -> ComparisonSet:
    """Единый набор сравнения на приложение (создаётся при первом обращении)."""
    global _default_comparison
    if _default_comparison is None:
        _default_comparison = ComparisonSet()
    return _default_comparison
