import os
import csv
import datetime
from modules.logger import log_action

REPORTS_DIR = "reports"


def export_to_csv(results: list):
    """
    Экспортирует результаты в CSV.
    Автоматически собирает все поля из всех файлов —
    работает для DOCX, PDF, PPTX, изображений и т.д.
    """
    if not results:
        log_action("CSV экспорт: нет данных для экспорта")
        return

    os.makedirs(REPORTS_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(REPORTS_DIR, f"forensic_export_{timestamp}.csv")

    # Собираем все возможные поля из всех записей динамически
    all_fields = []
    for result in results:
        for key in result.keys():
            if key not in all_fields:
                all_fields.append(key)

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=all_fields,
            extrasaction="ignore",   # игнорируем лишние поля
            restval="—"              # пустые поля заполняем "—"
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result)

    log_action(f"CSV экспорт сохранён: {filename} | Записей: {len(results)}")
    print(f"  ✅ CSV экспорт сохранён: {filename}")
    return filename