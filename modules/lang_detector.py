import os
from modules.logger import log_action

try:
    from langdetect import detect, detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# Расшифровка кодов языков
LANG_NAMES = {
    "ru": "Русский",
    "en": "Английский",
    "de": "Немецкий",
    "fr": "Французский",
    "zh-cn": "Китайский",
    "ar": "Арабский",
    "uk": "Украинский",
    "pl": "Польский",
    "es": "Испанский",
    "it": "Итальянский",
    "tr": "Турецкий",
    "fa": "Персидский (фарси)",
    "ko": "Корейский",
    "ja": "Японский",
}

def detect_language(filepath: str) -> dict:
    """
    Определяет язык текста документа.
    Полезно при международных расследованиях —
    помогает установить вероятное происхождение документа
    и направить его на перевод нужному специалисту.
    """
    result = {
        "Основной язык":       "Не определён",
        "Код языка":           "—",
        "Вероятности языков":  [],
        "Примечание":          "",
    }

    if not LANGDETECT_AVAILABLE:
        result["Примечание"] = "⚠️ Установите: pip install langdetect"
        return result

    try:
        from docx import Document
        doc  = Document(filepath)
        text = " ".join([p.text for p in doc.paragraphs if p.text.strip()])

        if len(text.strip()) < 20:
            result["Примечание"] = "Текст слишком короткий для определения языка"
            return result

        # Основной язык
        lang_code = detect(text)
        result["Код языка"]     = lang_code
        result["Основной язык"] = LANG_NAMES.get(lang_code, f"Неизвестный ({lang_code})")

        # Все вероятности
        langs = detect_langs(text)
        result["Вероятности языков"] = [
            f"{LANG_NAMES.get(str(l).split(':')[0], str(l).split(':')[0])}: "
            f"{round(float(str(l).split(':')[1]) * 100)}%"
            for l in langs
        ]

    except Exception as e:
        result["Примечание"] = f"Ошибка: {str(e)}"

    log_action(
        f"Язык определён: {os.path.basename(filepath)} | "
        f"Язык: {result['Основной язык']}"
    )
    return result