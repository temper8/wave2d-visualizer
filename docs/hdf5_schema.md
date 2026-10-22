# Схема HDF5-файла результатов (`results.h5`)

Документ описывает структуру HDF5-файла, который создаётся после расчёта и
лежит в каталоге задачи
(`Results/<конфигурация>/<дата-время>/tasks/<задача>/results.h5`). Лаунчер
дополнительно собирает run-level файл в корне прогона — см.
«Общий (run-level) отчёт `report.h5`».

Основано на модуле `Source/WaveToP/hdf5_writer.f90` (запись) и
`Source/WaveToP/hdf5_manager.f90` (низкоуровневые операции).

## Версия формата

Схема версионируется корневым атрибутом `format_version` (строка):

| Атрибут | Тип | Значение | Смысл |
|---|---|---|---|
| `format_version` | string | `0.96` | версия схемы HDF5-файла |

Атрибут пишется один раз при создании файла (`open('NEW')`) в
`write_report_to_hdf5` и сохраняется при дозаписи (`poloidal_field_2d`) и при
сборке общего файла серии. Версия инкрементируется при несовместимых
изменениях структуры. Чтение: `f.attrs['format_version']` (h5py).

## Кто и когда пишет файл

1. `wave2D` (опция 16, `FieldSolver`, вызывается лаунчером первым):
   - создаёт `results.h5` заново (`open('NEW')` — файл усекается);
   - пишет `/report/<task_name>/system`, `/report/toolchain` и
     `/report/<task_name>/run` (`created_local_time`, `task_id`), где
     `task_name` — имя каталога задачи;
   - пишет `/input/*`;
   - после `FieldSolver` дописывает `/report/<task_name>/run/elapsed_s`.
2. `power_balance` (`bin/power_balance.exe`, шаг `PowerBalance`):
   - открывает файл на дозапись (`open('OLD')`);
   - пишет группу `/power_balance/nphi*` — 1D радиальный энергобаланс моды.
3. `poloidal_field_2d` (запускается лаунчером после основного счёта):
   - открывает файл на дозапись (`open('OLD')`);
   - дописывает `/grid`, один блок `/fields/nphi*`, `/flux_surf`,
     `/plasma/params`, `/plasma/bfield`, `/plasma/dielectric`,
     `/plasma/resonance`, `/plasma/wkb`, `/geometry`.
4. `spectrum_an` (`bin/spectrum_an.exe`, шаг `SpectrumAn`, последний):
   - открывает файл на дозапись (`open('OLD')`);
   - пишет run-level группу `/spectrum` (тороидальный спектр антенны `An`).
5. Лаунчер (`launcher/results.py`) после завершения задачи дописывает через
   `h5py`:
   - `write_git_provenance` — в `/report/toolchain` поля `git_commit`,
     `git_branch`, `git_dirty`;
   - `write_report` — в `/report/<task_name>` данные из `report.toml`
     (`[metadata]` и `[execution_result]` — атрибуты группы, `[steps.*]` —
     подгруппы `duration/` и `status/`; разности времен считает лаунчер).

Важно: `poloidal_field_2d` обрабатывает **одну** выбранную моду `nphi`, поэтому
в файле **задачи** ровно одна группа `/fields/nphi*` (сокращённо `nphi`). Только
для серии по `nphi` лаунчер объединяет несколько мод в один файл (см. ниже).

## Соглашения о данных

- **Числа**: действительные — 8-байтовые (`H5T_IEEE_F64LE`), комплексные —
  составной тип `{r, i}` (`H5T_COMPOUND`); при чтении через `h5py` комплексные
  датасеты видны как `complex128`.
- **Размерности**: 2D-массивы в Фортране объявлены как `(Msmax, Nr)` — первым
  идёт полоидальный индекс, вторым радиальный. Из-за несовпадения порядка
  осей C/Fortran при чтении (`h5py`, `h5dump`) датасет выглядит как
  `(Nr, Msmax)`:
  - ось 0 — радиальный индекс (`Nr`, вдоль малого радиуса);
  - ось 1 — полоидальный индекс (`Msmax`, угол θ).
  Пример: `f['grid/X'][ir, itheta]`, где `ir = 0..Nr-1`.
