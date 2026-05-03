import re
import zipfile
import os
from modules.logger import log_action

# Стандартные безопасные домены (namespace Microsoft, W3C и т.д.)
SAFE_DOMAINS = [
    "schemas.openxmlformats.org",
    "schemas.microsoft.com",
    "schemas.android.com",
    "purl.org",
    "www.w3.org",
    "dublincore.org",
    "ns.adobe.com",
]

# Подозрительные ключевые слова — проверяем только по домену, не по всему URL
SUSPICIOUS_KEYWORDS = [
    "bit.ly", "tinyurl.com", "t.co", "goo.gl",
    "onion", "tor2web",
    "ngrok.io", "serveo.net", "localhost.run",
    "pastebin.com", "hastebin.com", "ghostbin.com",
    "temp-mail.org", "guerrillamail.com",
    "mega.nz", "anonfiles.com",
]

def _is_safe_namespace(url: str) -> bool:
    """Возвращает True если URL — стандартный XML namespace, не реальная ссылка"""
    return any(safe in url for safe in SAFE_DOMAINS)

def _extract_domain(url: str) -> str:
    try:
        return url.split("/")[2].lower()
    except IndexError:
        return ""

def extract_urls(filepath: str) -> dict:
    """
    Извлекает все гиперссылки и URL из документа.
    Полезно для OSINT: найденные ссылки могут указывать
    на инфраструктуру злоумышленника, фишинговые сайты,
    облачные хранилища или профили в соцсетях.
    """
    result = {
        "Гиперссылки из XML":  [],
        "URL из текста":       [],
        "Уникальные домены":   [],
        "Подозрительные URL":  [],
    }

    url_pattern       = re.compile(r'https?://[^\s"<>\']+')
    hyperlink_pattern = re.compile(r'Target="(https?://[^"]+)"')

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            for filename in z.namelist():
                if not (filename.endswith(".xml") or filename.endswith(".rels")):
                    continue

                content = z.read(filename).decode("utf-8", errors="ignore")

                # Гиперссылки из .rels — только реальные, не namespace
                for match in hyperlink_pattern.findall(content):
                    if match not in result["Гиперссылки из XML"]:
                        if not _is_safe_namespace(match):
                            result["Гиперссылки из XML"].append(match)

                # URL из текста XML — тоже только реальные
                for match in url_pattern.findall(content):
                    clean = match.rstrip(".,;)")
                    if clean not in result["URL из текста"]:
                        if not _is_safe_namespace(clean):
                            result["URL из текста"].append(clean)

        # Уникальные домены
        all_urls = result["Гиперссылки из XML"] + result["URL из текста"]
        domains  = set()
        for url in all_urls:
            d = _extract_domain(url)
            if d:
                domains.add(d)
        result["Уникальные домены"] = sorted(domains)

        # Проверка на подозрительность — сравниваем по домену точно
        for url in all_urls:
            domain = _extract_domain(url)
            for keyword in SUSPICIOUS_KEYWORDS:
                # Точное совпадение домена или домен заканчивается на keyword
                if domain == keyword or domain.endswith("." + keyword):
                    entry = f"⚠️ {url}  [{keyword}]"
                    if entry not in result["Подозрительные URL"]:
                        result["Подозрительные URL"].append(entry)
                    break

    except Exception as e:
        result["Ошибка"] = str(e)

    fname = os.path.basename(filepath)
    log_action(
        f"URL извлечены: {fname} | "
        f"Гиперссылок: {len(result['Гиперссылки из XML'])} | "
        f"Подозрительных: {len(result['Подозрительные URL'])}"
    )
    return result