# Поддержка схемы results.h5 >= 0.94

- **Приоритет:** P1
- **Статус:** done
- **Файлы:** `src/wave2d/schema.py`, `src/utils.py`, `w2d_render.py`,
  `src/wave2d/viewer.py`, `src/wave2d/app.py`, `tools/integrator*.py`,
  `docs/results_h5.md`

## Что сделано

- [x] Введён `src/wave2d/schema.py` (`MIN_FORMAT`, `UnsupportedFormatError`,
      `ensure_supported`/`open_results`, константы путей, `nphi`-хелперы);
      старые форматы отклоняются с сообщением «формат не поддерживается».
- [x] `w2d_render.py`/`viewer.py`/`app.py`/`integrator*.py`/`src/utils.py`
      переведены на новые пути (`/grid`, `/input`, `/plasma/*`,
      `/fields/nphi*`, `/manifest`), спека обновлена (`docs/results_h5.md`).