- **Dimension scales**: пока **не привязаны** (нет атрибутов `CLASS`,
  `DIMENSION_LIST`). Оси заданы неявно порядком выше; координаты —
  `grid/rho`, `grid/psi`, а полоидальный угол будет добавлен (`grid/theta_deg`)
  вместе с scales. План — см. `TODO/hdf5-dimension-scales.md`.
- **Единицы**: атрибуты и датасеты записываются в тех единицах, в которых
  величины хранятся в модулях кода. Часть длин нормирована (внутренние
  единицы), плотность/температура/частота — физические; конкретные единицы
  указаны в таблицах ниже.
- **Магнитная ось**: на оси (радиальный индекс 0) расчёт ведётся не для всех
  полоидальных точек, поэтому некоторые датасеты в строке `ir = 0` не
  заполнены (см. «Особенности» в конце).
- **Соответствие `input.toml`**: группы внутри `/input` названы так же, как
  секции `input.toml` (`w2grid`, `plasma`, `temper`, `kngrid`, `dens`), чтобы
  читателю было тривиально сопоставить входные параметры с конфигурацией.

## Структура

```
results.h5                  # корневой атрибут: format_version = "0.96"
├── report/                 # провенанс: окружение, инструменты, запуск
│   │                       #   + атрибуты прогона (только nphi:
│   │                       #     sum_tasks_time_sec, wall_time_sec)
│   ├── toolchain/          # compiler_ver, compiler_opt, hdf5_ver
│   │                       #   + git_commit, git_branch, git_dirty (пишет лаунчер)
│   └── <task_name>/        # по одной группе на задачу (имя = каталог задачи)
│       ├── system/         # окружение и железо узла: system, hostname, cpu_model,
│       │                   #   omp/openblas/mkl_num_threads, omp_max_threads
│       ├── run/            # created_local_time, task_id, elapsed_s
│       ├── duration/       # времена шагов, с: FieldSolver, PowerBalance, ...
│       ├── status/         # статусы шагов: SUCCESS/FAILED/SKIPPED (+ *_exit_code)
│       └── (attrs)         # node, start_time, slurm_job_id, status,
│                           #   exit_code, total_time_sec
├── input/                  # атрибуты входных параметров (имена = секции .toml)
│   ├── w2grid/             # [w2grid]
│   ├── plasma/             # [plasma]
│   ├── temper/             # [temper]
│   ├── kngrid/             # [kngrid]
│   └── dens/               # [dens]
├── grid/                   # сетка
│   ├── rho                 # (Nr), см (физическая радиальная ось)
│   ├── psi                 # (Nr), 1 (нормированная потоковая координата rho/a0)
│   ├── X                   # (Nr, Msmax), см
│   └── Y                   # (Nr, Msmax), см
├── geometry/               # R, Jc, Nh, sinb, cosb
├── plasma/                 # результаты 2D по плазме
│   ├── params/             # ne, coll_rate, damp_rate, Te, Ti, VRe, VRi
│   ├── bfield/             # Btot, Btor, Bpol, alpha, Nparall, jp
│   ├── dielectric/         # eps, gee, eta, L, aTT, aMX (комплексные)
│   ├── resonance/          # w0_wpe, w0_wlh, w0_wuh, w0_wce, Xcutoff_at_0, PolRes_at_0
│   └── wkb/                # Nrho1, Nrho2 (комплексные)
├── flux_surf/              # theta_deg, theta_pi_diff
├── spectrum/               # тороидальный спектр антенны An(n) (run-level)
│   ├── attrs: nphi_min, nphi_max, nphistep, Nsmax, dphi_rad,
│   │          ant_type, grill_type
│   ├── n                   # (M), int, nphi_min..nphi_max
│   ├── An                  # (M), complex128, arb. units
│   └── abs2                # (M), |An|^2, arb. units
├── power_balance/          # радиальный энергобаланс по модам nphi (как /fields)
│   └── nphi+122/           # группа моды (одна в файле задачи;
│       │                   #   много — в общем файле серии)
│       ├── attribute: nphi
│       ├── attrs: Pabs_kW, Pinp_kW, discrepancy
│       ├── psi             # (Nr), 1
│       ├── Sflux, dSflux_dpsi  # (Nr), kW
│       ├── dPld_dpsi, dPttmp_dpsi, dPmix_dpsi, dPtot_dpsi   # (Nr), kW
│       ├── dV              # (Nr), cm^3
│       ├── dP_tube         # (Nr), kW
│       └── p_ld, p_tt, p_mx    # (Nr), kW/cm^3
└── fields/                 # поля по модам nphi
    └── nphi+122/           # группа моды (одна в файле задачи;
        │                   #   много — в общем файле серии)
        ├── attribute: nphi
        ├── Ex, Ey, Ez      # (Nr, Msmax), комплексные
        └── Ea              # (Nr, Msmax), действительные
```

