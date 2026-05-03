import zipfile
import xml.etree.ElementTree as ET
import os
from modules.logger import log_action

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _get_text_from_run(run) -> str:
    """Извлекает текст из одного run элемента"""
    texts = []
    for t in run.findall(f"{{{W_NS}}}t"):
        if t.text is not None:
            texts.append(t.text)
    return "".join(texts)


def _is_hidden_run(run) -> bool:
    """Проверяет есть ли флаг w:vanish в run"""
    rpr = run.find(f"{{{W_NS}}}rPr")
    if rpr is None:
        return False
    return rpr.find(f"{{{W_NS}}}vanish") is not None


def _is_hidden_para(para) -> bool:
    """Проверяет есть ли флаг w:vanish на уровне параграфа"""
    ppr = para.find(f"{{{W_NS}}}pPr")
    if ppr is None:
        return False
    rpr = ppr.find(f"{{{W_NS}}}rPr")
    if rpr is None:
        return False
    return rpr.find(f"{{{W_NS}}}vanish") is not None


def _collect_runs(element) -> list:
    """
    Рекурсивно собирает все w:r элементы внутри элемента.
    Нужно потому что runs могут быть внутри w:hyperlink,
    w:ins, w:del и других вложенных тегов.
    """
    runs = []
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "r":
            runs.append(child)
        else:
            # Рекурсивно ищем внутри вложенных элементов
            runs.extend(_collect_runs(child))
    return runs


def extract_hidden_text(filepath: str) -> dict:
    """
    Извлекает скрытый текст из DOCX документа.
    Скрытый текст — фрагменты с флагом w:vanish в Word XML.
    Поддерживает runs внутри гиперссылок и вложенных элементов.
    """
    result = {
        "Скрытых фрагментов": 0,
        "Скрытый текст":      [],
        "Аномалии":           [],
        "Примечание":         "",
    }

    fname = os.path.basename(filepath)

    try:
        with zipfile.ZipFile(filepath, "r") as z:
            if "word/document.xml" not in z.namelist():
                result["Примечание"] = "word/document.xml не найден"
                return result
            content = z.read("word/document.xml").decode("utf-8", errors="ignore")

        root = ET.fromstring(content)
        body = root.find(f".//{{{W_NS}}}body")

        if body is None:
            result["Примечание"] = "Тело документа не найдено"
            return result

        hidden_fragments = []

        for para_idx, para in enumerate(body.findall(f".//{{{W_NS}}}p")):
            para_hidden = _is_hidden_para(para)

            # Собираем ВСЕ runs включая вложенные в hyperlink и т.д.
            all_runs = _collect_runs(para)

            hidden_runs_text  = []
            visible_runs_text = []

            for run in all_runs:
                run_text = _get_text_from_run(run)
                if run_text is None:
                    continue
                if para_hidden or _is_hidden_run(run):
                    hidden_runs_text.append(run_text)
                else:
                    visible_runs_text.append(run_text)

            if hidden_runs_text:
                hidden_text = "".join(hidden_runs_text)
                # Убираем лишние пробелы но сохраняем структуру
                hidden_text_clean = " ".join(hidden_text.split())
                visible_ctx = "".join(visible_runs_text)

                if not hidden_text_clean:
                    continue

                fragment = {
                    "Параграф №":    para_idx + 1,
                    "Скрытый текст": hidden_text_clean,
                    "Контекст":      visible_ctx[:80] + "..." if len(visible_ctx) > 80 else visible_ctx,
                    "Тип сокрытия":  "Весь параграф скрыт" if para_hidden else "Частичное сокрытие",
                    "Длина (симв.)": len(hidden_text_clean),
                }
                hidden_fragments.append(fragment)

        result["Скрытых фрагментов"] = len(hidden_fragments)
        result["Скрытый текст"]      = hidden_fragments

        if hidden_fragments:
            total_hidden_chars = sum(f["Длина (симв.)"] for f in hidden_fragments)

            result["Аномалии"].append(
                f"⚠️ Обнаружен скрытый текст: {len(hidden_fragments)} фрагментов, "
                f"{total_hidden_chars} символов"
            )

            SUSPICIOUS = [
                "пароль", "password", "passwd", "секрет", "secret",
                "токен", "token", "ключ", "key", "login", "логин",
                "карта", "card", "счёт", "account", "инн", "снилс",
            ]
            for fragment in hidden_fragments:
                text_lower = fragment["Скрытый текст"].lower()
                for keyword in SUSPICIOUS:
                    if keyword in text_lower:
                        result["Аномалии"].append(
                            f"🔴 Подозрительное слово «{keyword}» "
                            f"в скрытом тексте параграфа №{fragment['Параграф №']}"
                        )
                        break

            if total_hidden_chars > 500:
                result["Аномалии"].append(
                    f"🔴 Большой объём скрытого текста: {total_hidden_chars} символов — "
                    f"возможна намеренная скрытая информация"
                )
            elif total_hidden_chars > 100:
                result["Аномалии"].append(
                    f"🟡 Значительный объём скрытого текста: {total_hidden_chars} символов"
                )
        else:
            result["Примечание"] = "Скрытый текст не обнаружен"

    except zipfile.BadZipFile:
        result["Аномалии"].append("❌ Файл повреждён или не является DOCX")
    except Exception as e:
        result["Аномалии"].append(f"❌ Ошибка анализа: {e}")

    log_action(
        f"Анализ скрытого текста: {fname} | "
        f"Фрагментов: {result['Скрытых фрагментов']} | "
        f"Аномалий: {len(result['Аномалии'])}"
    )

    return result