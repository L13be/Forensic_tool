import os
import zipfile
import xml.etree.ElementTree as ET
from modules.logger import log_action

DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".scr", ".pif", ".com", ".msi", ".reg", ".hta",
    ".wsf", ".wsh", ".lnk", ".inf", ".sys", ".drv",
}

SUSPICIOUS_PATTERNS = [
    "cmd.exe", "powershell", "wscript", "cscript",
    "shell32", "CreateObject", "WScript.Shell",
    "ADODB.Stream", "eval(", "base64",
    "AutoOpen", "AutoClose", "AutoExec",
    "Document_Open", "Workbook_Open",
]

SUSPICIOUS_DOMAINS = [
    "bit.ly", "tinyurl", "goo.gl", "ow.ly",
    "pastebin", "ngrok", "duckdns",
]


def _check_embedded_files(filepath: str) -> list:
    findings = []
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            for name in z.namelist():
                ext = os.path.splitext(name)[1].lower()

                if ext in DANGEROUS_EXTENSIONS:
                    findings.append(
                        f"🔴 Обнаружен опасный файл внутри документа: {name}"
                    )

                if "vbaProject" in name:
                    findings.append(
                        f"🟡 Обнаружен модуль макросов: {name} — требует проверки"
                    )

                if "oleObject" in name.lower() or "embeddings" in name.lower():
                    findings.append(
                        f"🟡 Обнаружен OLE/Embedded объект: {name}"
                    )

    except zipfile.BadZipFile:
        findings.append("🟡 Файл не является валидным ZIP/DOCX архивом")
    except Exception as e:
        findings.append(f"⚠️ Ошибка проверки архива: {e}")

    return findings


def _check_xml_content(filepath: str) -> list:
    import re as _re

    findings = []

    SAFE_NAMESPACES = [
        "schemas.openxmlformats.org",
        "schemas.microsoft.com",
        "purl.org/dc/",
        "www.w3.org",
        "schemas.android.com",
    ]

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            xml_files = [
                f for f in z.namelist()
                if f.endswith(".xml") or f.endswith(".rels")
            ]

            for xml_name in xml_files:
                try:
                    content = z.read(xml_name).decode("utf-8", errors="ignore")
                    content_lower = content.lower()

                    for pattern in SUSPICIOUS_PATTERNS:
                        if pattern.lower() in content_lower:
                            findings.append(
                                f"🟡 Подозрительный паттерн «{pattern}» в {xml_name}"
                            )

                    urls = _re.findall(r'https?://[^\s"\'<>]+', content)
                    for url in urls:
                        if any(ns in url for ns in SAFE_NAMESPACES):
                            continue
                        if any(d in url.lower() for d in SUSPICIOUS_DOMAINS):
                            findings.append(
                                f"🔴 Подозрительный домен в {xml_name}: {url[:80]}"
                            )

                except Exception:
                    continue

    except Exception as e:
        findings.append(f"⚠️ Ошибка сканирования XML: {e}")

    return findings

def _check_external_links(filepath: str) -> list:
    findings = []
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            rels_files = [f for f in z.namelist() if f.endswith(".rels")]

            for rels_name in rels_files:
                try:
                    content = z.read(rels_name).decode("utf-8", errors="ignore")
                    root    = ET.fromstring(content)

                    for rel in root.findall(
                        ".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
                    ):
                        target      = rel.get("Target", "")
                        rel_type    = rel.get("Type",   "")
                        target_mode = rel.get("TargetMode", "")

                        if target_mode != "External":
                            continue
                        if not any(p in target.lower() for p in ["http://", "https://", "ftp://"]):
                            continue

                        if "attachedTemplate" in rel_type and target.startswith("http"):
                            findings.append(
                                f"🔴 ОПАСНО: Шаблон загружается с внешнего URL: {target} "
                                f"— техника Template Injection"
                            )
                            continue

                        is_suspicious = any(d in target.lower() for d in SUSPICIOUS_DOMAINS)
                        if is_suspicious:
                            findings.append(
                                f"🔴 Подозрительная внешняя ссылка: {target}"
                            )

                except Exception:
                    continue

    except Exception as e:
        findings.append(f"⚠️ Ошибка проверки .rels: {e}")

    return findings


