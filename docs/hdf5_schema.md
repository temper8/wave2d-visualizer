# Схема HDF5-файла результатов (`results.h5`)

Документ описывает структуру HDF5-файла, который создаётся после расчёта и
лежит в каталоге задачи
(`Results/<конфигурация>/<дата-время>/tasks/<задача>/results.h5`). Для серии по
`nphi` лаунчер дополнительно собирает общий файл в корне прогона — см.
«Общий файл для серии по `nphi`».

Основано на модуле `Source/WaveToP/hdf5_writer.f90` (запись) и
`Source/WaveToP/hdf5_manager.f90` (низкоуровневые операции).

## Версия формата

Схема версионируется корневым атрибутом `format_version` (строка):

| Атрибут | Тип | Значение | Смысл |
|---|---|---|---|
| `format_version` | string | `0.94` | версия схемы HDF5-файла |

Атрибут пишется один раз при создании файла (`open('NEW')`) в
`write_manifest_to_hdf5` и сохраняется при дозаписи (`poloidal_field_2d`) и при
сборке общего файла серии. Версия инкрементируется при несовместимых
изменениях структуры. Чтение: `f.attrs['format_version']` (h5py).

## Кто и когда пишет файл

1. `wave2D` (опция 16, `FieldSolver`, вызывается лаунчером первым):
   - создаёт `results.h5` заново (`open('NEW')` — файл усекается);
   - пишет `/manifest/system`, `/manifest/toolchain` и `/manifest/run`
     (`created_local_time`, `task_id`);
   - пишет `/input/*`;
   - после `FieldSolver` дописывает `/manifest/run/elapsed_s`.
2. `poloidal_field_2d` (запускается лаунчером после основного счёта):
   - открывает файл на дозапись (`open('OLD')`);
   - дописывает `/grid`, один блок `/fields/nphi*`, `/flux_surf`,
     `/plasma/params`, `/plasma/bfield`, `/plasma/dielectric`,
     `/plasma/resonance`, `/plasma/wkb`, `/geometry`.
3. Лаунчер (`launcher/results.py`, `write_git_provenance`) после завершения
   задачи дописывает через `h5py` в `/manifest/toolchain` поля `git_commit`,
   `git_branch`, `git_dirty`.

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
results.h5                  # корневой атрибут: format_version = "0.94"
├── manifest/               # провенанс: окружение, инструменты, запуск
│   ├── system/             # атрибуты: system, hostname, cpu_model
│   ├── toolchain/          # compiler_ver, compiler_opt, hdf5_ver
│   │                       #   + git_commit, git_branch, git_dirty (пишет лаунчер)
│   └── run/                # created_local_time, task_id, elapsed_s
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
└── fields/                 # поля по модам nphi
    └── nphi+122/           # группа моды (одна в файле задачи;
        │                   #   много — в общем файле серии)
        ├── attribute: nphi
        ├── Ex, Ey, Ez      # (Nr, Msmax), комплексные
        └── Ea              # (Nr, Msmax), действительные
```

## Атрибуты

### `/manifest/system`

| Атрибут | Тип | Смысл |
|---|---|---|
| `system` | string | ОС (например, `Linux`/`Windows`) |
| `hostname` | string | имя узла |
| `cpu_model` | string | модель CPU |

### `/manifest/toolchain`

| Атрибут | Тип | Смысл |
|---|---|---|
| `compiler_ver` | string | версия компилятора (build-time) |
| `compiler_opt` | string | флаги компиляции |
| `hdf5_ver` | string | версия слинкованной `libhdf5` (runtime) |
| `git_commit` | string | полный SHA git-коммита (пишет лаунчер) |
| `git_branch` | string | имя ветки (пишет лаунчер) |
| `git_dirty` | string | `clean`/`dirty` — были ли незакоммиченные изменения (пишет лаунчер) |

### `/manifest/run`

| Атрибут | Тип | Смысл |
|---|---|---|
| `created_local_time` | string | локальное время создания файла, ISO-8601 без зоны (`2026-09-28T12:31:18`) |
| `task_id` | string | имя каталога задачи (`nphi-122`, `single`; в общем файле серии — задача-база) |
| `elapsed_s` | double | стенное время фазы `FieldSolver`, с (`-1`, если часы недоступны) |

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

## Общий файл для серии по `nphi`

Для конфигурации с `[series] var = 'nphi'` каждая задача пишет свой
`results.h5` в `tasks/<задача>/`, а лаунчер (`launcher/results.py`,
`merge_nphi_results`) собирает общий файл
`Results/<конфигурация>/<дата-время>/results.h5`:

- базой копируется `results.h5` первой задачи — общие группы (`manifest`,
  `input`, `grid`, `geometry`, `plasma`, `flux_surf`) и её собственная
  группа `/fields/nphi*`;
- из каждой следующей задачи добавляется только её группа
  `/fields/nphi*`;
- в `/input/w2grid` записывается диапазон всей серии:
  `nphi1 = start`, `nphi2 = start + (number − 1)·step`, `nphistep = step`
  (в файле отдельной задачи там `nphi1 == nphi2 == значение моды`).

Таким образом, общий файл отличается от файла задачи только числом групп
`/fields/nphi*` и диапазоном в `input/w2grid`; остальные группы идентичны.

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

### 0.94 (текущая)

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
