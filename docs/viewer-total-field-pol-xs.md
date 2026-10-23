# Viewer-контракт: 2D полоидальное сечение поля, просуммированное по спектру `nphi`

Этот документ — **самодостаточный контракт для внешнего репозитория viewer**.
Он описывает, как построить 2D полоидальное сечение поля Wave2D,
просуммированное по тороидальному спектру `nphi`, **только по данным HDF5**
(`tasks/<task>/results.h5`). Код ниже не импортирует ничего из репозитория
Wave2D и не читает легаси-файлы `fld<nphi>.dat`, `Espctor.dat`, `psigrid.dat`.

Это Python-реализация легаси-процедуры `PrintTotalFieldPolXS`
(`Source/WaveToP/w2output.f90:837–926`, опция 7 `wave2D.exe`). Фон, точный
разбор алгоритма, сверка FFT и питфоллы — в
`docs/print-total-field-pol-xs.md` (репозиторий Wave2D). Общий контракт данных —
`docs/hdf5_schema.md`, раздел «Контракт для внешнего потребителя (viewer)».

## 1. Идея

Решатель считает отклик поля для **одной** моды `nphi` на задачу. Каждая задача
пишет в `tasks/<task>/results.h5` группу `/fields/<nphi>` с уже
синтезированным по полоидальному углу полем (`FOUR1(...,+1)` внутри
`compute_total_field`). Полное поле при тороидальном угле `phi` — линейная
комбинация мод с весами `An(nphi)` и тороидальной фазой:

```
E_total(ir, itheta) = Σ_nphi  An(nphi) · exp(i·nphi·phi) · E_nphi(ir, itheta)

|E_total|           = sqrt( |E_x|² + |E_y|² + |E_z|² )   (модуль ПОСЛЕ сумм)
```

где `phi` — в радианах, `E_nphi` — комплексные `/fields/<nphi>/{Ex,Ey,Ez}`.
Координаты `/grid/X`,`/grid/Y` в сумме **не участвуют** — они лишь кладутся в
выходные `.dat` (для сетки/отрисовки); если результат остаётся в массивах,
читать их не нужно.

> Важно: `|E_total| ≠ Σ |An·E_nphi|`. Сначала комплексная сумма по модам,
> модуль — в конце. `/fields/<nphi>/Ea` — это `|E_nphi|` для **одной** моды и
> годится только для валидации (см. §5).

## 2. Что читается из HDF5

| Величина | Узел | Тип/размер | Примечание |
|---|---|---|---|
| веса мод `An(n)` | `/spectrum/An` + `/spectrum/n` | `complex128 (M)`, `int (M)` | run-level, одинакова во всех задачах серии |
| атрибуты спектра | `/spectrum.attrs` | `nphi_min/max, nphistep, Nsmax, dphi_rad, ant_type, grill_type` | `ant_type ∈ {1=Grill, 4=GausBeam}` |
| поле моды | `/fields/<nphi>/{Ex,Ey,Ez}` | `complex128 (Nr, Msmax)` | ось 0 — радиальный индекс, ось 1 — полоидальный угол |
| номер моды | `/fields/<nphi>.attrs['nphi']` | `int` | надёжнее имени группы |
| координаты | `/grid/X`, `/grid/Y` | `float64 (Nr, Msmax)`, см | **только для вывода** `Epxs*.dat`; в сумме не участвуют |
| версия схемы | корневой атрибут `format_version` | `str` | текущая `"0.96"` |

Список задач — `tasks/*/results.h5` (или порядок из `logs/task_array.txt`).
Диапазон серии — `[series]` в run-level `input.toml`.

## 3. Вариант A: вакуумный запас не воспроизводится

Легаси-опция 7 писала `NRhoOut = int(1.1·Nr)` радиальных строк, добавляя
«вакуумный запас» за границей плазмы (`i > Nr`) с полем, равным нулю
(`RhoOut`, `grid2D.f90`). В HDF5 этих точек нет: `/grid/X`,`/grid/Y` содержат
ровно `Nr` строк.

**Решение (вариант A): запас не воспроизводится.** Viewer отдаёт только `Nr`
радиальных точек — поле за границей физически ноль, запас был чисто
оформительским. Выходные файлы поэтому короче легаси на
`(int(1.1·Nr) − Nr)` строк (для `Nr=101` — на 10 строк).

## 4. Полный скрипт (для переноса в репозиторий viewer)

Зависимости: `numpy`, `h5py`. Запуск:

```bash
python total_field_pol_xs.py <RUN_DIR> --phi 30 -o <OUT_DIR>
# <RUN_DIR> = Results/<config>/<timestamp>/   (внутри tasks/*/results.h5)
```