## Атрибуты

### `/report/<task_name>/system`

Окружение и железо узла, на котором считалась **эта** задача. Группа живёт под
задачей, а не в корне `/report`, потому что в серии задачи могут попасть на
разные узлы кластера (у каждого свой `hostname`/`cpu_model`).

| Атрибут | Тип | Смысл |
|---|---|---|
| `system` | string | ОС (например, `Linux`/`Windows`) |
| `hostname` | string | имя узла |
| `cpu_model` | string | модель CPU |
| `omp_num_threads` | string | значение `OMP_NUM_THREADS` (`unset`, если не задано) |
| `openblas_num_threads` | string | значение `OPENBLAS_NUM_THREADS` (`unset`, если не задано) |
| `mkl_num_threads` | string | значение `MKL_NUM_THREADS` (`unset`, если не задано) |
| `omp_max_threads` | int | эффективное число потоков OpenMP (`omp_get_max_threads()`); `0` — бинарник собран без OpenMP |

`*_num_threads` — это то, что *запросили* (env/планировщик), а `omp_max_threads` —
то, что OpenMP возьмёт по факту. На сборке без OpenMP `omp_max_threads = 0`,
хотя env-переменные всё равно сохраняются. Расхождение с числом потоков в
`Qinteg` (директива `NUM_THREADS(16)` в `forward_pass.f90`) — отдельный вопрос,
см. `TODO/qinteg-performance.md`.

### `/report/toolchain`

| Атрибут | Тип | Смысл |
|---|---|---|
| `compiler_ver` | string | версия компилятора (build-time) |
| `compiler_opt` | string | флаги компиляции |
| `hdf5_ver` | string | версия слинкованной `libhdf5` (runtime) |
| `git_commit` | string | полный SHA git-коммита (пишет лаунчер) |
| `git_branch` | string | имя ветки (пишет лаунчер) |
| `git_dirty` | string | `clean`/`dirty` — были ли незакоммиченные изменения (пишет лаунчер) |

### `/report/<task_name>/run`

| Атрибут | Тип | Смысл |
|---|---|---|
| `created_local_time` | string | локальное время создания файла, ISO-8601 без зоны (`2026-09-28T12:31:18`) |
| `task_id` | string | имя каталога задачи (`nphi-122`, `single`; в общем файле серии — задача-база) |
| `elapsed_s` | double | стенное время фазы `FieldSolver`, с (`-1`, если часы недоступны) |

### `/report/<task_name>`

Данные из `report.toml` (пишет `scripts/task_runner.sh`, разности времен —
`write_report` лаунчера). Поля `[metadata]` и `[execution_result]` хранятся
атрибутами самой группы, шаги `[steps.*]` — подгруппами `duration/` и `status/`
(см. ниже).

| Атрибут | Тип | Смысл |
|---|---|---|
| `task_name` | string | имя задачи (из `[metadata]`, совпадает с `task_id` и именем каталога) |
| `node` | string | узел, где выполнялся пайплайн |
| `start_time` | string | время старта пайплайна, ISO-8601 с зоной |
| `slurm_job_id` | string | id SLURM-задачи или `local` |
| `status` | string | итоговый статус (`SUCCESS`/`FAILED_*`) |
| `exit_code` | int | код возврата пайплайна |
| `total_time_sec` | double | полное время пайплайна, с |

Дубли (сохраняются намеренно): `task_name` ↔ `run/task_id`,
`start_time` ↔ `run/created_local_time`, `total_time_sec`/`duration/FieldSolver`
↔ `run/elapsed_s`.

### `/report/<task_name>/duration`

Стенное время каждого шага пайплайна, с (`end - start`, считает лаунчер):

