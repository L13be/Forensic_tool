import os
import fitz  # PyMuPDF
import zipfile
from pptx import Presentation
from colorama import init, Fore, Style
from modules.virus_scanner         import scan_file
from modules.extractor             import extract_metadata
from modules.anomaly_detector      import detect_anomalies
from modules.reporter              import generate_html_report
from modules.exporter              import export_to_csv
from modules.logger                import log_action
from modules.xml_analyzer          import analyze_xml_structure
from modules.url_extractor         import extract_urls
from modules.image_extractor       import extract_images, extract_full_exif
from modules.lang_detector         import detect_language
from modules.hidden_text           import extract_hidden_text
from modules.hasher                import compute_hashes
from modules.cloud.google_drive    import (
    analyze_google_doc, authenticate, extract_file_id,
    is_folder, analyze_google_folder,
)

init(autoreset=True)


def print_banner():
    print(Fore.CYAN + """
╔══════════════════════════════════════════════════════════╗
║         Forensic File Metadata Analyzer v2.0             ║
║   Инструмент компьютерной экспертизы, форензики, OSINT   ║
╚══════════════════════════════════════════════════════════╝
    """ + Style.RESET_ALL)


def print_section(title: str):
    print(Fore.CYAN + f"\n  ── {title} " + "─" * (45 - len(title)))

def _parse_pdf_date(raw: str) -> str:
    """
    Конвертирует дату PDF формата D:YYYYMMDDHHmmSSOHH'mm'
    в читаемый вид: DD.MM.YYYY HH:MM:SS
    Примеры входных данных:
      D:20210803161707Z00'00'
      D:20210803161707+03'00'
      D:20210803161707
    """
    if not raw or raw == "—":
        return "—"
    try:
        # Убираем префикс D:
        s = raw.strip()
        if s.startswith("D:"):
            s = s[2:]

        # Берём только первые 14 символов (YYYYMMDDHHmmSS)
        s = s[:14]

        if len(s) < 8:
            return raw  # не можем распарсить — возвращаем как есть

        year  = s[0:4]
        month = s[4:6]  if len(s) >= 6  else "01"
        day   = s[6:8]  if len(s) >= 8  else "01"
        hour  = s[8:10] if len(s) >= 10 else "00"
        minute= s[10:12]if len(s) >= 12 else "00"
        sec   = s[12:14]if len(s) >= 14 else "00"

        return f"{day}.{month}.{year} {hour}:{minute}:{sec}"

    except Exception:
        return raw  # если что-то пошло не так — оригинал


