# modules/ole_analyzer.py
#
# Глубокий анализ Office-документов через oletools:
#   olevba  — извлечение и анализ VBA-макросов (код, автозапуск, IOC)
#   msodde  — обнаружение DDE-полей (Dynamic Data Exchange)
#   olefile — потоки и временны́е метки OLE2
#   msoffcrypto — детект зашифрованных файлов
#
# Стандарты: OOXML ISO 29500, ECMA-376, VBA ISO/IEC 26300

import os
from modules.logger import log_action

# ── oletools ──────────────────────────────────────────────────────────────────
try:
    from oletools.olevba import VBA_Parser
    OLEVBA_AVAILABLE = True
except ImportError:
    OLEVBA_AVAILABLE = False

try:
    from oletools.msodde import process_file as _dde_process
    MSODDE_AVAILABLE = True
except ImportError:
    MSODDE_AVAILABLE = False

# ── olefile ───────────────────────────────────────────────────────────────────
try:
    import olefile as _olefile
    OLEFILE_AVAILABLE = True
except ImportError:
    OLEFILE_AVAILABLE = False

# ── msoffcrypto ───────────────────────────────────────────────────────────────
try:
    import msoffcrypto
    MSOFFCRYPTO_AVAILABLE = True
except ImportError:
    MSOFFCRYPTO_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 1. Детект зашифрованного файла
# ─────────────────────────────────────────────────────────────────────────────

def detect_encryption(filepath: str) -> dict:
    """
    Определяет, зашифрован ли Office-документ (парольная защита).
    Сам факт шифрования — форензическая аномалия.
    """
    result = {"Зашифрован": False, "Аномалии": []}

    if not MSOFFCRYPTO_AVAILABLE:
        result["Статус"] = "msoffcrypto-tool не установлен"
        return result

    try:
        with open(filepath, "rb") as f:
            office_file = msoffcrypto.OfficeFile(f)
            if office_file.is_encrypted():
                result["Зашифрован"] = True
                result["Аномалии"].append(
                    "🔒 Файл зашифрован паролем — содержимое недоступно без пароля "
                    "(характерный признак сокрытия информации)"
                )
    except Exception as e:
        result["Статус"] = f"Ошибка проверки шифрования: {e}"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. Анализ VBA-макросов через olevba
# ─────────────────────────────────────────────────────────────────────────────

# Типы ключевых слов oletools → человекочитаемые метки
_KW_LABELS = {
    "AutoExec":    "Авто-запуск",
    "Suspicious":  "Подозрительно",
    "IOC":         "Индикатор угрозы (IOC)",
    "Hex String":  "Hex-строка",
    "Base64 String": "Base64",
    "Dridex String": "Dridex-обфускация",
    "VBA string":  "VBA-обфускация",
    "Obfuscation": "Обфускация",
    "External":    "Внешний ресурс",
}


