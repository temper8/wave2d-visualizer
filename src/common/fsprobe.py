"""Безопасные проверки доступности файловой системы.

Обращение к недоступной сетевой папке (SMB/UNC) блокирует ``os.path.isdir``,
``iterdir``, ``stat`` на SMB-таймаут — в GUI-потоке это выглядит как вечное
зависание ещё до отрисовки окна. Здесь проверки выполняются в daemon-потоке
с ограничением времени: если проверка не успела, путь считается недоступным.

Поток-демон по таймауту не убивается (Python этого не умеет) — заблокированный
системный вызов «дожжётся» сам и завершится, но UI его не ждёт.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterable
from pathlib import Path

#: Таймаут по умолчанию (секунды). Достаточно для живой папки, мало для SMB-зависания.
DEFAULT_TIMEOUT = 4.0


def _probe(check, path: str | Path, timeout: float) -> bool:
    """Выполняет ``check(path)`` в потоке и ждёт не дольше ``timeout``."""
    result = {"ok": False}

    def run() -> None:
        try:
            result["ok"] = bool(check(os.fspath(path)))
        except OSError:
            result["ok"] = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)
    return result["ok"] if not thread.is_alive() else False


def is_dir(path: str | Path, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Проверяет, что ``path`` — доступный каталог, не блокируясь дольше таймаута."""
    return _probe(os.path.isdir, path, timeout)


def is_file(path: str | Path, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Проверяет, что ``path`` — доступный файл, не блокируясь дольше таймаута."""
    return _probe(os.path.isfile, path, timeout)


def available_dirs(
    paths: Iterable[str | Path], timeout: float = DEFAULT_TIMEOUT
) -> list[Path]:
    """Из ``paths`` возвращает доступные каталоги, сохраняя их порядок.

    Все проверки идут параллельно с общим дедлайном, поэтому ожидание
    ограничено ``timeout``, а не ``timeout * len(paths)``.
    """
    items = [Path(p) for p in paths]
    if not items:
        return []

    ok = [False] * len(items)

    def make(index: int, path: Path):
        def run() -> None:
            try:
                ok[index] = os.path.isdir(os.fspath(path))
            except OSError:
                ok[index] = False

        return run

    threads: list[threading.Thread] = []
    for index, path in enumerate(items):
        thread = threading.Thread(target=make(index, path), daemon=True)
        thread.start()
        threads.append(thread)

    deadline = time.monotonic() + timeout
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(remaining)

    return [
        path
        for index, path in enumerate(items)
        if ok[index] and not threads[index].is_alive()
    ]
