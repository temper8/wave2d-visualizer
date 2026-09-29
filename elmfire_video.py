"""Точка входа: сборка MP4 из кадров флуктуаций ELMFIRE.

Логика — в :func:`~src.elmfire.video.make_fluctuations_video`.

Запуск::

    uv run elmfire_video.py [<run_id>]   # по умолчанию WagD
"""

import sys

from src.elmfire.video import make_fluctuations_video

DEFAULT_RUN = "WagD"


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    run_id = argv[0] if argv else DEFAULT_RUN
    make_fluctuations_video(run_id)


if __name__ == "__main__":
    main()
