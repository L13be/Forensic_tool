import os
import io
import zipfile
from modules.logger import log_action

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import exifread as _exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False

REPORTS_DIR = "reports/extracted_images"


def _convert_gps_coord(coord_tuple, ref):
    try:
        d = float(coord_tuple[0])
        m = float(coord_tuple[1])
        s = float(coord_tuple[2])
        dec = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            dec = -dec
        return dec
    except Exception:
        return None


def _parse_gps_block(gps_raw):
    gps = {}
    if not gps_raw: return gps
    decoded = {GPSTAGS.get(k, f"GPS_{k}"): v for k, v in gps_raw.items()}

    lat = _convert_gps_coord(decoded.get("GPSLatitude"), decoded.get("GPSLatitudeRef","N"))
    lon = _convert_gps_coord(decoded.get("GPSLongitude"), decoded.get("GPSLongitudeRef","E"))
    if lat and lon:
        gps["Широта"]      = round(lat, 8)
        gps["Долгота"]     = round(lon, 8)
        gps["Координаты"]  = f"{round(lat,6)}, {round(lon,6)}"
        gps["Google Maps"] = f"https://www.google.com/maps?q={round(lat,6)},{round(lon,6)}"
        gps["Yandex Maps"] = f"https://yandex.ru/maps/?pt={round(lon,6)},{round(lat,6)}&z=16&l=map"

    alt = decoded.get("GPSAltitude")
    if alt:
        av = float(alt)
        if decoded.get("GPSAltitudeRef",0) == 1: av = -av
        gps["Высота над уровнем моря"] = f"{round(av,1)} м"

    speed = decoded.get("GPSSpeed")
    if speed and float(speed) > 0:
        units = {"K":"км/ч","M":"миль/ч","N":"узлов"}
        gps["Скорость"] = f"{round(float(speed),1)} {units.get(decoded.get('GPSSpeedRef','K'),'км/ч')}"
        gps["Снято в движении"] = "Да"

    direction = decoded.get("GPSImgDirection")
    if direction:
        gps["Направление съёмки"] = f"{round(float(direction),1)}° ({decoded.get('GPSImgDirectionRef','')})"

    gps_time = decoded.get("GPSTimeStamp")
    gps_date = decoded.get("GPSDateStamp", "")
    if gps_time and gps_date:
        try:
            h = int(float(gps_time[0]))
            m = int(float(gps_time[1]))
            s = int(float(gps_time[2]))
            gps["Время GPS (UTC)"] = f"{gps_date} {h:02d}:{m:02d}:{s:02d} UTC"
        except Exception:
            pass
    return gps