def analyze_file(filepath: str) -> dict:
    """Полный форензик-анализ одного DOCX файла"""

    fname = os.path.basename(filepath)
    print(Fore.YELLOW + f"\n{'='*60}")
    print(Fore.YELLOW + f"  📄 Файл: {fname}")
    print(Fore.YELLOW + f"{'='*60}")

    full_result = {"filepath": filepath}

    # 1. Метаданные
    print_section("МЕТАДАННЫЕ")
    metadata = extract_metadata(filepath)
    for key, value in metadata.items():
        print(f"     {Fore.WHITE}{key:25}: {Fore.GREEN}{value}")
    full_result["metadata"] = metadata

    # 2. Детектор аномалий
    print_section("ДЕТЕКТОР АНОМАЛИЙ")
    anomalies = detect_anomalies(metadata)
    if anomalies:
        for a in anomalies:
            print(Fore.RED + f"     {a}")
    else:
        print(Fore.GREEN + "     ✅ Аномалий не обнаружено")
    full_result["anomalies"] = anomalies

    # 3. XML-структура
    print_section("XML СТРУКТУРА")
    xml_info = analyze_xml_structure(filepath)
    print(f"     {Fore.WHITE}Файлов внутри DOCX : {Fore.GREEN}{len(xml_info['Все файлы внутри DOCX'])}")
    print(f"     {Fore.WHITE}Медиафайлов        : {Fore.GREEN}{len(xml_info['Встроенные медиафайлы'])}")
    macro_val   = xml_info['Наличие макросов (vbaProject)']
    macro_color = Fore.RED if "ДА" in macro_val else Fore.GREEN
    print(f"     {Fore.WHITE}Макросы            : {macro_color}{macro_val}")
    if xml_info["Нестандартные компоненты"]:
        print(Fore.YELLOW + f"     ⚠️  Нестандартные компоненты: {xml_info['Нестандартные компоненты']}")
    full_result["xml"] = xml_info

    # 4. URL и гиперссылки
    print_section("URL И ГИПЕРССЫЛКИ (OSINT)")
    url_info = extract_urls(filepath)
    print(f"     {Fore.WHITE}Гиперссылок найдено: {Fore.GREEN}{len(url_info['Гиперссылки из XML'])}")
    for url in url_info["Гиперссылки из XML"]:
        print(f"       {Fore.CYAN}🔗 {url}")
    if url_info["Подозрительные URL"]:
        for s in url_info["Подозрительные URL"]:
            print(Fore.RED + f"       {s}")
    else:
        print(Fore.GREEN + "     ✅ Подозрительных URL не обнаружено")
    domains = ', '.join(url_info['Уникальные домены']) or 'Нет'
    print(f"     {Fore.WHITE}Уникальных доменов : {Fore.GREEN}{domains}")
    full_result["urls"] = url_info

    # 5. Скрытый текст (w:vanish)
    print_section("СКРЫТЫЙ ТЕКСТ (w:vanish)")
    hidden = extract_hidden_text(filepath)
    if hidden["Скрытых фрагментов"] > 0:
        print(Fore.RED + f"     🔴 Найдено фрагментов: {hidden['Скрытых фрагментов']}")
        for fragment in hidden["Скрытый текст"]:
            print(Fore.RED +    f"     📌 Параграф №{fragment['Параграф №']} — {fragment['Тип сокрытия']}")
            print(Fore.YELLOW + f"        Текст   : {fragment['Скрытый текст'][:200]}")
            if fragment["Контекст"]:
                print(Fore.WHITE + f"        Контекст: {fragment['Контекст']}")
        for anom in hidden["Аномалии"]:
            print(Fore.RED + f"     {anom}")
        # Добавляем в общий список аномалий
        full_result["anomalies"] += hidden["Аномалии"]
    else:
        print(Fore.GREEN + "     ✅ Скрытый текст не обнаружен")
    full_result["hidden"] = hidden

    # 6. Изображения и EXIF
    print_section("ИЗОБРАЖЕНИЯ И EXIF")
    images = extract_images(filepath)
    if images:
        for img in images:
            print(f"     {Fore.WHITE}📷 {img.get('Файл')} "
                  f"| {img.get('Размер (байт)')} байт")

            camera = img.get("Камера", {})
            if camera.get("Устройство"):
                print(f"        {Fore.YELLOW}📱 {camera['Устройство']}")
            if camera.get("Серийный номер камеры"):
                print(f"        {Fore.RED}🔑 Серийный №: {camera['Серийный номер камеры']}")

            times = img.get("Временные метки", {})
            if times.get("Дата и время съёмки"):
                print(f"        {Fore.WHITE}📅 {times['Дата и время съёмки']}")

            soft = img.get("Программное обеспечение", {})
            if soft.get("ПО обработки"):
                print(f"        {Fore.YELLOW}🖼️  ПО: {soft['ПО обработки']}")

            gps = img.get("GPS", {})
            if gps.get("Координаты"):
                print(Fore.RED  + f"        📍 GPS: {gps['Координаты']}")
                print(Fore.CYAN + f"        🗺️  {gps['Google Maps']}")
                if gps.get("Высота над уровнем моря"):
                    print(f"        {Fore.GREEN}⛰️  {gps['Высота над уровнем моря']}")
                if gps.get("Скорость"):
                    print(Fore.YELLOW + f"        🚗 {gps['Скорость']}")

            img_anomalies = img.get("Аномалии", [])
            if img_anomalies:
                print(Fore.RED + f"        ⚠️  Аномалий: {len(img_anomalies)}")
                for a in img_anomalies:
                    print(Fore.RED + f"           → {a}")
    else:
        print(Fore.WHITE + "     Изображений не найдено")
    full_result["images"] = images

    # 7. Вирусное сканирование
    print_section("ВИРУСНОЕ СКАНИРОВАНИЕ")
    scan = scan_file(filepath)
    print(f"     {Fore.WHITE}Риск: {scan['Риск']}")
    for finding in scan["Находки"]:
        color = Fore.RED if "🔴" in finding else Fore.YELLOW
        print(color + f"     {finding}")
    if not scan["Находки"]:
        print(Fore.GREEN + "     ✅ Угроз не обнаружено")
    full_result["scan"] = scan

    return full_result