| Атрибут | Смысл |
|---|---|
| `FieldSolver` | шаг `bin/wave2D.exe -w <task>` |
| `PowerBalance` | шаг `bin/power_balance.exe -w <task>` |
| `poloidal_field_2d` | шаг `bin/poloidal_field_2d.exe -w <task>` |

Длительность пишется только для выполненных шагов; у `SKIPPED` её нет.

### `/report/<task_name>/status`

Статус каждого шага (пишет лаунчер из `[steps.*]`):

| Атрибут | Смысл |
|---|---|
| `<step>` | `SUCCESS` / `FAILED` / `SKIPPED` |
| `<step>_exit_code` | код возврата шага (int; у `SKIPPED` отсутствует) |

### `/input/w2grid` (целые)

| Атрибут | Смысл |
|---|---|
| `Nr` | число радиальных точек |
| `nphi1`, `nphi2`, `nphistep` | диапазон/шаг тороидальных мод |
| `Mmax` | максимальное полоидальное мод-число |
| `Nmax` | `6*(2*Mmax+1)` |
| `Msmax` | размер полоидальной сетки |

### `/input/plasma`

| Атрибут | Смысл |
|---|---|
| `R0`, `a0`, `SOL`, `Delx` | геометрия (длины — внутренние единицы кода) |
| `lamw`, `gamw` | эллиптичность/триангулярность последней поверхности |
| `wave_circular_frequency` | круговая частота волны, с⁻¹ |
| `number_of_ion_species` | число ионных сортов |

### `/input/temper`

| Атрибут | Смысл |
|---|---|
| `hot_plasma_model` | признак горячей плазмы |
| `Te0`, `Tel` | Te на оси/на лимитере, кэВ |
| `pTe1`, `pTe2`, `lTe` | параметры профиля Te (длины — внутренние единицы) |
| `Ti0`, `Til` | Ti на оси/на лимитере, кэВ |
| `pTi1`, `pTi2`, `lTi` | параметры профиля Ti |
| `VRmin` | мин. `kll*vt/ω0` |
| `Landau_damping`, `ECR_damping`, `ICR_damping`, `Transit_Time_damping`, `Mixed_Terms_damping` | признаки включения механизмов затухания |

### `/input/kngrid`

| Атрибут | Смысл |
|---|---|
| `Nymax`, `Nzmax` | границы по компонентам волнового вектора |
| `XSaveType` | режим сохранения по x (0 — нет, 1 — заданный x, 2 — у УР) |
| `Xcut` | позиция сохранения (нужна при `XSaveType = 1`) |

### `/input/dens`

| Атрибут | Смысл |
|---|---|
| `DensProfType` | тип профиля плотности (`PARAB`/`GAUSS`/`SPLIN`) |
| `de0`, `del` | плотность на оси/лимитере, 10¹² см⁻³ |
| `pde1`, `pde2`, `lde` | параметры профиля (длина — внутренние единицы) |
| `de0flc` | амплитуда флуктуаций плотности, 10¹² см⁻³ |
| `phiflc` | фаза флуктуаций, град |
| `lamflc` | длина волны флуктуаций (внутренние единицы) |
| `x0flc`, `dxflc` | центр и ширина области флуктуаций (внутренние единицы) |

## Датасеты

> **Юниты.** Каждый датасет несёт строковый атрибут `units`; значение `1` —
> безразмерная величина. Поля нормированы на амплитуду источника и даны в
> условных единицах кода (`arb. units`).

| Датасет | `units` |
|---|---|
| `grid/rho`, `grid/X`, `grid/Y` | `cm` |
| `grid/psi` | `1` |
| `geometry/R`, `geometry/Jc`, `geometry/Nh` | `cm` |
| `geometry/sinb`, `geometry/cosb` | `1` |
| `plasma/params/ne` | `10^12 cm^-3` |
| `plasma/params/Te`, `plasma/params/Ti` | `keV` |
| `plasma/params/coll_rate`, `damp_rate`, `VRe`, `VRi` | `1` |
| `plasma/bfield/Btot`, `Btor`, `Bpol` | `kG` |
| `plasma/bfield/alpha` | `deg` |
| `plasma/bfield/Nparall` | `1` |
| `plasma/bfield/jp` | `kA/cm^2` |
| `plasma/dielectric/*` | `1` |
| `plasma/resonance/*` | `1` |
| `plasma/wkb/Nrho1`, `Nrho2` | `1` |
| `spectrum/n` | `1` |
| `spectrum/An`, `spectrum/abs2` | `arb. units` |
| `flux_surf/theta_deg`, `theta_pi_diff` | `deg` |
| `fields/nphi*/Ex`, `Ey`, `Ez`, `Ea` | `arb. units` |

