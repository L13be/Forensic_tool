import os
import io
import re
from modules.logger import log_action

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import yadisk
    YADISK_AVAILABLE = True
except ImportError:
    YADISK_AVAILABLE = False


def get_client() -> object:
    if not YADISK_AVAILABLE:
        raise ImportError("Установите yadisk: pip install yadisk")
    token = os.environ.get("YANDEX_TOKEN", "")
    if not token:
        raise ValueError(
            "Токен Яндекс.Диска не найден. "
            "Добавьте YANDEX_TOKEN=<токен> в файл .env рядом с main.py"
        )
    client = yadisk.YaDisk(token=token)
    if not client.check_token():
        raise ValueError("Токен Яндекс.Диска недействителен или истёк")
    log_action("Авторизация в Яндекс.Диске выполнена успешно")
    return client


def extract_file_id(url: str) -> str:
    patterns = [
        r"disk\.yandex\.ru/d/([a-zA-Z0-9_-]+)",
        r"disk\.yandex\.ru/i/([a-zA-Z0-9_-]+)",
        r"yadi\.sk/d/([a-zA-Z0-9_-]+)",
        r"yadi\.sk/i/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_folder(url: str) -> bool:
    try:
        client = get_client()
        info = client.get_public_meta(url)
        return getattr(info, "type", "") == "dir"
    except Exception:
        return "/d/" in url and "/i/" not in url


def get_file_metadata(client, public_url: str) -> dict:
    try:
        info = client.get_public_meta(public_url)

        size     = getattr(info, "size", 0) or 0
        size_str = f"{size} байт ({round(size/1024, 2)} КБ)" if size else "Нет данных"

        owner = getattr(info, "owner", None)
        owner_login = "—"
        owner_name  = "—"
        if owner:
            owner_login = getattr(owner, "login",        "—")
            owner_name  = getattr(owner, "display_name", "—")

        created  = str(getattr(info, "created",  "—"))
        modified = str(getattr(info, "modified", "—"))

        metadata = {
            "ID документа": "—",
            "Название": getattr(info, "name", "—"),
            "Тип файла (MIME)": getattr(info, "mime_type", "—"),
            "Оригинальное имя": getattr(info, "name", "—"),
            "Размер": size_str,
            "Версия": "—",
            "ID последней ревизии": "—",
            "Хранилище": "Яндекс.Диск",

            "Владелец": owner_name,
            "Email владельца": "—",
            "Последний редактор": "—",
            "Email редактора": "—",
            "Поделился (имя)": "—",
            "Поделился (email)": "—",

            "Дата создания": created,
            "Дата изменения": modified,

            "Общий доступ": "Да",
            "В корзине": "Нет",
            "Избранное": "—",

            "Ссылка на документ": public_url,
            "Описание": "Нет",

            "[Доступ] Тип доступа": "🟢 Публичная ссылка",
            "[Доступ] Риск утечки": "Низкий",
            "[Доступ] Можно скачать": "Да",
            "[Доступ] Можно редактировать": "Нет",
            "[Доступ] Можно расшарить дальше": "—",
            "[Доступ] Можно копировать": "—",

            "MD5 (Яндекс)": getattr(info, "md5", "—"),
            "SHA256 (Яндекс)": getattr(info, "sha256", "—"),
            "Владелец (логин)": owner_login,
            "Тип ресурса": getattr(info, "type", "—"),
            "Превью доступно": "Да" if getattr(info, "preview", None) else "Нет",

            "Права доступа": [],
        }

        log_action(
            f"Метаданные Яндекс.Диска получены: {metadata['Название']} | "
            f"Владелец: {owner_login} | Размер: {size_str}"
        )

        return metadata

    except Exception as e:
        log_action(f"Ошибка получения метаданных Яндекс.Диска: {e}")
        return {"Ошибка": str(e)}


def download_file(client, public_url: str) -> bytes:
    try:
        buf = io.BytesIO()
        client.download_public(public_url, buf)
        return buf.getvalue()
    except Exception as e:
        log_action(f"Ошибка скачивания с Яндекс.Диска: {e}")
        return None


def list_folder_files(client, public_url: str) -> list:
    SUPPORTED_MIME = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "image/jpeg",
        "image/png",
        "image/tiff",
    ]

    files   = []
    try:
        items = client.get_public_meta(public_url, limit=100)
        embedded = getattr(items, "_embedded", None)
        if not embedded:
            return []

        for item in getattr(embedded, "items", []):
            mime = getattr(item, "mime_type", "")
            if mime in SUPPORTED_MIME:
                files.append({
                    "name":       getattr(item, "name",         "—"),
                    "mime_type":  mime,
                    "size":       getattr(item, "size",         0),
                    "public_url": getattr(item, "public_url",   None) or public_url,
                    "path":       str(getattr(item, "path",     "—")),
                    "md5":        getattr(item, "md5",          "—"),
                    "modified":   str(getattr(item, "modified", "—")),
                })
                print(f"     ✅ {item.name} ({mime.split('.')[-1]})")
            else:
                print(f"     ⏭️  Пропущен: {getattr(item,'name','—')} ({mime})")

    except Exception as e:
        log_action(f"Ошибка получения списка папки Яндекс.Диска: {e}")

    return files


