from __future__ import annotations

from datetime import datetime
from modules.logger import log_action


def parse_date(date_str: str) -> datetime | None:
    """Пытается распарсить дату из строки."""
    try:
        # Убираем timezone info для сравнения
        clean = str(date_str).split("+")[0].split(".")[0].strip()
        return datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def detect_anomalies(metadata: dict[str, str]) -> list[str]:
    """
    Анализирует метаданные и возвращает список найденных аномалий.
    Каждая аномалия — потенциальный признак фальсификации документа.
    """
    anomalies = []
    filename = metadata.get("Файл", "")

    # Проверка 1: дата создания позже даты изменения
    created = parse_date(metadata.get("Дата создания", ""))
    modified = parse_date(metadata.get("Дата изменения", ""))

    if created and modified and created > modified:
        anomalies.append(
            "⚠️ Дата создания позже даты изменения — возможна подмена метаданных"
        )

    # Проверка 2: автор не совпадает с последним редактором
    author = metadata.get("Автор", "").strip().lower()
    last_mod = metadata.get("Последний редактор", "").strip().lower()

    if author and last_mod and author != last_mod \
            and author != "не указан" and last_mod != "не указан":
        anomalies.append(
            f"⚠️ Автор ({metadata['Автор']}) не совпадает с последним редактором "
            f"({metadata['Последний редактор']}) — документ редактировался другим лицом"
        )

    # Проверка 3: нулевой номер редакции при наличии дат
    revision = metadata.get("Номер редакции", "0")
    if str(revision) in ("0", "1") and created and modified and created != modified:
        anomalies.append(
            "⚠️ Номер редакции слишком мал при наличии изменений — возможен сброс истории"
        )

    # Проверка 4: пустой автор
    if metadata.get("Автор", "Не указан") == "Не указан":
        anomalies.append(
            "⚠️ Поле 'Автор' пустое — метаданные могли быть намеренно очищены"
        )

    if anomalies:
        log_action(f"Обнаружены аномалии в файле {filename}: {len(anomalies)} шт.")
    else:
        log_action(f"Аномалий не обнаружено в файле: {filename}")

    return anomalies