```python
#!/usr/bin/env python3
"""Total poloidal field cross-section, summed over the nphi spectrum.

Viewer-side port of the legacy Wave2D option 7 (PrintTotalFieldPolXS).
Reads only tasks/*/results.h5 (HDF5 contract, format_version 0.96).
Variant A: no vacuum margin beyond Nr (see the contract doc).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import numpy as np

SUPPORTED_FORMAT = ("0.96",)
ANT_GRILL, ANT_GAUSS_BEAM = 1, 4


def find_task_files(run_dir: Path):
    """Return sorted tasks/*/results.h5 under a run directory."""
    files = sorted((run_dir / "tasks").glob("*/results.h5"))
    if not files:
        raise FileNotFoundError(f"no tasks/*/results.h5 under {run_dir}")
    return files


def read_spectrum(task_files):
    """Read the run-level /spectrum group (complex An and its attrs)."""
    for p in task_files:
        with h5py.File(p, "r") as f:
            if "spectrum" in f:
                s = f["spectrum"]
                n = s["n"][...].astype(int)
                an = s["An"][...].astype(complex)
                attrs = {k: s.attrs[k] for k in s.attrs}
                fmt = f.attrs.get("format_version")
                return n, an, attrs, fmt
    raise FileNotFoundError("no /spectrum group in any task results.h5")


def compute_total_field(task_files, phi_deg, mode_filter=None):
    """Sum An(nphi)*exp(i*nphi*phi)*E_nphi over all solved modes.

    Coordinates are not involved: returns (Ex, Ey, Ez), used_modes,
    spectrum_attrs.
    """
    n, an, attrs, fmt = read_spectrum(task_files)
    if isinstance(fmt, bytes):
        fmt = fmt.decode()
    if fmt not in SUPPORTED_FORMAT:
        print(f"warning: format_version={fmt!r} not in {SUPPORTED_FORMAT}", file=sys.stderr)
    ant_type = int(attrs.get("ant_type", -1))
    if ant_type not in (ANT_GRILL, ANT_GAUSS_BEAM):
        print(f"warning: ant_type={ant_type} is neither grill nor gbeam", file=sys.stderr)

    weights = {int(k): complex(v) for k, v in zip(n, an)}
    phi = np.deg2rad(phi_deg)
    acc = None
    used = []
    for p in task_files:
        with h5py.File(p, "r") as f:
            fields = f.get("fields")
            if fields is None or len(fields) == 0:
                continue
            grp = next(iter(fields))
            nphi = int(fields[grp].attrs["nphi"])
            if mode_filter is not None and nphi not in mode_filter:
                continue
            w = weights.get(nphi)
            if w is None:
                print(f"warning: no An for nphi={nphi}, skip", file=sys.stderr)
                continue
            term = w * np.exp(1j * nphi * phi)
            ex = fields[grp]["Ex"][...]
            ey = fields[grp]["Ey"][...]
            ez = fields[grp]["Ez"][...]
            if acc is None:
                acc = [term * ex, term * ey, term * ez]
            else:
                acc[0] += term * ex
                acc[1] += term * ey
                acc[2] += term * ez
            used.append(nphi)
    if acc is None:
        raise RuntimeError("no usable modes found")
    return acc, used, attrs


def read_grid(task_files):
    """Return (X, Y) in cm; identical for all tasks, so read from the first."""
    with h5py.File(task_files[0], "r") as f:
        return f["grid/X"][...], f["grid/Y"][...]


def _e15_4(x: float) -> str:
    """Format a real like Fortran '(e15.4)' -> ' 0.1234E+01' (15 chars)."""
    x = float(x)
    if x == 0.0 or not np.isfinite(x):
        body = "0.0000E+00"
    else:
        mant, exp = f"{abs(x):.3E}".split("E")
        body = f"{'-' if x < 0 else ''}0.{mant.replace('.', '')}E{int(exp) + 1:+03d}"
    return body.rjust(15)


def write_dat(out_dir: Path, X, Y, Ex, Ey, Ez):
    """Write Epxs1..3.dat (X,Y,Re,Im) and Epxsa.dat (X,Y,|E|), Fortran 'e15.4'."""
    Ea = np.sqrt(np.abs(Ex) ** 2 + np.abs(Ey) ** 2 + np.abs(Ez) ** 2)
    nr, msmax = Ex.shape
    paths = [out_dir / f"Epxs{j}.dat" for j in (1, 2, 3)] + [out_dir / "Epxsa.dat"]
    with open(paths[0], "w") as f1, open(paths[1], "w") as f2, \
         open(paths[2], "w") as f3, open(paths[3], "w") as fa:
        # legacy order: outer radius -> axis, poloidal angle 0..2pi
        for ir in range(nr - 1, -1, -1):
            for it in range(msmax):
                x, y = _e15_4(X[ir, it]), _e15_4(Y[ir, it])
                f1.write(f"{x}{y}{_e15_4(Ex[ir, it].real)}{_e15_4(Ex[ir, it].imag)}\n")
                f2.write(f"{x}{y}{_e15_4(Ey[ir, it].real)}{_e15_4(Ey[ir, it].imag)}\n")
                f3.write(f"{x}{y}{_e15_4(Ez[ir, it].real)}{_e15_4(Ez[ir, it].imag)}\n")
                fa.write(f"{x}{y}{_e15_4(Ea[ir, it])}\n")
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path, help="run root with tasks/*/results.h5")
    ap.add_argument("-p", "--phi", type=float, required=True, help="toroidal angle, degrees")
    ap.add_argument("-o", "--output", type=Path, default=None, help="output dir (default: run_dir)")
    ap.add_argument("--nphi", type=int, nargs="*", default=None, help="restrict to these modes")
    args = ap.parse_args(argv)

    out_dir = args.output or args.run_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    task_files = find_task_files(args.run_dir)
    modes = set(args.nphi) if args.nphi else None
    acc, used, attrs = compute_total_field(task_files, args.phi, modes)
    X, Y = read_grid(task_files)  # only needed for the .dat output
    paths = write_dat(out_dir, X, Y, *acc)
    print(f"modes used: {len(used)} (nphi in [{min(used)}, {max(used)}])")
    print(f"Nsmax={attrs.get('Nsmax')} ant_type={attrs.get('ant_type')} "
          f"grill_type={attrs.get('grill_type')}")
    for p in paths:
        print("wrote", p)


if __name__ == "__main__":
    raise SystemExit(main())
```

