"""Точка входа: конвертация сырых ``.dat`` ELMFIRE в ``z1.h5``.

Логика — в :func:`~src.elmfire.convert.convert_raw_to_h5`.

Запуск::

    uv run elmfire_convert.py [<run_id>]   # по умолчанию WagD
"""

import sys

from src.elmfire.convert import convert_raw_to_h5

DEFAULT_RUN = "WagD"


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    run_id = argv[0] if argv else DEFAULT_RUN
    convert_raw_to_h5(run_id)


if __name__ == "__main__":
    main()