### `/grid`

| Датасет | Размерность | Смысл |
|---|---|---|
| `rho` | `(Nr)` | радиальная координата полярной сетки, см (совпадает с радиальной осью 2D-датасетов) |
| `psi` | `(Nr)` | нормированная потоковая координата `rho/a0` (`[0,1]`) |
| `X` | `(Nr, Msmax)` | декартова координата X, см |
| `Y` | `(Nr, Msmax)` | декартова координата Y, см |

### `/fields/nphi*` (например, `nphi+122`, `nphi-061`, `nphi+000`)

В файле задачи такая группа одна; в общем файле серии — по одной на моду.
Датасеты поля лежат прямо в группе моды (без промежуточной `field_2D`).

- атрибут `nphi` — целое тороидальное число.

| Датасет | Размерность | Смысл |
|---|---|---|
| `Ex`, `Ey`, `Ez` | `(Nr, Msmax)` | комплексные проекции поля, условные единицы кода |
| `Ea` | `(Nr, Msmax)` | `sqrt(|Ex|²+|Ey|²+|Ez|²)`, условные единицы кода |

### `/flux_surf`

| Датасет | Размерность | Смысл |
|---|---|---|
| `theta_deg` | `(Nr, Msmax)` | полоидальный угол θ, град |
| `theta_pi_diff` | `(Nr, Msmax)` | `π − |θ − π|`, град |

### `/power_balance/nphi*` (например, `nphi+122`, `nphi-061`, `nphi+000`)

Радиальный энергобаланс для одной моды `nphi` — замена прежних `.dat`
(`flux(psi).dat`, `pabs(psi).dat`, `power_balance.dat`). В файле задачи такая
группа одна; в общем файле серии — по одной на моду, как в `/fields`.
Датасеты длины `Nr`; ось `ir = 0` (r = 0) занулена.

- атрибут `nphi` — целое тороидальное число (одна мода, как в `/fields`);
- атрибут `Pabs_kW` — полная поглощённая мощность, кВт;
- атрибут `Pinp_kW` — входная (пойнтинговская) мощность, кВт;
- атрибут `discrepancy` — `|Pabs − Pinp| / mean(Pabs, Pinp)`, безразмерно.

| Датасет | Единицы | Смысл |
|---|---|---|
| `psi` | 1 | `rho/a0` (дублирует `/grid/psi`) |
| `Sflux` | kW | поток энергии через поверхность потока |
| `dSflux_dpsi` | kW | производная потока по `psi` |
| `dPld_dpsi`, `dPttmp_dpsi`, `dPmix_dpsi`, `dPtot_dpsi` | kW | вклады (LD, TTMP, mixed) и их сумма |
| `dV` | cm³ | объём трубки потока |
| `dP_tube` | kW | мощность, поглощённая в трубке |
| `p_ld`, `p_tt`, `p_mx` | kW/cm³ | удельные плотности вкладов |

### `/spectrum` (тороидальный спектр антенны `An(n)`)

Run-level свойство антенны, **не** разбито по модам `nphi`; в файле ровно
одна группа. Пишет `bin/spectrum_an.exe` (шаг `SpectrumAn`,
`core/an_spectrum_mod.f90`) в файл **задачи**; для серии по `nphi` лаунчер
копирует базовый файл целиком, поэтому группа попадает и в общий
`results.h5`. См. формулу и сверку с `Espctor.dat` в
`docs/toroidal-amplitudes-an.md`.

- атрибут `nphi_min`, `nphi_max`, `nphistep` — запрошенный диапазон (секция
  `[spectrum]`);
- атрибут `Nsmax` — длина тороидального FFT (степень двойки);
- атрибут `dphi_rad` — `2π/Nsmax`, рад;
- атрибут `ant_type` — тип антенны (`1` = Grill, из `w2source.inp`);
- атрибут `grill_type` — `1` = E-grill, `2` = H-grill (из `w2wall.inp`).

