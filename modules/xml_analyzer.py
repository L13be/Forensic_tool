import zipfile
import os
from modules.logger import log_action

def analyze_xml_structure(filepath: str) -> dict:
    """
    DOCX — это ZIP-архив с XML файлами внутри.
    Этот модуль вскрывает архив и анализирует его содержимое —
    находит скрытые части, нестандартные компоненты, встроенные объекты.
    Полезно для выявления скрытого содержимого и следов редактирования.
    """
    result = {
        "Все файлы внутри DOCX":       [],
        "XML компоненты":               [],
        "Встроенные медиафайлы":        [],
        "Нестандартные компоненты":     [],
        "Наличие макросов (vbaProject)": "Нет",
    }

    standard_parts = {
        "word/document.xml",
        "word/styles.xml",
        "word/settings.xml",
        "word/theme/theme1.xml",
        "word/webSettings.xml",
        "word/fontTable.xml",
        "docProps/core.xml",
        "docProps/app.xml",
        "[Content_Types].xml",
        "_rels/.rels",
        "word/_rels/document.xml.rels",
    }

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            all_files = z.namelist()
            result["Все файлы внутри DOCX"] = all_files

            for f in all_files:
                if f.endswith(".xml") or f.endswith(".rels"):
                    result["XML компоненты"].append(f)

                if f.startswith("word/media/"):
                    result["Встроенные медиафайлы"].append(f)

                if "vbaProject" in f:
                    result["Наличие макросов (vbaProject)"] = "⚠️ ДА — обнаружен vbaProject.bin"

                if f not in standard_parts and not f.startswith("word/media/") \
                   and not f.startswith("word/_rels/") and not f.endswith(".rels"):
                    result["Нестандартные компоненты"].append(f)

    except Exception as e:
        result["Ошибка"] = str(e)

    log_action(
        f"XML-структура проанализирована: {os.path.basename(filepath)} | "
        f"Файлов внутри: {len(result['Все файлы внутри DOCX'])} | "
        f"Медиафайлов: {len(result['Встроенные медиафайлы'])}"
    )
    return result