def analyze_other_file(filepath: str, ext: str) -> dict:
    """Анализ не-DOCX файлов: PDF, PPTX, изображения"""

    fname = os.path.basename(filepath)
    print(Fore.YELLOW + f"\n{'='*60}")
    print(Fore.YELLOW + f"  📄 Файл: {fname}")
    print(Fore.YELLOW + f"{'='*60}")

    hashes   = compute_hashes(filepath)
    metadata = {
        "Файл":        fname,
        "Полный путь": filepath,
        "Размер":      f"{round(os.path.getsize(filepath)/1024, 2)} КБ",
        "MD5":         hashes.get("MD5", "—"),
        "SHA256":      hashes.get("SHA256", "—"),
    }

    anomalies = []
    images    = []

    # ── ИЗОБРАЖЕНИЯ (JPG, PNG и т.д.) ────────────────────
    if ext in (".jpg", ".jpeg", ".png", ".tiff", ".bmp"):
        print_section("EXIF АНАЛИЗ ИЗОБРАЖЕНИЯ")
        with open(filepath, "rb") as f:
            image_bytes = f.read()

        exif = extract_full_exif(image_bytes, fname)
        images.append(exif)

        camera = exif.get("Камера", {})
        times  = exif.get("Временные метки", {})
        gps    = exif.get("GPS", {})
        soft   = exif.get("Программное обеспечение", {})

        if camera.get("Устройство"):
            print(f"     {Fore.YELLOW}📱 Устройство : {camera['Устройство']}")
            metadata["Устройство"] = camera["Устройство"]
        if times.get("Дата и время съёмки"):
            print(f"     {Fore.WHITE}📅 Дата съёмки: {times['Дата и время съёмки']}")
            metadata["Дата создания"] = times["Дата и время съёмки"]
        if soft.get("ПО обработки"):
            print(f"     {Fore.YELLOW}🖼️  ПО         : {soft['ПО обработки']}")
        if gps.get("Координаты"):
            print(Fore.RED + f"     📍 GPS        : {gps['Координаты']}")
            print(Fore.CYAN + f"     🗺️  Maps       : {gps['Google Maps']}")
            metadata["GPS"] = gps["Координаты"]
            anomalies.append(f"📍 GPS обнаружен: {gps['Координаты']}")

        anomalies.extend(exif.get("Аномалии", []))

    # ── PDF ───────────────────────────────────────────────
    elif ext == ".pdf":
        print_section("АНАЛИЗ PDF")
        try:
            with open(filepath, "rb") as f:
                pdf_bytes = f.read()

            pdf  = fitz.open(stream=pdf_bytes, filetype="pdf")
            meta = pdf.metadata

            metadata["Автор"]          = meta.get("author",        "—")
            metadata["Тема"]           = meta.get("subject",       "—")
            metadata["Заголовок"]      = meta.get("title",         "—")
            metadata["Создатель"]      = meta.get("creator",       "—")
            metadata["Продюсер"]       = meta.get("producer",      "—")
            metadata["Дата создания"] = _parse_pdf_date(meta.get("creationDate", ""))
            metadata["Дата изменения"] = _parse_pdf_date(meta.get("modDate", ""))
            metadata["Страниц"]        = len(pdf)

            for k, v in metadata.items():
                if k not in ("Файл", "Полный путь", "Размер", "MD5", "SHA256"):
                    print(f"     {Fore.WHITE}{k:20}: {Fore.GREEN}{v}")

            print_section("ИЗОБРАЖЕНИЯ В PDF")
            exif_fn = extract_full_exif
            img_count = 0
            for page_num in range(len(pdf)):
                page     = pdf[page_num]
                img_list = page.get_images(full=True)
                for img_index, img in enumerate(img_list):
                    xref       = img[0]
                    base_image = pdf.extract_image(xref)
                    img_bytes  = base_image["image"]
                    ext_img    = base_image["ext"]
                    img_name   = f"page{page_num+1}_img{img_index+1}.{ext_img}"
                    exif       = exif_fn(img_bytes, img_name)
                    exif["Источник"] = f"PDF стр.{page_num+1}"
                    images.append(exif)
                    img_count += 1
                    if exif.get("GPS", {}).get("Координаты"):
                        anomalies.append(
                            f"📍 GPS в {img_name}: {exif['GPS']['Координаты']}"
                        )

            print(f"     {Fore.WHITE}Изображений найдено: {Fore.GREEN}{img_count}")
            pdf.close()

        except ImportError:
            print(Fore.RED + "  ⚠️  PyMuPDF не установлен — pip install PyMuPDF")
        except Exception as e:
            print(Fore.RED + f"  ❌ Ошибка PDF: {e}")

    # ── PPTX ─────────────────────────────────────────────
    elif ext == ".pptx":
        print_section("АНАЛИЗ PPTX")
        try:
            import io

            prs  = Presentation(filepath)
            core = prs.core_properties

            metadata["Автор"]              = core.author            or "—"
            metadata["Последний редактор"] = core.last_modified_by  or "—"
            metadata["Дата создания"]      = str(core.created)      or "—"
            metadata["Дата изменения"]     = str(core.modified)     or "—"
            metadata["Заголовок"]          = core.title             or "—"
            metadata["Слайдов"]            = len(prs.slides)

            for k, v in metadata.items():
                if k not in ("Файл", "Полный путь", "Размер", "MD5", "SHA256"):
                    print(f"     {Fore.WHITE}{k:20}: {Fore.GREEN}{v}")

            print_section("ИЗОБРАЖЕНИЯ В PPTX")
            exif_fn = extract_full_exif
            img_count = 0
            with zipfile.ZipFile(filepath, "r") as z:
                media = [
                    f for f in z.namelist()
                    if f.startswith("ppt/media/")
                    and f.lower().endswith((".jpg", ".jpeg", ".png", ".tiff"))
                ]
                for media_path in media:
                    img_bytes = z.read(media_path)
                    img_name  = os.path.basename(media_path)
                    exif      = exif_fn(img_bytes, img_name)
                    exif["Источник"] = f"PPTX: {media_path}"
                    images.append(exif)
                    img_count += 1
                    if exif.get("GPS", {}).get("Координаты"):
                        anomalies.append(
                            f"📍 GPS в {img_name}: {exif['GPS']['Координаты']}"
                        )

            print(f"     {Fore.WHITE}Изображений найдено: {Fore.GREEN}{img_count}")

        except ImportError:
            print(Fore.RED + "  ⚠️  python-pptx не установлен — pip install python-pptx")
        except Exception as e:
            print(Fore.RED + f"  ❌ Ошибка PPTX: {e}")

    # ── АНОМАЛИИ ─────────────────────────────────────────
    # Этот блок всегда выполняется, независимо от типа файла
    print_section("АНОМАЛИИ")
    if anomalies:
        for a in anomalies:
            print(Fore.RED + f"     {a}")
    else:
        print(Fore.GREEN + "     ✅ Аномалий не обнаружено")

    # ── ВИРУСНОЕ СКАНИРОВАНИЕ ─────────────────────────────
    print_section("ВИРУСНОЕ СКАНИРОВАНИЕ")
    scan = scan_file(filepath)
    print(f"     {Fore.WHITE}Риск: {scan['Риск']}")
    for finding in scan["Находки"]:
        color = Fore.RED if "🔴" in finding else Fore.YELLOW
        print(color + f"     {finding}")
    if not scan["Находки"]:
        print(Fore.GREEN + "     ✅ Угроз не обнаружено")

    log_action(
        f"Анализ завершён: {fname} | Аномалий: {len(anomalies)} | "
        f"Изображений: {len(images)}"
    )

    return {
        "metadata":  metadata,
        "anomalies": anomalies,
        "images":    images,
        "scan":      scan,
    }


