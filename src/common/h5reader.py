"""Чтение HDF5: одно соединение на много чтений.

Пример::

    from src.common.h5reader import H5Reader

    with H5Reader("results.h5") as r:
        params = r.params()                        # /run_params
        X = r.array("/coord/X")                     # np.ndarray (копия)
        dset = r.dataset("/nphi+122/field_2D/Ea")   # h5py.Dataset (лениво)

Класс общий (не завязан на Wave2D/ELMFIRE): доменные обёртки вроде
``Wave2DResults`` можно надстроить позже — см. ``TODO.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import h5py
import numpy as np


class H5Reader:
    """Читатель HDF5-файла.

    Одно соединение переиспользуется для всех чтений. При использовании как
    контекст-менеджера файл закрывается автоматически; без ``with`` соединение
    открывается лениво при первом доступе и закрывается методом :meth:`close`.
    При ошибках бросает исключения (``FileNotFoundError``, ``KeyError``), а не
    завершает процесс.
    """

    def __init__(
        self,
        path: str | Path,
        mode: str = "r",
        verbose: bool = False,
    ) -> None:
        self.path = Path(path)
        self.mode = mode
        self.verbose = verbose
        self._file: h5py.File | None = None

    # --- соединение ------------------------------------------------------

    def open(self) -> "H5Reader":
        """Открывает файл (если ещё не открыт) и возвращает ``self``."""
        if self._file is None:
            self._file = h5py.File(self.path, self.mode)
            if self.verbose:
                print(f"Открыт файл: {self.path}")
        return self

    def close(self) -> None:
        """Закрывает соединение, если оно открыто."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "H5Reader":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def file(self) -> h5py.File:
        """Открытый ``h5py.File`` (ленивое открытие)."""
        if self._file is None:
            self.open()
        assert self._file is not None
        return self._file

    # --- структура -------------------------------------------------------

    def contains(self, name: str) -> bool:
        """Есть ли объект с таким путём в файле."""
        return name in self.file

    def keys(self, path: str = "/") -> list[str]:
        """Имена дочерних объектов группы."""
        return list(self.file[path].keys())

    # --- массивы ---------------------------------------------------------

    def dataset(self, name: str) -> h5py.Dataset:
        """``h5py.Dataset`` без копирования в память (ленивое чтение)."""
        if name not in self.file:
            raise KeyError(f"Набор данных '{name}' не найден в {self.path}")
        return self.file[name]

    def array(self, name: str) -> np.ndarray:
        """Датасет как ``np.ndarray`` (копия в память)."""
        return np.array(self.dataset(name))

    def shape(self, name: str) -> tuple[int, ...]:
        """Форма датасета без чтения данных."""
        return self.dataset(name).shape

    def dtype(self, name: str) -> np.dtype:
        """Тип данных датасета без чтения данных."""
        return self.dataset(name).dtype

    # --- параметры / атрибуты -------------------------------------------

    def attrs(self, name: str) -> dict[str, Any]:
        """Атрибуты объекта (группы или датасета)."""
        if name not in self.file:
            raise KeyError(f"Объект '{name}' не найден в {self.path}")
        return dict(self.file[name].attrs.items())

    def attrs_recursive(self, start_path: str = "/") -> dict[str, dict[str, Any]]:
        """Рекурсивно собирает атрибуты, начиная с ``start_path``.

        Ключи — имена объектов внутри ``start_path`` (как отдаёт
        ``h5py.visititems``), а сам стартовый объект — под ``start_path``.
        """
        start_path = start_path.rstrip("/") or "/"
        if start_path not in self.file:
            raise KeyError(f"Путь '{start_path}' не найден в {self.path}")

        result: dict[str, dict[str, Any]] = {}
        start_obj = self.file[start_path]
        if start_obj.attrs:
            result[start_path] = dict(start_obj.attrs.items())
        if isinstance(start_obj, h5py.Group):
            def visitor(name: str, obj: h5py.HLObject) -> None:
                if obj.attrs:
                    result[name] = dict(obj.attrs.items())

            start_obj.visititems(visitor)
        return result

    def params(self, start_path: str = "/run_params") -> dict[str, dict[str, Any]]:
        """Атрибуты ``/run_params`` (рекурсивно)."""
        return self.attrs_recursive(start_path)

    def run_info(self) -> dict[str, dict[str, Any]]:
        """Атрибуты ``/run_info`` (рекурсивно)."""
        return self.attrs_recursive("/run_info")

    # --- служебное -------------------------------------------------------

    def __repr__(self) -> str:
        state = "open" if self._file is not None else "closed"
        return f"H5Reader({str(self.path)!r}, {state})"
