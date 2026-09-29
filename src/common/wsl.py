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

# Корни UNC для доступа к WSL; берём первый существующий.
_UNC_ROOTS = (r"\\wsl.localhost", r"\\wsl$")


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
    """Пары ``(подпись, UNC-путь)`` для меню; пусто, если WSL недоступен."""
    distros = wsl_distros()
    root = _unc_root()
    if not distros or root is None:
        return []
    return [(f"WSL: {d}", f"{root}\\{d}") for d in distros]


def _unc_root() -> str | None:
    """Первый доступный UNC-корень WSL."""
    for root in _UNC_ROOTS:
        if os.path.isdir(root):
            return root
    # Ни один не отвечает (WSL остановлен) — берём вариант по умолчанию.
    return _UNC_ROOTS[0]