| Датасет | Размерность | Единицы | Смысл |
|---|---|---|---|
| `n` | `(M)` | 1 | тороидальное число, `nphi_min … nphi_max` |
| `An` | `(M)` | arb. units | комплексная амплитуда `An(n)` |
| `abs2` | `(M)` | arb. units | `|An|^2` (ключ упорядочивания серии, P8) |

`M = nphi_max − nphi_min + 1`. Абсолютный масштаб задаёт `Amptor` из
`w2wall.inp`. Одинаков для всех задач серии — поэтому и хранится один раз.

### `/plasma/params`

| Датасет | Смысл |
|---|---|
| `ne` | плотность, 10¹² см⁻³ |
| `coll_rate` | частота столкновений |
| `damp_rate` | скорость затухания |
| `Te`, `Ti` | температуры, кэВ |
| `VRe`, `VRi` | `k∥·v_Te/ω0` и `k∥·v_Ti/ω0` |

### `/plasma/bfield`

| Датасет | Смысл |
|---|---|
| `Btot`, `Btor`, `Bpol` | магнитное поле, кГс |
| `alpha` | угол, град |
| `Nparall` | продольный показатель преломления |
| `jp` | плотность тока, кА/см² |

### `/plasma/dielectric` (комплексные)

`eps`, `gee`, `eta`, `L`, `aTT`, `aMX` — компоненты тензора диэлектрической
проницаемости (безразмерные).

### `/plasma/resonance`

`w0_wpe`, `w0_wlh`, `w0_wuh`, `w0_wce` — отношения частот; `Xcutoff_at_0`,
`PolRes_at_0` — положение отсечки/поляризационного резонанса.

### `/geometry`

| Датасет | Смысл |
|---|---|
| `R` | большой радиус, см |
| `Jc`, `Nh` | якобиан и метрический коэффициент, см |
| `sinb`, `cosb` | синус/косинус угла наклона поля |

### `/plasma/wkb` (комплексные)

`Nrho1`, `Nrho2` — два корня радиального показателя преломления (WKB).

## Общий (run-level) отчёт `report.h5`

Каждый прогон (одна задача или серия) собирает общий файл
`Results/<конфигурация>/<дата-время>/report.h5` функцией
`launcher/results.py:merge_reports`. Файл **report-only**: он всегда содержит
`/report` и **никогда** не содержит научных данных. Данные остаются в файлах
задач `tasks/<task_name>/results.h5` (см. выше); объединение данных — задача
внешнего просмотрщика результатов (viewer), а не лаунчера.

При сборке берётся `report/toolchain` и из каждой задачи копируется её группа
`report/<task_name>` (с `system/`, `run/`, `duration/`, `status/` и
атрибутами); в `/report` пишутся атрибуты прогона (`write_work_times`, см.
ниже). Кроме того, в `/report` всегда добавляются run-level группы
`/report/build` и `/report/system_info` (см. ниже). Файл пересоздаётся с нуля
(`'w'`), поэтому данные предыдущего merge не могут «протечь» в текущий.

В корень `/report` общего файла дополнительно пишутся атрибуты прогона
(`write_work_times`):

| Атрибут | Тип | Смысл |
|---|---|---|
| `sum_tasks_time_sec` | double | сумма `total_time_sec` по всем задачам |
| `wall_time_sec` | double | стенное время всего прогона по таймеру Python |

В корень `/report` общего файла дополнительно пишется группа `/report/build` —
паспорт сборки, скопированный из `bin/build-info.json` (`_write_build_info`):

| Атрибут | Тип | Смысл |
|---|---|---|
| `timestamp` | string | UTC-время сборки |
| `compiler` | string | компилятор (`FC`) |
| `compiler_version` | string | полная версия компилятора |
| `optflags` | string | флаги оптимизации сборки |
| `blas` | string | BLAS-библиотека и её версия |
| `hdf5` | string | версия HDF5 |
| `hdf5_libs` | string | линковочные библиотеки HDF5 |
| `git_commit`, `git_branch`, `git_dirty` | string/bool | git на момент сборки |
| `wave2D_sha256`, `poloidal_field_2d_sha256` | string | sha256 бинарников |