def analyze_vba(filepath: str) -> dict:
    """
    Извлекает и анализирует VBA-макросы через olevba.

    Поддерживает: DOCX, XLSX, PPTX, DOC, XLS, PPT, XLSM, XLSB, DOTM, PPTM.

    Returns:
        {
          "Макросы обнаружены": bool,
          "Модулей": int,
          "Код макросов": [{"Модуль": str, "Код": str, "Строк": int}, ...],
          "Ключевые слова": [{"Категория": str, "Ключевое слово": str, "Описание": str}, ...],
          "Авто-запуск": [str, ...],   # функции, запускающиеся при открытии
          "Риск": str,
          "Аномалии": [str, ...],
        }
    """
    result = {
        "Макросы обнаружены": False,
        "Модулей":            0,
        "Код макросов":       [],
        "Ключевые слова":     [],
        "Авто-запуск":        [],
        "Риск":               "✅ VBA-макросы не обнаружены",
        "Аномалии":           [],
    }

    if not OLEVBA_AVAILABLE:
        result["Статус"] = "oletools не установлен — pip install oletools"
        return result

    try:
        vba = VBA_Parser(filepath)

        if not vba.detect_vba_macros():
            log_action(f"olevba: {os.path.basename(filepath)} — макросов нет")
            vba.close()
            return result

        result["Макросы обнаружены"] = True

        # ── Извлечение кода ───────────────────────────────────────────
        modules = []
        for (_fname, _stream, vba_filename, vba_code) in vba.extract_macros():
            if not vba_code or not vba_code.strip():
                continue
            modules.append({
                "Модуль": vba_filename,
                "Код":    vba_code,
                "Строк":  len(vba_code.splitlines()),
            })
        result["Модулей"]      = len(modules)
        result["Код макросов"] = modules

        # ── Анализ ключевых слов ──────────────────────────────────────
        keywords = []
        risk_score = 0
        auto_exec  = []

        for kw_type, keyword, description in vba.analyze_macros():
            label = _KW_LABELS.get(kw_type, kw_type)
            keywords.append({
                "Категория":      label,
                "Ключевое слово": keyword,
                "Описание":       description,
            })

            # Автозапуск — критично для форензики
            if kw_type == "AutoExec":
                auto_exec.append(keyword)
                result["Аномалии"].append(
                    f"⚡ Авто-запуск «{keyword}» — "
                    f"макрос выполнится автоматически при открытии документа"
                )
                risk_score += 3

            elif kw_type in ("Suspicious", "IOC"):
                result["Аномалии"].append(
                    f"🔴 {label}: «{keyword}» — {description}"
                )
                risk_score += 2

            elif kw_type == "Obfuscation":
                risk_score += 3

            elif kw_type in ("Hex String", "Base64 String",
                              "Dridex String", "VBA string"):
                risk_score += 2

            elif kw_type == "External":
                result["Аномалии"].append(
                    f"🌐 Внешний ресурс в макросе: «{keyword}»"
                )
                risk_score += 2

        result["Ключевые слова"] = keywords
        result["Авто-запуск"]   = auto_exec

        # Обфускация — сводная аномалия
        obfusc_count = sum(
            1 for k in keywords
            if k["Категория"] in ("Обфускация", "Hex-строка", "Base64",
                                   "Dridex-обфускация", "VBA-обфускация")
        )
        if obfusc_count > 0:
            result["Аномалии"].append(
                f"🔴 Обфускация кода: {obfusc_count} признаков — "
                f"код намеренно скрыт от анализа"
            )

        # ── Финальный уровень риска ───────────────────────────────────
        if risk_score >= 6:
            result["Риск"] = (
                f"🔴 КРИТИЧЕСКИЙ — {len(result['Аномалии'])} угрозы "
                f"(score={risk_score})"
            )
        elif risk_score >= 3:
            result["Риск"] = f"🟡 ПОДОЗРИТЕЛЬНО — требует ручного анализа (score={risk_score})"
        elif modules:
            result["Риск"] = f"🟡 МАКРОСЫ ПРИСУТСТВУЮТ — {len(modules)} модуль(ей)"

        vba.close()

    except Exception as e:
        result["Ошибка"] = str(e)
        log_action(f"olevba ошибка {filepath}: {e}")

    log_action(
        f"olevba: {os.path.basename(filepath)} | "
        f"Макросы: {result['Макросы обнаружены']} | "
        f"Модулей: {result['Модулей']} | "
        f"Аномалий: {len(result['Аномалии'])}"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. Обнаружение DDE-полей (Dynamic Data Exchange)
# ─────────────────────────────────────────────────────────────────────────────

def detect_dde(filepath: str) -> dict:
    """
    Обнаруживает DDE-поля в Word/Excel документах.

    DDE (Dynamic Data Exchange) — механизм Windows для межпроцессного обмена.
    В документах используется как вектор атаки: при открытии файла Word/Excel
    может выполнить произвольную команду через DDE без VBA-макросов.

    Техника активно применялась в APT-атаках (CVE не зафиксирован,
    классифицируется как «feature» Microsoft).

    Фильтрация: пропускаем стандартные Word-поля (PAGE, MERGEFORMAT, DATE…)
    и отдельные символы — они не являются DDE-атаками.
    """
    result = {
        "DDE обнаружен": False,
        "Полей":         0,
        "Поля":          [],
        "Аномалии":      [],
    }

    if not MSODDE_AVAILABLE:
        result["Статус"] = "oletools.msodde недоступен"
        return result

    # Обычные Word/Excel поля, которые msodde ошибочно помечает как DDE
    _SAFE_FIELDS = {
        "page", "numpages", "date", "time", "author", "title", "subject",
        "mergeformat", "numchars", "numwords", "filename", "docproperty",
        "styleref", "ref", "seq", "toc", "hyperlink", "xe", "tc",
        "pageref", "if", "set", "ask", "fillin", "index", "rd",
        "revnum", "savedate", "printdate", "edittime", "numref",
    }

    # Паттерны, характерные для реальных DDE-атак
    _DDE_ATTACK_PATTERNS = [
        "cmd", "powershell", "wscript", "cscript", "mshta", "rundll32",
        "regsvr32", "certutil", "bitsadmin", "msiexec", "wmic",
        "dde", "ddeauto", "shell", "winword", "excel", "msexcel",
        "\\\\", "c:\\", "system32", "%comspec%", "%windir%",
    ]

    try:
        raw = _dde_process(filepath, field_filter_mode=None)
        if not raw:
            return result

        # msodde возвращает символы по одному — склеиваем в строку,
        # затем разбиваем по переносам строк, чтобы получить целые поля
        joined = "".join(str(c) for c in raw)
        candidates = [ln.strip() for ln in joined.splitlines() if ln.strip()]

        real_dde = []
        for text in candidates:
            # Пропускаем слишком короткие фрагменты
            if len(text) <= 3:
                continue

            text_lower = text.lower()

            # Пропускаем стандартные Word-поля (PAGE, MERGEFORMAT, DATE…)
            if text_lower in _SAFE_FIELDS:
                continue
            if any(text_lower.startswith(sf) for sf in _SAFE_FIELDS):
                continue

            # Считаем реальным DDE только если присутствует паттерн атаки
            if any(pat in text_lower for pat in _DDE_ATTACK_PATTERNS):
                real_dde.append(text)

        if real_dde:
            result["DDE обнаружен"] = True
            result["Полей"]         = len(real_dde)
            result["Поля"]          = [f[:200] for f in real_dde]
            for field in real_dde:
                result["Аномалии"].append(
                    f"🔴 DDE-атака: «{field[:120]}» — "
                    f"возможно выполнение системных команд при открытии"
                )

    except Exception as e:
        log_action(f"msodde ошибка {filepath}: {e}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. OLE2-потоки и временны́е метки (olefile)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_ole_streams(filepath: str) -> dict:
    """
    Читает OLE2-структуру файла через olefile.
    Применимо к: DOC, XLS, PPT (бинарные форматы Office 97-2003)
    и к vbaProject.bin внутри DOCX/XLSX/PPTX.

    Возвращает список потоков с временны́ми метками — важно для
    установления хронологии редактирования.
    """
    result = {
        "OLE-файл":   False,
        "Потоков":    0,
        "Потоки":     [],
        "Метаданные": {},
        "Аномалии":   [],
    }

    if not OLEFILE_AVAILABLE:
        result["Статус"] = "olefile не установлен"
        return result

    ext = os.path.splitext(filepath)[1].lower()
    # olefile работает только с бинарными OLE2-форматами
    if ext not in (".doc", ".xls", ".ppt", ".dot", ".xlt", ".pps", ".msg"):
        result["Статус"] = f"OLE2-анализ не применим к {ext}"
        return result

    try:
        ole = _olefile.OleFileIO(filepath)
        result["OLE-файл"] = True

        # Список всех потоков
        streams = []
        for entry in ole.listdir():
            path = "/".join(entry)
            try:
                mtime = ole.get_type(entry)
                size  = ole.get_size(entry)
                streams.append({
                    "Путь":   path,
                    "Размер": f"{size} байт",
                })
            except Exception:
                streams.append({"Путь": path, "Размер": "—"})

        result["Потоков"] = len(streams)
        result["Потоки"]  = streams

        # SummaryInformation — базовые свойства документа
        if ole.exists("\x05SummaryInformation"):
            meta = ole.get_metadata()
            result["Метаданные"] = {
                "Автор":              str(meta.author or ""),
                "Последний редактор": str(meta.last_saved_by or ""),
                "Дата создания":      str(meta.create_time or ""),
                "Дата изменения":     str(meta.last_saved_time or ""),
                "Приложение":         str(meta.creating_application or ""),
                "Редакций":           str(meta.revision_number or ""),
                "Страниц":            str(meta.num_pages or ""),
                "Слов":               str(meta.num_words or ""),
            }

        ole.close()

    except Exception as e:
        result["Ошибка"] = str(e)
        log_action(f"olefile ошибка {filepath}: {e}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Главная функция — полный OLE-форензик
# ─────────────────────────────────────────────────────────────────────────────

def full_ole_analysis(filepath: str) -> dict:
    """
    Запускает полный набор OLE-анализа:
      1. Детект шифрования (msoffcrypto)
      2. VBA-макросы (olevba)
      3. DDE-поля (msodde)
      4. OLE2-потоки (olefile, только для бинарных форматов)

    Returns unified dict со всеми результатами.
    """
    ext = os.path.splitext(filepath)[1].lower()

    enc  = detect_encryption(filepath)
    vba  = analyze_vba(filepath)      if ext in (".docx", ".doc", ".xlsx", ".xls",
                                                   ".pptx", ".ppt", ".xlsm", ".xlsb",
                                                   ".dotm", ".pptm", ".docm") else {}
    dde  = detect_dde(filepath)       if ext in (".docx", ".doc", ".xlsx", ".xls") else {}
    ole  = analyze_ole_streams(filepath)

    # Суммарные аномалии
    all_anomalies = (
        enc.get("Аномалии", []) +
        vba.get("Аномалии", []) +
        dde.get("Аномалии", []) +
        ole.get("Аномалии", [])
    )

    return {
        "Шифрование": enc,
        "VBA":        vba,
        "DDE":        dde,
        "OLE":        ole,
        "Аномалии":   all_anomalies,
    }