def scan_yandex_file(client, public_url: str, mime_type: str, filename: str) -> dict:
    from modules.cloud.file_scanner import (
        scan_docx_images, scan_pdf_images,
        extract_full_exif
    )

    result = {
        "Файл":                filename,
        "MIME":                mime_type,
        "Статус скачивания":   "—",
        "Изображений найдено": 0,
        "Изображения":         [],
        "GPS обнаружен":       False,
        "Координаты":          [],
        "Все следы":           [],
        "Все аномалии":        [],
        "Устройства":          [],
        "Скрытый текст":       {},
    }

    print(f"\n  📥 Скачивание: {filename}")
    file_bytes = download_file(client, public_url)

    if not file_bytes:
        result["Статус скачивания"] = "❌ Ошибка скачивания"
        return result

    size_kb = round(len(file_bytes) / 1024, 2)
    result["Статус скачивания"] = f"✅ Скачан ({size_kb} КБ)"
    print(f"  ✅ Скачан: {size_kb} КБ")

    if "wordprocessingml" in mime_type or mime_type == "application/msword":
        images = scan_docx_images(file_bytes)

        import tempfile
        from modules.hidden_text import extract_hidden_text
        from modules.ole_analyzer  import full_ole_analysis
        from modules.virus_scanner import scan_file

        suffix = ".doc" if mime_type == "application/msword" else ".docx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # ── Скрытый текст ───────────────────────────────────────
            try:
                hidden = extract_hidden_text(tmp_path)
                result["Скрытый текст"] = hidden
                if hidden.get("Скрытых фрагментов", 0) > 0:
                    print(f"  👁️  Скрытых фрагментов: {hidden['Скрытых фрагментов']}")
                    for frag in hidden["Скрытый текст"]:
                        print(f"     📌 Параграф №{frag['Параграф №']}: {frag['Скрытый текст'][:100]}")
                    for anom in hidden["Аномалии"]:
                        result["Все аномалии"].append(f"[Скрытый текст] {anom}")
                else:
                    print("  👁️  Скрытый текст: не обнаружен")
            except Exception as e:
                log_action(f"Ошибка анализа скрытого текста: {e}")

            # ── VBA / DDE / OLE ─────────────────────────────────────
            try:
                ole = full_ole_analysis(tmp_path)
                result["OLE"] = ole

                vba = ole.get("VBA", {})
                dde = ole.get("DDE", {})
                enc = ole.get("Шифрование", {})

                if vba.get("Макросов найдено", 0):
                    risk  = vba.get("Оценка риска", "—")
                    score = vba.get("Счёт риска", 0)
                    print(f"  ☣️  VBA: {vba['Макросов найдено']} модуль(ей) | риск: {risk} (score={score})")
                    result["Все аномалии"].append(
                        f"[VBA] Обнаружены макросы: {vba['Макросов найдено']} модуль(ей), риск {risk}"
                    )
                    for kw in vba.get("Подозрительные ключевые слова", []):
                        result["Все следы"].append(f"[VBA] {kw}")
                else:
                    print("  ☣️  VBA макросы: не найдены")

                dde_fields = dde.get("Поля DDE", [])
                if dde_fields:
                    print(f"  ⚡ DDE-полей: {len(dde_fields)}")
                    for field in dde_fields:
                        cmd = field.get("Команда", field.get("Поле", ""))
                        result["Все аномалии"].append(f"[DDE] {cmd}")
                else:
                    print("  ⚡ DDE-поля: не обнаружены")

                if enc.get("Зашифрован"):
                    print("  🔒 Файл зашифрован")
                    result["Все аномалии"].append("[OLE] Файл зашифрован паролем")

            except Exception as e:
                log_action(f"Ошибка OLE-анализа облачного файла: {e}")

            # ── Вирусное сканирование ────────────────────────────────
            try:
                scan = scan_file(tmp_path)
                result["Вирусное сканирование"] = scan
                if scan.get("Находки"):
                    for f in scan["Находки"]:
                        result["Все аномалии"].append(f"[Вирус] {f}")
                print(f"  🛡️  Риск: {scan['Риск']}")
            except Exception as e:
                log_action(f"Ошибка вирусного сканирования: {e}")

        finally:
            os.unlink(tmp_path)

    elif mime_type == "application/pdf":
        images = scan_pdf_images(file_bytes)

    elif mime_type.startswith("image/"):
        images = [extract_full_exif(file_bytes, filename)]

    else:
        images = []

    result["Изображений найдено"] = len(images)
    result["Изображения"]         = images

    for img in images:
        gps = img.get("GPS", {})
        if gps.get("Координаты"):
            result["GPS обнаружен"] = True
            result["Координаты"].append({
                "Файл":        img["Файл"],
                "Координаты":  gps["Координаты"],
                "Google Maps": gps.get("Google Maps", ""),
                "Yandex Maps": gps.get("Yandex Maps", ""),
                "Высота":      gps.get("Высота над уровнем моря", "—"),
                "Скорость":    gps.get("Скорость", "—"),
                "Время GPS":   gps.get("Время GPS (UTC)", "—"),
            })
            print(f"  📍 GPS: {gps['Координаты']}")
        device = img.get("Камера", {}).get("Устройство", "")
        if device and device not in result["Устройства"]:
            result["Устройства"].append(device)
        for t in img.get("Следы",    []): result["Все следы"].append(f"[{img['Файл']}] {t}")
        for a in img.get("Аномалии", []): result["Все аномалии"].append(f"[{img['Файл']}] {a}")

    log_action(
        f"Сканирование Яндекс.Диска: {filename} | "
        f"Следов: {len(result['Все следы'])} | "
        f"Аномалий: {len(result['Все аномалии'])}"
    )
    return result