def analyze_folder(folder_path: str):
    """Пакетный анализ всех поддерживаемых файлов в папке"""

    # Поддерживаемые расширения
    SUPPORTED = {
        ".docx": "Word документ",
        ".pdf":  "PDF документ",
        ".pptx": "PowerPoint презентация",
        ".jpg":  "Фотография JPEG",
        ".jpeg": "Фотография JPEG",
        ".png":  "Изображение PNG",
        ".tiff": "Изображение TIFF",
        ".bmp":  "Изображение BMP",
    }

    all_files = []
    for f in os.listdir(folder_path):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED:
            all_files.append((os.path.join(folder_path, f), ext, SUPPORTED[ext]))

    if not all_files:
        print(Fore.RED + "  ❌ Поддерживаемые файлы не найдены.")
        print(Fore.WHITE + f"  Поддерживаются: {', '.join(SUPPORTED.keys())}")
        return

    print(Fore.YELLOW + f"\n  Найдено файлов: {len(all_files)}")
    for filepath, ext, ftype in all_files:
        print(f"     {Fore.CYAN}{ext:6} {Fore.WHITE}{os.path.basename(filepath)}")

    log_action(f"Начало пакетного анализа. Файлов: {len(all_files)}")

    all_results = []
    anomalies_map = {}
    local_images_map = {}
    local_scan_map = {}
    local_hidden_map = {}

    for filepath, ext, ftype in all_files:
        if ext == ".docx":
            result = analyze_file(filepath)
            all_results.append(result["metadata"])
            fname = result["metadata"]["Файл"]
            anomalies_map[fname] = result["anomalies"]
            local_images_map[fname] = result.get("images", [])
            local_scan_map[fname] = result.get("scan", {})
            local_hidden_map[fname] = result.get("hidden", {})
        else:
            result = analyze_other_file(filepath, ext)
            if result:
                all_results.append(result["metadata"])
                fname = result["metadata"]["Файл"]
                anomalies_map[fname] = result.get("anomalies", [])
                local_images_map[fname] = result.get("images", [])
                local_scan_map[fname] = result.get("scan", {})
                local_hidden_map[fname] = result.get("hidden", {})

    print(Fore.CYAN + f"\n{'='*60}")
    print(Fore.CYAN + "  📊 ГЕНЕРАЦИЯ ОТЧЁТОВ")
    generate_html_report(all_results, anomalies_map,
                         local_images_map=local_images_map,
                         local_scan_map=local_scan_map,
                         local_hidden_map=local_hidden_map)
    export_to_csv(all_results)
    log_action(f"Анализ завершён. Файлов обработано: {len(all_files)}")
    print(Fore.GREEN + f"\n  ✅ Готово! Отчёты сохранены в папке /reports")