def _check_pdf(filepath: str) -> list:
    findings = []
    try:
        with open(filepath, "rb") as f:
            content = f.read().decode("latin-1", errors="ignore")

        pdf_dangerous = {
            "/JavaScript": "JavaScript код в PDF (возможна интерактивная форма или угроза)",
            "/JS": "JavaScript — сокращённая форма (возможна интерактивная форма или угроза)",
            "/AA":          "Автоматическое действие (AutoAction)",
            "/OpenAction":  "Действие при открытии файла",
            "/Launch":      "Запуск внешней программы",
            "/EmbeddedFile":"Встроенный файл в PDF",
            "/RichMedia":   "Rich Media объект",
            "/XFA":         "XFA форма (потенциально опасна)",
            "/Encrypt":     "Зашифрованное содержимое",
            "/ObjStm":      "Сжатые объекты (обфускация)",
            "/URI":         "Внешний URI в PDF",
        }

        for keyword, description in pdf_dangerous.items():
            if keyword in content:
                level = "🔴" if keyword in ("/JavaScript", "/Launch", "/OpenAction") else "🟡"
                findings.append(f"{level} PDF: {description} ({keyword})")

        for domain in SUSPICIOUS_DOMAINS:
            if domain in content.lower():
                findings.append(f"🔴 PDF: Подозрительный домен «{domain}»")

    except Exception as e:
        findings.append(f"⚠️ Ошибка анализа PDF: {e}")

    return findings


def _check_image(filepath: str) -> list:
    findings = []
    try:
        size = os.path.getsize(filepath)
        ext  = os.path.splitext(filepath)[1].lower()

        if ext in (".jpg", ".jpeg") and size > 10 * 1024 * 1024:
            findings.append(
                f"🟡 Аномально большой JPEG ({round(size/1024/1024, 1)} МБ) "
                f"— возможна стеганография"
            )
        if ext == ".png" and size > 20 * 1024 * 1024:
            findings.append(
                f"🟡 Аномально большой PNG ({round(size/1024/1024, 1)} МБ) "
                f"— возможна стеганография"
            )

        with open(filepath, "rb") as f:
            header = f.read(16)

        signatures = {
            b"\xff\xd8\xff":           "JPEG",
            b"\x89PNG\r\n\x1a\n":      "PNG",
            b"GIF87a":                 "GIF",
            b"GIF89a":                 "GIF",
            b"BM":                     "BMP",
            b"II\x2a\x00":            "TIFF",
            b"MM\x00\x2a":            "TIFF",
        }

        ext_to_sig = {
            ".jpg":  b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff",
            ".png":  b"\x89PNG",
            ".gif":  b"GIF",
            ".bmp":  b"BM",
        }

        expected = ext_to_sig.get(ext)
        if expected and not header.startswith(expected):
            findings.append(
                f"🔴 Сигнатура файла не соответствует расширению {ext} "
                f"— файл может быть замаскирован"
            )

        with open(filepath, "rb") as f:
            content = f.read()
        if b"PK\x03\x04" in content[100:]:
            findings.append(
                "🔴 Обнаружен ZIP-архив внутри изображения — возможен polyglot файл"
            )

        if b"MZ" in content[100:] and b"PE\x00\x00" in content:
            findings.append(
                "🔴 Обнаружена сигнатура исполняемого файла (PE) внутри изображения"
            )

    except Exception as e:
        findings.append(f"⚠️ Ошибка проверки изображения: {e}")

    return findings


def scan_file(filepath: str) -> dict:
    ext      = os.path.splitext(filepath)[1].lower()
    fname    = os.path.basename(filepath)
    findings = []
    risk     = "✅ Угроз не обнаружено"

    log_action(f"Вирусное сканирование: {fname}")

    if ext in (".docx", ".pptx", ".xlsx", ".doc"):
        findings += _check_embedded_files(filepath)
        findings += _check_xml_content(filepath)
        findings += _check_external_links(filepath)

    elif ext == ".pdf":
        findings += _check_pdf(filepath)

    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"):
        findings += _check_image(filepath)

    else:
        findings.append(f"🟡 Тип файла {ext} не поддерживается для сканирования")

    red_count    = sum(1 for f in findings if f.startswith("🔴"))
    yellow_count = sum(1 for f in findings if f.startswith("🟡"))

    if red_count > 0:
        risk = f"🔴 ВЫСОКИЙ РИСК ({red_count} критических)"
    elif yellow_count > 0:
        risk = f"🟡 ТРЕБУЕТ ВНИМАНИЯ ({yellow_count} предупреждений)"
    else:
        risk = "✅ Угроз не обнаружено"

    result = {
        "Файл":        fname,
        "Расширение":  ext,
        "Риск":        risk,
        "Находки":     findings,
        "Красных":     red_count,
        "Жёлтых":     yellow_count,
    }

    log_action(
        f"Сканирование завершено: {fname} | "
        f"Риск: {risk} | Находок: {len(findings)}"
    )

    return result