## 5. Валидация

1. **Одна мода.** Запустить с `--nphi <n>` (или серией из одной задачи):
   `Ea_tot` должен совпасть с `|An(n)|·/fields/<nphi>/Ea`. В массивах до
   записи в файл — с точностью машинного округления; в записанных `.dat` —
   с точностью формата `e15.4` (~5e-6). Проверено на
   `Results/FT-2_LH_nphi_lite/2026-10-23_00-26-35` (`nphi=0`):
   `max|Ea_tot − |An(0)|·Ea| ≈ 1.4e-17` (in-memory),
   `≈ 5.0e-6` (после `e15.4`), `|An(0)| = 0.05859375`.
2. **Координаты.** `X`,`Y` в `Epxs*.dat` должны совпадать с `/grid/X`,`/grid/Y`
   (с точностью формата `e15.4`) и ложиться на границу `rho=a0` при `ir=Nr−1`.
3. **Полный спектр.** На том же прогоне (245 мод, `Nr=101`, `Msmax=512`)
   скрипт отрабатывает за ~2 с; `|E_total|` конечен, симметрия по
   `phi → −phi`/азимуту qualitatively сохраняется.
4. **Регресс.** Форматтер `_e15_4` сверен с gfortran `'(e15.4)'` побайтово на
   наборе значений (совпадение).

## 6. Замечания

- `An` берётся из `/spectrum` первой задачи, где группа есть; все задачи серии
  обязаны иметь одинаковый `/spectrum` (владелец — Wave2D).
- Если в прогоне есть `nphi=0` и `±n`: цикл идёт по всем найденным задачам,
  порядок не важен — сумма коммутативна.
- Единицы поля — условные единицы кода (`arb. units`), координаты — в сантиметрах (см. §2).
- Абсолютная шкала `An` задаётся `Amptor` антенны, а не `Pinp`; для физических
  Вт/кВт нужна отдельная нормировка (см. `docs/toroidal-amplitudes-an.md` §5).

## 7. Топ-вид тора в GUI (наш viewer)

Для любого датасета с осью `phi` (`total_fields.hdf5`: `/fields/{Ex,Ey,Ez,Ea}`)
в `w2d_viewer`/`w2d_app` доступен чекбокс **«Тороидальный вид»**: рядом с
полоидальной картой рисуется топ-вид тора. Если в файле есть `/geometry/R`
(большой радиус `R(rho,theta)`, см), на схему накладывается
**экваториальное сечение `Z=0`**: точки мидплейна `theta=0` (наружу) и
`theta=180` (внутрь) для каждого угла `phi` кладутся в полярные координаты
`(R·cos phi, R·sin phi)` и окрашиваются выбранной составляющей. Стрелка-«часовая» указывает текущий `phi`
(значение из `/phi`, выбранное слайдером моды) и кончается на внутренней границе
кольца; от неё до внешней границы идёт подсвеченный луч того же цвета (выбранное
сечение). Угол отсчитывается от `+x` против часовой стрелки (стандартная ориентация
`(R, phi, Z)`). Нефизичные сентинелы `R <= 0` (ось) отбрасываются. Если
`/geometry/R` нет (старый `total_fields.hdf5` — надо перегенерировать),
рисуется только схема-компас без данных. Для merged-файла (ось `nphi`)
переключатель не показывается — тороидального угла там нет.