def print_image_scan_results(scan_result: dict):
    """Красивый вывод результатов сканирования изображений"""

    print(Fore.CYAN + f"\n  ── СКАНИРОВАНИЕ ИЗОБРАЖЕНИЙ {'─'*30}")
    print(f"  {Fore.WHITE}Изображений найдено : {Fore.GREEN}{scan_result.get('Изображений найдено', 0)}")
    print(f"  {Fore.WHITE}GPS обнаружен       : {Fore.RED if scan_result.get('GPS обнаружен') else Fore.GREEN}{'Да ⚠️' if scan_result.get('GPS обнаружен') else 'Нет'}")

    # Устройства
    devices = scan_result.get("Устройства", [])
    if devices:
        print(f"  {Fore.WHITE}Устройства          : {Fore.YELLOW}{', '.join(devices)}")

    # GPS координаты
    for coord in scan_result.get("Координаты", []):
        print(Fore.RED + f"\n  📍 GPS в файле: {coord['Файл']}")
        print(f"     {Fore.WHITE}Координаты  : {Fore.GREEN}{coord['Координаты']}")
        print(f"     {Fore.WHITE}Google Maps : {Fore.CYAN}{coord['Google Maps']}")
        print(f"     {Fore.WHITE}Yandex Maps : {Fore.CYAN}{coord['Yandex Maps']}")
        if coord.get("Высота") != "—":
            print(f"     {Fore.WHITE}Высота      : {Fore.GREEN}{coord['Высота']}")
        if coord.get("Скорость") != "—":
            print(f"     {Fore.WHITE}Скорость    : {Fore.YELLOW}{coord['Скорость']}")
        if coord.get("Время GPS") != "—":
            print(f"     {Fore.WHITE}Время GPS   : {Fore.GREEN}{coord['Время GPS']}")

    # Детали по каждому изображению
    images = scan_result.get("Изображения", [])
    for img in images:
        if "Ошибка" in img or "Примечание" in img:
            continue

        print(Fore.CYAN + f"\n  🖼️  {img.get('Файл', '—')} "
              f"| {img.get('Источник', '—')}")

        # Основное
        osnovnoe = img.get("Основное", {})
        if osnovnoe:
            print(f"     {Fore.WHITE}Разрешение  : {Fore.GREEN}{osnovnoe.get('Разрешение', '—')}")
            print(f"     {Fore.WHITE}Размер      : {Fore.GREEN}{osnovnoe.get('Размер файла', '—')}")

        # Камера
        camera = img.get("Камера", {})
        if camera.get("Устройство"):
            print(f"     {Fore.WHITE}Устройство  : {Fore.YELLOW}{camera['Устройство']}")
        if camera.get("Серийный номер камеры"):
            print(f"     {Fore.WHITE}Серийный №  : {Fore.RED}{camera['Серийный номер камеры']}")
        if camera.get("Объектив"):
            print(f"     {Fore.WHITE}Объектив    : {Fore.GREEN}{camera['Объектив']}")

        # Временные метки
        times = img.get("Временные метки", {})
        if times.get("Дата и время съёмки"):
            print(f"     {Fore.WHITE}Дата съёмки : {Fore.GREEN}{times['Дата и время съёмки']}")
        if times.get("Часовой пояс съёмки"):
            print(f"     {Fore.WHITE}Часовой пояс: {Fore.YELLOW}{times['Часовой пояс съёмки']}")

        # ПО
        soft = img.get("Программное обеспечение", {})
        if soft.get("ПО обработки"):
            print(f"     {Fore.WHITE}ПО обработки: {Fore.YELLOW}{soft['ПО обработки']}")
        if soft.get("Автор (Artist)"):
            print(f"     {Fore.WHITE}Artist      : {Fore.RED}{soft['Автор (Artist)']}")

        # Аномалии изображения
        anomalies = img.get("Аномалии", [])
        if anomalies:
            print(Fore.RED + f"     ⚠️  Аномалии ({len(anomalies)}):")
            for a in anomalies:
                print(Fore.RED + f"        → {a}")

    # Общие аномалии
    all_anomalies = scan_result.get("Все аномалии", [])
    if all_anomalies:
        print(Fore.RED + f"\n  ⚠️  ИТОГО АНОМАЛИЙ: {len(all_anomalies)}")