def _extract_makernotes(image_bytes: bytes) -> dict:
    """
    Извлекает MakerNotes и расширенные теги через exifread (IFD4).

    MakerNotes — проприетарный блок EXIF, который каждый производитель
    (Canon, Nikon, Sony, Apple, Samsung…) заполняет по собственному формату.
    Pillow не парсит этот блок; exifread умеет читать большинство марок.

    Возвращает:
        {
          "MakerNotes":                  {tag: value, ...},   # проприетарные теги
          "Серийный номер (MakerNotes)": str,                  # из блока MakerNotes
          "Владелец камеры":             str,                  # owner name если прописан
          "Внутренний номер кадра":      str,                  # file number камеры
          "Всего тегов":                 int,                  # сколько тегов распознал exifread
        }
    """
    out = {
        "MakerNotes":                  {},
        "Серийный номер (MakerNotes)": "",
        "Владелец камеры":             "",
        "Внутренний номер кадра":      "",
        "Всего тегов":                 0,
    }
    if not EXIFREAD_AVAILABLE:
        out["Статус"] = "exifread не установлен — pip install exifread"
        return out

    try:
        f = io.BytesIO(image_bytes)
        tags = _exifread.process_file(f, details=True, strict=False)
        out["Всего тегов"] = len(tags)

        for tag_name, value in tags.items():
            str_val = str(value).strip()
            # Пропускаем пустые, нулевые и сырые байтовые массивы "[N, N, N, ...]"
            if not str_val or str_val in ("0", "[0]", "[]", "None"):
                continue
            # Пропускаем нечитаемые сырые байты — длинные числовые массивы
            if str_val.startswith("[") and "," in str_val and any(c.isdigit() for c in str_val[:6]):
                # Допускаем только короткие числовые значения (GPS, рациональные числа)
                if len(str_val) > 40:
                    continue
            # Пропускаем теги с hex-именами вида "Tag 0xXXXX" — нераспознанные блоки
            if "Tag 0x" in tag_name:
                continue

            lower = tag_name.lower()

            # ── MakerNotes ────────────────────────────────────────────
            if "makernote" in lower:
                # Убираем префикс "MakerNote " для чистого отображения
                parts = tag_name.split(" ", 1)
                clean = parts[1] if len(parts) > 1 else tag_name
                # Пропускаем сам блок MakerNote (сырые байты всего блока)
                if clean.lower() in ("makernote", "makernoteversion"):
                    continue
                out["MakerNotes"][clean] = str_val

                # Серийный номер из MakerNotes (Canon, Nikon, Sony…)
                if any(s in lower for s in ("serialnumber", "serial number",
                                            "cameraserial", "camera serial",
                                            "bodyserial", "body serial")):
                    out["Серийный номер (MakerNotes)"] = str_val

                # Владелец камеры (Canon CameraOwnerName, Nikon Owner…)
                if any(s in lower for s in ("ownername", "owner name",
                                            "cameraowner", "camera owner")):
                    out["Владелец камеры"] = str_val

                # Внутренний номер кадра
                if any(s in lower for s in ("filenumber", "file number",
                                            "imagenumber", "image number",
                                            "shaternumber", "shuttercount")):
                    out["Внутренний номер кадра"] = str_val

    except Exception as e:
        out["Ошибка"] = str(e)
        log_action(f"exifread ошибка: {e}")

    return out


