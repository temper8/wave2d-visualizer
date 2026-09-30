"""Обнаружение WSL-дистрибутивов для доступа к их ФС из Windows.

Файловые системы WSL доступны по UNC-пути ``\\\\wsl.localhost\\<distro>``
(новые сборки Windows) или ``\\\\wsl$\\<distro>`` (старые). Нативный диалог
выбора папки эти пути в дереве не показывает, поэтому
:class:`~src.wave2d.app.W2DNavigatorApp` добавляет по пункту на дистрибутив.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from src.common import fsprobe

# Корни UNC для доступа к WSL; берём первый существующий.
_UNC_ROOTS = (r"\\wsl.localhost", r"\\wsl$")

# Таймаут проверки UNC-корня: WSL отвечает быстро, а выключенный — не виснет.
_UNC_TIMEOUT = 2.0


def wsl_distros() -> list[str]:
    """Список установленных WSL-дистрибутивов (пусто, если WSL недоступен)."""
    if os.name != "nt":
        return []
    exe = shutil.which("wsl")
    if exe is None:
        return []
    try:
        proc = subprocess.run(
            [exe, "-l", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "WSL_UTF8": "1"},
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def wsl_roots() -> list[tuple[str, str]]:
    """Пары ``(имя дистрибутива, UNC-путь)``; пусто, если WSL недоступен."""
    distros = wsl_distros()
    root = _unc_root()
    if not distros or root is None:
        return []
    return [(d, f"{root}\\{d}") for d in distros]


def _unc_root() -> str | None:
    """Первый доступный UNC-корень WSL.

    Проверка идёт через :mod:`src.common.fsprobe` с таймаутом: если WSL
    остановлен, ``\\wsl$`` иначе подвис бы на SMB-таймаут в GUI-потоке.
    """
    for root in fsprobe.available_dirs(_UNC_ROOTS, timeout=_UNC_TIMEOUT):
        return str(root)
    # Ни один не отвечает (WSL остановлен) — берём вариант по умолчанию.
    return _UNC_ROOTS[0]
