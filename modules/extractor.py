from docx import Document
import os
import zipfile
import xml.etree.ElementTree as ET
from modules.logger import log_action
from modules.hasher import compute_hashes

def extract_app_properties(filepath: str) -> dict:
    app_props = {}
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "docProps/app.xml" in z.namelist():
                content = z.read("docProps/app.xml").decode("utf-8", errors="ignore")
                root    = ET.fromstring(content)

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


def _extract_core_xml(filepath: str) -> dict:
    NS = {
        "cp":      "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc":      "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
    }
    result = {}
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "docProps/core.xml" not in z.namelist():
                return result
            content = z.read("docProps/core.xml").decode("utf-8", errors="ignore")
            root    = ET.fromstring(content)

            def g(tag, ns_key):
                el = root.find(f"{{{NS[ns_key]}}}{tag}")
                return el.text.strip() if el is not None and el.text else None

            result["author"]           = g("creator",        "dc")
            result["last_modified_by"] = g("lastModifiedBy", "cp")
            result["created"]          = g("created",        "dcterms")
            result["modified"]         = g("modified",       "dcterms")
            result["revision"]         = g("revision",       "cp")
            result["title"]            = g("title",          "dc")
            result["subject"]          = g("subject",        "dc")
            result["keywords"]         = g("keywords",       "cp")
            result["category"]         = g("category",       "cp")
            result["description"]      = g("description",    "dc")
            result["language"]         = g("language",       "dc")
            result["identifier"]       = g("identifier",     "dc")
    except Exception:
        pass
    return result


def extract_metadata(filepath: str) -> dict:
    log_action(f"Начало анализа файла: {filepath}")

    hashes = compute_hashes(filepath)
    app    = extract_app_properties(filepath)
    size   = os.path.getsize(filepath)

    try:
        doc   = Document(filepath)
        props = doc.core_properties
        core  = {
            "author":           props.author or "",
            "last_modified_by": props.last_modified_by or "",
            "created":          str(props.created)  if props.created  else None,
            "modified":         str(props.modified) if props.modified else None,
            "revision":         str(props.revision) if props.revision else None,
            "title":            getattr(props, "title",       None),
            "subject":          getattr(props, "subject",     None),
            "keywords":         getattr(props, "keywords",    None),
            "category":         getattr(props, "category",    None),
            "description":      getattr(props, "description", None),
            "language":         getattr(props, "language",    None),
            "identifier":       getattr(props, "identifier",  None),
        }
    except Exception:
        core = _extract_core_xml(filepath)

    metadata = {

        "Файл":              os.path.basename(filepath),
        "Полный путь":       os.path.abspath(filepath),
        "Размер файла":      f"{size} байт ({round(size / 1024, 2)} КБ)",

        "Автор":                  core.get("author")           or "Не указан",
        "Последний редактор":     core.get("last_modified_by") or "Не указан",
        "Организация":            app.get("Организация", "Не указана"),
        "Менеджер":               app.get("Менеджер",    "Не указан"),

        "Дата создания":          core.get("created")  or "Нет данных",
        "Дата изменения":         core.get("modified") or "Нет данных",
        "Время редактирования":   app.get("Время редактирования (мин)", "Нет данных") + " мин"
                                  if app.get("Время редактирования (мин)") else "Нет данных",
        "Номер редакции":         core.get("revision") or "Нет данных",

        "Приложение":             app.get("Приложение",         "Не определено"),
        "Версия приложения":      app.get("Версия приложения",  "Не определена"),
        "Шаблон документа":       app.get("Шаблон документа",   "Не указан"),

        "Название":               core.get("title")       or "Не указано",
        "Тема":                   core.get("subject")     or "Не указана",
        "Категория":              core.get("category")    or "Не указана",
        "Ключевые слова":         core.get("keywords")    or "Не указаны",
        "Комментарий":            core.get("description") or "Нет",
        "Описание":               core.get("description") or "Нет",
        "Язык":                   core.get("language")    or "Не указан",
        "Идентификатор":          core.get("identifier")  or "Нет",

        "Страниц":                app.get("Страниц",    "—"),
        "Слов":                   app.get("Слов",       "—"),
        "Абзацев":                app.get("Абзацев",    "—"),
        "Строк":                  app.get("Строк",      "—"),
        "Символов":               app.get("Символов",   "—"),

        "Защита документа":       app.get("Защита документа", "0"),
        "Общий документ":         app.get("Общий документ",   "Нет"),

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