def analyze_google_doc_mode():
    """Режим анализа Google Drive — файл или папка"""
    url = input(
        Fore.YELLOW + "  Вставьте ссылку на файл или папку Google Drive: "
        + Style.RESET_ALL
    ).strip()

    print("\n  🔐 Авторизация в Google Drive...")
    service   = authenticate()
    file_id   = extract_file_id(url)
    folder    = is_folder(service, file_id) if file_id else False

    if folder:
        print(Fore.CYAN + "  📁 Обнаружена папка — анализируем все файлы внутри...")
        results = analyze_google_folder(url)

        if not results:
            print(Fore.RED + "  ❌ Нет результатов.")
            return

        # Выводим краткую сводку
        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + f"  📊 СВОДКА: проанализировано {len(results)} файлов")
        print(Fore.CYAN + f"{'='*60}")

        for r in results:
            if "Ошибка" in r:
                print(Fore.RED + f"  ❌ {r['Ошибка']}")
                continue
            name    = r.get("Название", "—")
            owner   = r.get("Email владельца", "—")
            scan    = r.get("Сканирование файла", {})
            img_cnt = scan.get("Изображений найдено", 0) if scan else 0
            gps     = "📍 GPS!" if scan and scan.get("GPS обнаружен") else ""
            print(
                f"  {Fore.WHITE}📄 {name:30} "
                f"| {Fore.GREEN}{owner:25} "
                f"| {Fore.CYAN}🖼️  {img_cnt} изобр. "
                f"{Fore.RED}{gps}"
            )

        # Генерируем один общий отчёт
        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + "  📊 ГЕНЕРАЦИЯ ОТЧЁТА")
        generate_html_report([], {}, google_results=results)

    else:
        # Одиночный файл — старая логика
        try:
            result = analyze_google_doc(url)
        except Exception as e:
            print(Fore.RED + f"\n  ❌ Ошибка: {e}")
            return

        if not result or "Ошибка" in result:
            print(Fore.RED + f"  ❌ {result.get('Ошибка', 'Неизвестная ошибка')}")
            return

        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + "  📊 РЕЗУЛЬТАТЫ АНАЛИЗА GOOGLE DRIVE")
        print(Fore.CYAN + f"{'='*60}\n")

        for key, value in result.items():
            if key in ("Права доступа", "Сканирование файла"):
                continue
            print(f"  {Fore.WHITE}{key:35}: {Fore.GREEN}{value}")

        perms = result.get("Права доступа", [])
        if perms:
            print(f"\n  {Fore.WHITE}👥 Права доступа ({len(perms)} записей):")
            for i, perm in enumerate(perms, 1):
                print(f"     [{i}]")
                for k, v in perm.items():
                    print(f"       {Fore.CYAN}{k:10}: {Fore.GREEN}{v}")

        scan = result.get("Сканирование файла")
        if scan:
            print_image_scan_results(scan)

        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + "  📊 ГЕНЕРАЦИЯ ОТЧЁТА")
        generate_html_report([], {}, google_results=[result])

    log_action("Анализ Google Drive завершён")