Группа появляется только если `bin/build-info.json` существует (сборка
Windows его не создаёт — там шаг пропускается). Она
служит для сопоставления прогона с конкретной сборкой: `*_sha256` однозначно
привязывают результаты к бинарникам. `/report/toolchain` при этом остаётся тем,
что отдал сам Fortran (компилятор/HDF5/флаги), и не перезаписывается.

В корень `/report` общего файла также пишется группа `/report/system_info` —
машина и Python, запустившие лаунчер (из `launcher/system_info.py`; тот же
набор, что в `system_info.ini`, `_write_system_info`):

| Атрибут | Тип | Смысл |
|---|---|---|
| `system` | string | ОС (`Linux`/`Windows`/…) |
| `host` | string | имя узла, где запущен лаунчер |
| `release` | string | версия ядра/ОС |
| `machine` | string | архитектура (`x86_64`, …) |
| `processor` | string | процессор (часто пусто на Linux) |
| `python` | string | версия Python лаунчера |

Это узел-оркестратор, а не узел счёта: per-task `report/<task_name>/system`
описывает машину, считавшую конкретную задачу. Группа пишется всегда, когда
известен `system_info`.

## Контракт для внешнего потребителя (viewer)

Обмен между репозиториями Wave2D и viewer'ом идёт только через формат данных
(HDF5-схему и раскладку каталога), без импорта Python-кода. Viewer читает:

| Что | Где |
|---|---|
| Научные данные задачи (`/input`, `/grid`, `/geometry`, `/plasma`, `/fields/nphi*`, `/power_balance/nphi*`, `/flux_surf`, `/spectrum`) | `tasks/<task_name>/results.h5` — **единственный** источник данных |
| Список и порядок задач | `logs/task_array.txt` (SLURM) либо отсортированные `tasks/*/` |
| Параметры серии (`var`, `start`, `step`, `number`) | `input.toml` прогона, секция `[series]` |
| Статусы, тайминги, git, build, system_info прогона | `report.h5`, группа `/report` |
| Сырой per-task отчёт | `tasks/<task_name>/report.toml` |

Правила:

- диапазон мод серии берите из `[series]` в `input.toml`; в файле задачи
  `input/w2grid` всегда `nphi1 == nphi2 == значение моды`;
- run-level `report.h5` не гарантирует наличия данных ни для одной серии;
- в старых прогонах (до перехода на `report.h5`) данные серии по `nphi` могли
  лежать в run-level `results.h5` — при чтении старых каталогов учитывайте оба
  варианта, но приоритет всегда у `tasks/*/results.h5`;
- версия схемы — корневой атрибут `format_version`; проверяйте его перед
  чтением. Владелец схемы — репозиторий Wave2D
  (`Source/WaveToP/hdf5_writer.f90`).

## Особенности

- **Ось.** Строка `ir = 0` (магнитная ось) заполняется не для всех датасетов:
  `flux_surf` и `plasma/wkb` на оси не вычисляются, а в `plasma/params`,
  `plasma/bfield`, `plasma/dielectric`, `plasma/resonance` и `geometry` на оси
  рассчитана только первая полоидальная точка. Не использовать ось без
  проверки.
- **Не всё попадает в файл.** Часть величин в коде помечена комментарием и не
  записывается: `Mspow_excess`, `Pinterv`, `freq` (вместо неё
  `wave_circular_frequency`), `list_of_ions`, весь блок `w2front`,
  `kymax2D`, `kzmax2D`, `accuracy`, поле `R` в `plasma/dielectric`, `w0_wci` в
  `plasma/resonance`, а также сохранённые в структурах `x`/`y` (они есть в
  `/grid`).

## История схемы и миграция

### 0.96 (текущая)

- run-level артефакт разделён: вместо общего `results.h5` (для серии по `nphi`
  он содержал данные) — report-only `report.h5`; научные данные остаются
  только в `tasks/<task_name>/results.h5` и объединяются внешним viewer'ом
  (`launcher/results.py:merge_reports`). **Структура per-task файла не
  изменилась** — bump `0.95 → 0.96` отражает смену run-level контракта:
  `report.h5` несовместим со старым combined `results.h5` (в нём больше нет
  групп `/input`, `/grid`, `/fields/*`, …).
