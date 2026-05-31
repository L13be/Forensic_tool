import os
import io
import zipfile
from modules.logger import log_action
from modules.image_extractor import extract_full_exif

try:
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

DOWNLOADABLE_MIME = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf":    "pdf",
    "application/msword": "doc",
    "image/jpeg":         "jpg",
    "image/png":          "png",
    "image/gif":          "gif",
    "image/tiff":         "tiff",
    "video/mp4":          "mp4",
    "video/quicktime":    "mov",
}

EXPORT_MIME = {
    "application/vnd.google-apps.document":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.spreadsheet":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.presentation":
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def download_file(service, file_id, mime_type):
    try:
        if mime_type in EXPORT_MIME:
            request = service.files().export_media(fileId=file_id, mimeType=EXPORT_MIME[mime_type])
        else:
            request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        dl  = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()
    except Exception as e:
        log_action(f"Ошибка скачивания {file_id}: {e}")
        return None


def scan_docx_images(file_bytes):
    images = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            media = [f for f in z.namelist()
                     if f.startswith("word/media/")
                     and f.lower().endswith((".jpg",".jpeg",".png",".gif",".tiff",".bmp"))]
            print(f"  🖼️  Найдено изображений в DOCX: {len(media)}")
            for path in media:
                name = os.path.basename(path)
                data = z.read(path)
                print(f"     → Анализ EXIF: {name}")
                exif = extract_full_exif(data, name)
                exif["Источник"] = f"Вложение DOCX: {path}"
                images.append(exif)
    except Exception as e:
        log_action(f"Ошибка сканирования DOCX: {e}")
        images.append({"Ошибка": str(e)})
    return images


def scan_pdf_images(file_bytes):
    images = []
    try:
        import fitz
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        total = 0
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            img_list = page.get_images(full=True)
            total += len(img_list)
            for idx, img in enumerate(img_list):
                base_image = pdf.extract_image(img[0])
                name = f"page{page_num+1}_img{idx+1}.{base_image['ext']}"
                print(f"     → Анализ EXIF: {name}")
                exif = extract_full_exif(base_image["image"], name)
                exif["Источник"] = f"PDF стр.{page_num+1}, изобр.{idx+1}"
                images.append(exif)
        print(f"  🖼️  Найдено изображений в PDF: {total}")
        pdf.close()
    except ImportError:
        images.append({"Примечание": "Установите: pip install PyMuPDF"})
    except Exception as e:
        log_action(f"Ошибка PDF: {e}")
    return images


def scan_cloud_file(service, file_id, mime_type, filename):
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
    }

    print(f"\n  📥 Скачивание: {filename}")
    file_bytes = download_file(service, file_id, mime_type)
    if not file_bytes:
        result["Статус скачивания"] = "❌ Ошибка скачивания"
        return result

    size_kb = round(len(file_bytes)/1024, 2)
    result["Статус скачивания"] = f"✅ Скачан ({size_kb} КБ)"
    print(f"  ✅ Скачан: {size_kb} КБ")

    eff_mime = EXPORT_MIME.get(mime_type, mime_type)
    if "wordprocessingml" in eff_mime or mime_type == "application/msword":
        images = scan_docx_images(file_bytes)

        try:
            import tempfile
            from modules.hidden_text import extract_hidden_text
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                hidden = extract_hidden_text(tmp_path)
            finally:
                os.unlink(tmp_path)
            result["Скрытый текст"] = hidden
            if hidden.get("Скрытых фрагментов", 0) > 0:
                print(f"  👁️  Скрытых фрагментов: {hidden['Скрытых фрагментов']}")
                for frag in hidden["Скрытый текст"]:
                    print(f"     📌 Параграф №{frag['Параграф №']}: {frag['Скрытый текст'][:100]}")
                for anom in hidden["Аномалии"]:
                    result["Все аномалии"].append(f"[Скрытый текст] {anom}")
            else:
                print(f"  👁️  Скрытый текст: не обнаружен")
        except Exception as e:
            log_action(f"Ошибка анализа скрытого текста: {e}")

    elif mime_type == "application/pdf":
        images = scan_pdf_images(file_bytes)
    elif mime_type.startswith("image/"):
        images = [extract_full_exif(file_bytes, filename)]
    else:
        images = []
        result["Примечание"] = "Тип файла не поддерживает сканирование"

    result["Изображений найдено"] = len(images)
    result["Изображения"]         = images

    for img in images:
        gps = img.get("GPS",{})
        if gps.get("Координаты"):
            result["GPS обнаружен"] = True
            result["Координаты"].append({
                "Файл":        img["Файл"],
                "Координаты":  gps["Координаты"],
                "Google Maps": gps.get("Google Maps",""),
                "Yandex Maps": gps.get("Yandex Maps",""),
                "Высота":      gps.get("Высота над уровнем моря","—"),
                "Скорость":    gps.get("Скорость","—"),
                "Время GPS":   gps.get("Время GPS (UTC)","—"),
            })
            print(f"  📍 GPS: {gps['Координаты']}")
        device = img.get("Камера",{}).get("Устройство","")
        if device and device not in result["Устройства"]:
            result["Устройства"].append(device)
        for t in img.get("Следы",   []): result["Все следы"].append(f"[{img['Файл']}] {t}")
        for a in img.get("Аномалии",[]): result["Все аномалии"].append(f"[{img['Файл']}] {a}")

    print(f"\n  📊 Изображений  : {len(images)}")
    print(f"  📍 С GPS        : {len(result['Координаты'])}")
    print(f"  🔵 Следов       : {len(result['Все следы'])}")
    print(f"  ⚠️  Аномалий    : {len(result['Все аномалии'])}")
    if result["Устройства"]:
        print(f"  📱 Устройства   : {', '.join(result['Устройства'])}")

    log_action(f"Сканирование: {filename} | Следов: {len(result['Все следы'])} | Аномалий: {len(result['Все аномалии'])}")
    return result