def extract_full_exif(image_bytes, filename):
    """
    Извлекает EXIF. Разделяет на:
      - Следы (GPS, устройство, часовой пояс) — полезные данные для эксперта
      - Аномалии (очистка, редакторы, несоответствия) — подозрительные факты
    """
    result = {
        "Файл":                    filename,
        "Следы":                   [],
        "Аномалии":                [],
        "Основное":                {},
        "Камера":                  {},
        "Параметры съёмки":        {},
        "GPS":                     {},
        "Временные метки":         {},
        "Программное обеспечение": {},
        "MakerNotes":              {},   # проприетарные теги (Canon/Nikon/Sony…)
        "Сырой EXIF":              {},
    }
    if not PIL_AVAILABLE:
        result["Ошибка"] = "Pillow не установлен — pip install Pillow"
        return result
    try:
        img = Image.open(io.BytesIO(image_bytes))
        result["Основное"] = {
            "Разрешение":      f"{img.width} x {img.height} px",
            "Формат":          img.format or "—",
            "Цветовая модель": img.mode,
            "Размер файла":    f"{round(len(image_bytes)/1024,2)} КБ",
        }
        # getexif() — публичный API (Pillow 6.0+), работает для JPEG и TIFF
        exif_obj = img.getexif()
        raw_exif = dict(exif_obj) if exif_obj else None
        if not raw_exif:
            if img.format == "PNG":
                result["Примечание"] = "PNG — EXIF не поддерживается стандартом"
            else:
                result["Аномалии"].append("EXIF отсутствует в JPEG — метаданные могли быть намеренно очищены")
                result["Аномалии"].append("Word автоматически удаляет EXIF при вставке — запрашивайте оригинальные файлы")
            return result

        all_tags = {TAGS.get(k, f"Tag_{k}"): v for k, v in raw_exif.items()}
        result["Сырой EXIF"] = {k: str(v) for k,v in all_tags.items()}

        camera = {}
        make  = all_tags.get("Make","")
        model = all_tags.get("Model","")
        if make:  camera["Производитель"] = str(make).strip()
        if model: camera["Модель камеры"] = str(model).strip()
        if make or model:
            camera["Устройство"] = f"{str(make).strip()} {str(model).strip()}".strip()
            result["Следы"].append(f"📱 Устройство: {camera['Устройство']}")
        lens_model = all_tags.get("LensModel","")
        if lens_model:
            camera["Объектив"] = f"{all_tags.get('LensMake','')} {lens_model}".strip()
            result["Следы"].append(f"🔭 Объектив: {camera['Объектив']}")
        serial = all_tags.get("BodySerialNumber","") or all_tags.get("CameraSerialNumber","")
        if serial:
            camera["Серийный номер камеры"] = str(serial)
            result["Следы"].append(f"🔑 Серийный номер: {serial} — уникальный ID устройства")
        result["Камера"] = camera

        shoot = {}
        if "ExposureTime"    in all_tags: shoot["Выдержка"]            = str(all_tags["ExposureTime"]) + " с"
        if "FNumber"         in all_tags: shoot["Диафрагма"]           = f"f/{float(all_tags['FNumber'])}"
        if "ISOSpeedRatings" in all_tags: shoot["ISO"]                 = str(all_tags["ISOSpeedRatings"])
        if "FocalLength"     in all_tags: shoot["Фокусное расстояние"] = f"{float(all_tags['FocalLength'])} мм"
        if "Flash"           in all_tags: shoot["Вспышка"] = "Сработала" if int(all_tags["Flash"]) & 1 else "Не использовалась"
        result["Параметры съёмки"] = shoot

        times = {}
        date_orig = all_tags.get("DateTimeOriginal","")
        date_dig  = all_tags.get("DateTimeDigitized","")
        date_mod  = all_tags.get("DateTime","")
        if date_orig:
            times["Дата и время съёмки"]  = str(date_orig)
            result["Следы"].append(f"📅 Дата съёмки: {date_orig}")
        if date_dig:  times["Дата оцифровки"]       = str(date_dig)
        if date_mod:  times["Дата изменения файла"] = str(date_mod)
        if date_orig and date_mod and str(date_orig) != str(date_mod):
            result["Аномалии"].append(
                f"Дата съёмки ({date_orig}) не совпадает с датой изменения ({date_mod}) — файл мог быть изменён после съёмки"
            )
        offset = all_tags.get("OffsetTimeOriginal","")
        if offset:
            times["Часовой пояс съёмки"] = str(offset)
            result["Следы"].append(f"🕐 Часовой пояс: {offset} — позволяет установить регион съёмки")
        result["Временные метки"] = times

        soft = {}
        software = all_tags.get("Software","")
        if software:
            soft["ПО обработки"] = str(software).strip()
            result["Следы"].append(f"💻 ПО создания: {software.strip()}")
            for ed in ["photoshop","lightroom","gimp","snapseed","instagram","facetune","meitu","vsco"]:
                if ed in str(software).lower():
                    result["Аномалии"].append(f"Обнаружен редактор: {software.strip()} — фото могло быть изменено")
                    break
        artist = all_tags.get("Artist","")
        if artist:
            soft["Автор (Artist)"] = str(artist)
            result["Следы"].append(f"👤 Автор (Artist): {artist}")
        copyright_ = all_tags.get("Copyright","")
        if copyright_:
            soft["Авторские права"] = str(copyright_)
            result["Следы"].append(f"©️ Авторские права: {copyright_}")
        user_comment = all_tags.get("UserComment", b"")
        if user_comment:
            try:
                comment = user_comment.decode("utf-8", errors="ignore").strip()
                if comment:
                    soft["Комментарий"] = comment
                    result["Следы"].append(f"💬 Скрытый комментарий: «{comment}»")
            except Exception:
                pass
        result["Программное обеспечение"] = soft

        # ── GPS — используем get_ifd(0x8825), а не all_tags["GPSInfo"] ──
        # all_tags["GPSInfo"] возвращает int (смещение в файле), а не dict.
        # Правильный API: exif_obj.get_ifd(tag_id) — даёт настоящий словарь GPS IFD.
        try:
            gps_ifd = exif_obj.get_ifd(0x8825)   # 0x8825 = GPS Info IFD
            if gps_ifd:
                gps_data = _parse_gps_block(gps_ifd)
                result["GPS"] = gps_data
                if gps_data.get("Координаты"):
                    result["Следы"].append(f"📍 GPS координаты: {gps_data['Координаты']}")
                    result["Следы"].append(f"🗺️ Google Maps: {gps_data['Google Maps']}")
                    if gps_data.get("Высота над уровнем моря"):
                        result["Следы"].append(f"⛰️ Высота: {gps_data['Высота над уровнем моря']}")
                    if gps_data.get("Скорость"):
                        result["Следы"].append(f"🚗 Скорость: {gps_data['Скорость']} — снято в движении")
                    if gps_data.get("Время GPS (UTC)"):
                        result["Следы"].append(f"🕐 Время GPS: {gps_data['Время GPS (UTC)']}")
            else:
                result["GPS"] = {"Статус": "GPS не обнаружен"}
        except Exception as gps_err:
            result["GPS"] = {"Статус": f"Ошибка разбора GPS: {gps_err}"}
            log_action(f"GPS ошибка {filename}: {gps_err}")

        # ── ImageUniqueID ─────────────────────────────────────────────
        uid = all_tags.get("ImageUniqueID", "")
        if uid:
            result["Основное"]["Уникальный ID"] = str(uid)
            result["Следы"].append(f"🔐 Уникальный ID: {uid}")

        # ── MakerNotes: второй слой анализа через exifread ──────────
        try:
            mn = _extract_makernotes(image_bytes)
            result["MakerNotes"] = mn.get("MakerNotes", {})

            # Серийный номер из MakerNotes — если Pillow его не нашёл
            if not result["Камера"].get("Серийный номер камеры") and mn.get("Серийный номер (MakerNotes)"):
                sn = mn["Серийный номер (MakerNotes)"]
                result["Камера"]["Серийный номер камеры"] = f"{sn} ★MakerNotes"
                result["Следы"].append(f"🔑 Серийный номер (MakerNotes): {sn}")

            # Владелец камеры — уникальный след, редко встречается
            if mn.get("Владелец камеры"):
                owner = mn["Владелец камеры"]
                result["Программное обеспечение"]["Владелец камеры"] = owner
                result["Следы"].append(f"👤 Владелец камеры (MakerNotes): {owner}")
                result["Аномалии"].append(
                    f"Обнаружено имя владельца камеры: «{owner}» — прямая идентификация устройства"
                )

            # Внутренний номер кадра — показывает сколько снимков сделано этой камерой
            if mn.get("Внутренний номер кадра"):
                fn = mn["Внутренний номер кадра"]
                result["Камера"]["Номер кадра (всего по камере)"] = fn
                result["Следы"].append(
                    f"📷 Счётчик кадров камеры: {fn} — помогает установить интенсивность использования"
                )

            if mn.get("Всего тегов", 0) > 0:
                result["Основное"]["Тегов EXIF (exifread)"] = str(mn["Всего тегов"])

        except Exception as mn_err:
            log_action(f"MakerNotes ошибка {filename}: {mn_err}")

    except Exception as e:
        result["Ошибка"] = str(e)
        log_action(f"Ошибка EXIF {filename}: {e}")

    log_action(f"EXIF: {filename} | Следов: {len(result['Следы'])} | Аномалий: {len(result['Аномалии'])}")
    return result


def extract_images(filepath):
    """
    Извлекает все изображения из локального DOCX файла.
    Использует полный EXIF анализ с разделением на Следы и Аномалии.
    """
    images = []
    os.makedirs(REPORTS_DIR, exist_ok=True)
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            media = [f for f in z.namelist()
                     if f.startswith("word/media/")
                     and f.lower().endswith((".jpg",".jpeg",".png",".gif",".tiff",".bmp"))]
            log_action(f"Изображений в {os.path.basename(filepath)}: {len(media)}")
            for path in media:
                name = os.path.basename(path)
                data = z.read(path)
                save_path = os.path.join(REPORTS_DIR, name)
                with open(save_path, "wb") as f:
                    f.write(data)
                exif = extract_full_exif(data, name)
                exif["Источник"]      = f"Локальный DOCX: {path}"
                exif["Сохранён в"]    = save_path
                exif["Размер (байт)"] = len(data)
                images.append(exif)
                if exif["GPS"].get("Координаты"):
                    log_action(f"GPS в {name}: {exif['GPS']['Координаты']}")
    except Exception as e:
        log_action(f"Ошибка извлечения из {filepath}: {e}")
    return images