- добавлена run-level группа `/spectrum` — тороидальный спектр антенны
  `An(n)` (`n`, `An` комплексный, `abs2 = |An|^2`), пишет
  `bin/spectrum_an.exe` (шаг `SpectrumAn`); аддитивное изменение.
- добавлена группа `/power_balance/nphi*` — 1D радиальный энергобаланс,
  который пишет отдельный бинарник `bin/power_balance.exe` (шаг
  `PowerBalance`); аддитивное изменение (объединение по модам теперь на
  стороне viewer'а).

### 0.95

- группа `/manifest` переименована в `/report`: общий `/report/toolchain` и
  per-task `/report/<task_name>`;
- `system` живёт под задачей: `/report/<task_name>/system` (узлы кластера
  разные, поэтому глобальной группы `/report/system` больше нет);
- `run` переехал под задачу: `/report/<task_name>/run`;
- данные `report.toml` пишутся в `/report/<task_name>`: `[metadata]` и
  `[execution_result]` — атрибуты группы, `[steps.*]` — подгруппы
  `/report/<task_name>/duration` и `/report/<task_name>/status`, а
  `total_time_sec` считается из `[timestamps.total]` (пишет лаунчер,
  `write_report`).
- в `/report/<task_name>/system` добавлены потоки: `omp_num_threads`,
  `openblas_num_threads`, `mkl_num_threads` (env-значения, `unset` если не
  заданы) и `omp_max_threads` (`omp_get_max_threads()`, `0` без OpenMP);
  для этого `system_info.f90` препроцессируется (`-cpp` у gfortran, `-fpp` уже
  был у Intel) под `#ifdef _OPENMP`.
- в общем файле добавлена run-level группа `/report/system_info` — машина и
  Python лаунчера (из `launcher/system_info.py`, как в `system_info.ini`).

### 0.94

- `/grid/rho` теперь имеет длину `Nr`, хранится в см (`rho*scale`) и точно
  совпадает с радиальной осью всех 2D-датасетов `(Nr, Msmax)`;
- добавлен `/grid/psi` — нормированная потоковая координата `rho/a0` (`units=1`);
- из `/flux_surf` удалён `psi` (дублировал `/grid/psi`, θ-константа);
- из `/input/w2grid` удалён атрибут `Nrmargin` (устаревшее глобальное состояние).
  Запас за `a0` остался только в легаси-ASCII выводе (`.dat`/`.bln`) и теперь
  вычисляется локально в процедурах вывода.

### 0.93

Аддитивные дополнения манифеста (старые читатели, игнорирующие незнакомые
атрибуты, работать не перестают):

- добавлена группа `/manifest/run` (`created_local_time`, `task_id`, `elapsed_s`);
- в `/manifest/toolchain` добавлены `git_commit`, `git_branch`, `git_dirty`
  (пишутся лаунчером через `h5py` после расчёта);
- у всех датасетов появился строковый атрибут `units` (см. раздел «Датасеты»).

### 0.92

Реструктуризация «пространств имён» и упрощение путей:

| Было (0.91) | Стало (0.92) |
|---|---|
| `run_params/w2grid` | `input/w2grid` |
| `run_params/plasma` | `input/plasma` |
| `run_params/temperature` | `input/temper` |
| `run_params/kngrid` | `input/kngrid` |
| `run_params/density` | `input/dens` |
| `coord` | `grid` |
| `geometry_2D` | `geometry` |
| `plasma_par_2D` | `plasma/params` |
| `magnt_fld_2D` | `plasma/bfield` |
| `di_tensor_2D` | `plasma/dielectric` |
| `resonance_2D` | `plasma/resonance` |
| `wkb_2D` | `plasma/wkb` |
| `flux_surf_2D` | `flux_surf` |
| `nphi+000` (в корне) | `fields/nphi+000` |
| `nphi+000/field_2D/Ex` | `fields/nphi+000/Ex` |

### 0.91

| Было (0.9) | Стало (0.91) |
|---|---|
| корневой атрибут `version` | `format_version` |
| `run_info/system` (все атрибуты) | `manifest/system` (`system`, `hostname`, `cpu_model`) + `manifest/toolchain` (`compiler_ver`, `compiler_opt`, `hdf5_ver`) |

Также в 0.91 перестал создаваться текстовый `system_info.dat`; его поля
(`cpu_model`, компилятор) перенесены в `manifest/`.
