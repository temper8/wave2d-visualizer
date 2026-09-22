import glob
import os
import sys

import imageio.v3 as iio
from tqdm import tqdm

from src.common.paths import frames_dir, video_dir

run_id = sys.argv[1] if len(sys.argv) > 1 else "WagD"
output_dir = str(frames_dir(run_id))
# --- 3. СБОРКА ВИДЕОРОЛИКА ---
print("\nСборка видеоролика...")

# Ищем все сохраненные картинки и правильно их сортируем
images = sorted(glob.glob(os.path.join(output_dir, "*.png")))

if images:
    video_dir().mkdir(parents=True, exist_ok=True)
    video_name = str(video_dir() / "fluctuations_evolution.mp4")
    
    # Читаем кадры и записываем в MP4 видео
    # fps=5 означает 5 кадров в секунду. Подкрутите это число, если видео идет слишком медленно или быстро.
    frames = [iio.imread(img) for img in tqdm(images, desc="Склейка кадров в видео")]
    iio.imwrite(video_name, frames, fps=15)
    
    print(f"Видео успешно создано и сохранено как: {video_name}")
else:
    print("Ошибка: не найдено кадров для создания видео.")   