def analyze_yandex_mode():
    """Режим анализа Яндекс.Диска"""
    from modules.cloud.yandex_disk import (
        analyze_yandex_file, analyze_yandex_folder,
        is_folder as yandex_is_folder,
    )

    url = input(
        Fore.YELLOW + "  Вставьте публичную ссылку на файл или папку Яндекс.Диска: "
        + Style.RESET_ALL
    ).strip()

    if yandex_is_folder(url):
        print(Fore.CYAN + "  📁 Обнаружена папка — анализируем все файлы...")
        results = analyze_yandex_folder(url)
        if not results:
            print(Fore.RED + "  ❌ Нет результатов.")
            return
        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + f"  📊 СВОДКА: {len(results)} файлов")
        for r in results:
            if "Ошибка" in r:
                print(Fore.RED + f"  ❌ {r['Ошибка']}")
                continue
            name    = r.get("Название", "—")
            scan    = r.get("Сканирование файла", {})
            img_cnt = scan.get("Изображений найдено", 0) if scan else 0
            gps     = "📍 GPS!" if scan and scan.get("GPS обнаружен") else ""
            print(f"  {Fore.WHITE}📄 {name:30} | {Fore.CYAN}🖼️  {img_cnt} изобр. {Fore.RED}{gps}")
        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + "  📊 ГЕНЕРАЦИЯ ОТЧЁТА")
        generate_html_report([], {}, google_results=results)
    else:
        result = analyze_yandex_file(url)
        if not result or "Ошибка" in result:
            print(Fore.RED + f"  ❌ {result.get('Ошибка','Неизвестная ошибка')}")
            return
        print(Fore.CYAN + f"\n{'='*60}")
        print(Fore.CYAN + "  📊 РЕЗУЛЬТАТЫ АНАЛИЗА ЯНДЕКС.ДИСКА")
        for key, value in result.items():
            if key == "Сканирование файла":
                continue
            print(f"  {Fore.WHITE}{key:35}: {Fore.GREEN}{value}")
        scan = result.get("Сканирование файла")
        if scan:
            print_image_scan_results(scan)
        print(Fore.CYAN + "  📊 ГЕНЕРАЦИЯ ОТЧЁТА")
        generate_html_report([], {}, google_results=[result])

    log_action("Анализ Яндекс.Диска завершён")


def main():
    print_banner()
    log_action("=== Запуск Forensic File Metadata Analyzer v2.0 ===")

    print(Fore.CYAN  + "  Выберите режим работы:\n")
    print(Fore.WHITE + "  1 — 📁 Анализ локальных файлов (DOCX, PDF, PPTX, JPG, PNG...)")
    print(Fore.WHITE + "  2 — ☁️  Анализ документа Google Drive по ссылке")
    print(Fore.WHITE + "  3 — 🟡 Анализ документа Яндекс.Диска по ссылке")
    print()

    choice = input(Fore.YELLOW + "  Ваш выбор ( 1 - 3 ): " + Style.RESET_ALL).strip()

    if choice == "1":
        folder = input(Fore.YELLOW + "  Путь к папке с файлами: " + Style.RESET_ALL).strip()
        if not os.path.isdir(folder):
            print(Fore.RED + "  ❌ Папка не найдена. Проверьте путь.")
            return
        analyze_folder(folder)

    elif choice == "2":
        analyze_google_doc_mode()

    elif choice == "3":
        analyze_yandex_mode()

    else:
        print(Fore.RED + "  ❌ Неверный выбор. Введите 1, 2 или 3.")


if __name__ == "__main__":
    main()