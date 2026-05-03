from docx import Document
import os
import zipfile
import xml.etree.ElementTree as ET
from modules.logger import log_action
from modules.hasher import compute_hashes

def extract_app_properties(filepath: str) -> dict:
    """
    Извлекает расширенные свойства из docProps/app.xml —
    там хранится информация о приложении, компании, статистика документа.
    Эти данные недоступны через python-docx напрямую, поэтому читаем XML вручную.
    """
    app_props = {}
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "docProps/app.xml" in z.namelist():
                content = z.read("docProps/app.xml").decode("utf-8", errors="ignore")
                root    = ET.fromstring(content)

                # Убираем namespace из тегов для удобного поиска
                for elem in root.iter():
                    elem.tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                fields = {
                    "Application":    "Приложение",
                    "AppVersion":     "Версия приложения",
                    "Company":        "Организация",
                    "Manager":        "Менеджер",
                    "Template":       "Шаблон документа",
                    "Pages":          "Страниц",
                    "Words":          "Слов",
                    "Characters":     "Символов",
                    "CharactersWithSpaces": "Символов с пробелами",
                    "Paragraphs":     "Абзацев",
                    "Lines":          "Строк",
                    "TotalTime":      "Время редактирования (мин)",
                    "DocSecurity":    "Защита документа",
                    "HyperlinksChanged": "Гиперссылки изменялись",
                    "LinksUpToDate":  "Ссылки актуальны",
                    "ScaleCrop":      "Масштабирование",
                    "SharedDoc":      "Общий документ",
                }

                for xml_key, ru_key in fields.items():
                    elem = root.find(xml_key)
                    if elem is not None and elem.text:
                        app_props[ru_key] = elem.text.strip()

    except Exception as e:
        app_props["Ошибка app.xml"] = str(e)

    return app_props


def extract_metadata(filepath: str) -> dict:
    """
    Полное извлечение метаданных из DOCX-файла.
    Включает: базовые свойства, расширенные свойства приложения,
    криминалистически значимые поля, хэши для доказательной базы.
    """
    log_action(f"Начало анализа файла: {filepath}")

    doc    = Document(filepath)
    props  = doc.core_properties
    hashes = compute_hashes(filepath)
    app    = extract_app_properties(filepath)
    size   = os.path.getsize(filepath)

    metadata = {

        # ── ИДЕНТИФИКАЦИЯ ФАЙЛА ──────────────────────────────
        "Файл":              os.path.basename(filepath),
        "Полный путь":       os.path.abspath(filepath),
        "Размер файла":      f"{size} байт ({round(size / 1024, 2)} КБ)",

        # ── АВТОРСТВО (ключевое для экспертизы) ──────────────
        "Автор":                  props.author           or "Не указан",
        "Последний редактор":     props.last_modified_by or "Не указан",
        "Организация":            app.get("Организация", "Не указана"),
        "Менеджер":               app.get("Менеджер",    "Не указан"),

        # ── ВРЕМЕННЫ́Е МЕТКИ (критично для установления хронологии) ──
        "Дата создания":          str(props.created)  if props.created  else "Нет данных",
        "Дата изменения":         str(props.modified) if props.modified else "Нет данных",
        "Время редактирования":   app.get("Время редактирования (мин)", "Нет данных") + " мин"
                                  if app.get("Время редактирования (мин)") else "Нет данных",
        "Номер редакции":         str(props.revision) if props.revision else "Нет данных",

        # ── ПРОГРАММНАЯ СРЕДА (установление происхождения) ───
        "Приложение":             app.get("Приложение",         "Не определено"),
        "Версия приложения":      app.get("Версия приложения",  "Не определена"),
        "Шаблон документа":       app.get("Шаблон документа",   "Не указан"),

        # ── СОДЕРЖИМОЕ ДОКУМЕНТА ─────────────────────────────
        "Название":               getattr(props, 'title',       None) or "Не указано",
        "Тема":                   getattr(props, 'subject',     None) or "Не указана",
        "Категория":              getattr(props, 'category',    None) or "Не указана",
        "Ключевые слова":         getattr(props, 'keywords',    None) or "Не указаны",
        "Комментарий":            getattr(props, 'comments',    None) or "Нет",
        "Описание":               getattr(props, 'description', None) or "Нет",
        "Язык":                   getattr(props, 'language',    None) or "Не указан",
        "Идентификатор":          getattr(props, 'identifier',  None) or "Нет",

        # ── СТАТИСТИКА (помогает оценить объём работы) ───────
        "Страниц":                app.get("Страниц",    "—"),
        "Слов":                   app.get("Слов",       "—"),
        "Абзацев":                app.get("Абзацев",    "—"),
        "Строк":                  app.get("Строк",      "—"),
        "Символов":               app.get("Символов",   "—"),

        # ── БЕЗОПАСНОСТЬ ─────────────────────────────────────
        "Защита документа":       app.get("Защита документа", "0"),
        "Общий документ":         app.get("Общий документ",   "Нет"),

        # ── КРИПТОГРАФИЧЕСКИЕ ХЭШИ (доказательная база) ──────
        "MD5":                    hashes["MD5"],
        "SHA256":                 hashes["SHA256"],
    }

    log_action(
        f"Метаданные извлечены: {os.path.basename(filepath)} | "
        f"Автор: {metadata['Автор']} | "
        f"Приложение: {metadata['Приложение']} | "
        f"Редакций: {metadata['Номер редакции']}"
    )
    return metadata