def analyze_yandex_file(url: str) -> dict:
    try:
        print("\n  🔐 Подключение к Яндекс.Диску...")
        client = get_client()
        print("  ✅ Авторизация успешна")

        print("  📥 Получение метаданных...")
        metadata = get_file_metadata(client, url)

        if "Ошибка" in metadata:
            return metadata

        mime_type = metadata.get("Тип файла (MIME)", "")
        filename  = metadata.get("Название", "unknown")

        SCANNABLE = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/pdf",
            "application/msword",
            "image/jpeg", "image/png", "image/tiff",
        ]

        if mime_type in SCANNABLE:
            print(f"\n  🔍 Сканирование: {filename}")
            scan_result = scan_yandex_file(client, url, mime_type, filename)
            metadata["Сканирование файла"] = scan_result
        else:
            print(f"\n  ⚠️  MIME тип '{mime_type}' не поддерживается для сканирования")

        log_action(f"Анализ Яндекс.Диска завершён: {filename}")
        return metadata

    except Exception as e:
        log_action(f"Критическая ошибка analyze_yandex_file: {e}")
        return {"Ошибка": str(e)}


def analyze_yandex_folder(url: str) -> list:
    try:
        print("\n  🔐 Подключение к Яндекс.Диску...")
        client = get_client()

        print(f"  📁 Сканирование папки...")
        files = list_folder_files(client, url)

        if not files:
            print("  ❌ Поддерживаемых файлов не найдено")
            return []

        print(f"\n  Найдено файлов: {len(files)}")
        results = []

        for i, file in enumerate(files, 1):
            print(f"\n  [{i}/{len(files)}] {file['name']}")
            metadata = {
                "Название":         file["name"],
                "Тип файла (MIME)": file["mime_type"],
                "Размер":           f"{file['size']} байт",
                "MD5 (Яндекс)":     file["md5"],
                "Дата изменения":   file["modified"],
                "Публичная ссылка": file["public_url"],
            }
            scan_result = scan_yandex_file(
                client, file["public_url"],
                file["mime_type"], file["name"]
            )
            metadata["Сканирование файла"] = scan_result
            results.append(metadata)

        return results

    except Exception as e:
        log_action(f"Ошибка analyze_yandex_folder: {e}")
        return [{"Ошибка": str(e)}]