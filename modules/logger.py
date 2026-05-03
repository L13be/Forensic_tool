# modules/logger.py
from __future__ import annotations

import os
from datetime import datetime

LOG_DIR = "logs"


def init_logger() -> None:
    """Создаёт папку для логов если её нет."""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_action(action: str) -> None:
    """Записывает действие эксперта в лог-файл с временной меткой."""
    init_logger()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_filename = datetime.now().strftime("%Y-%m-%d") + "_session.log"
    log_path = os.path.join(LOG_DIR, log_filename)

    entry = f"[{timestamp}] {action}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)