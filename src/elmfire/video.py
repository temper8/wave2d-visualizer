"""Сборка видеоролика из кадров флуктуаций ELMFIRE.

Читает PNG-кадры (``polar_time_*.png``) из ``data/derived/frames/<run>/``
и склеивает их в ``data/derived/video/fluctuations_evolution.mp4``.

Точка входа — ``elmfire_video.py`` в корне репозитория.
"""

import imageio.v3 as iio
from tqdm import tqdm

from src.common.paths import frames_dir, video_dir

FPS = 15


def make_fluctuations_video(run_id: str, fps: int = FPS) -> None:
    """Склеивает кадры прогона ``run_id`` в MP4 (по умолчанию 15 кадров/с)."""
    print("\nСборка видеоролика...")

    # Все сохранённые кадры, отсортированные по имени (= по времени).
    images = sorted(frames_dir(run_id).glob("*.png"))

    if not images:
        print("Ошибка: не найдено кадров для создания видео.")
        return

    video_dir().mkdir(parents=True, exist_ok=True)
    video_name = video_dir() / "fluctuations_evolution.mp4"

    # Читаем кадры и записываем MP4.
    frames = [iio.imread(img) for img in tqdm(images, desc="Склейка кадров в видео")]
    iio.imwrite(str(video_name), frames, fps=fps)

    print(f"Видео успешно создано и сохранено как: {video_name}")
