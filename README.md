<div align="center">

# 🔍 Forensic File Metadata Analyzer

### Инструмент компьютерной форензики и анализа метаданных

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Version](https://img.shields.io/badge/Version-2.0-blue?style=for-the-badge)


</div>

---

## 📋 О проекте

**Forensic File Metadata Analyzer v2.0** — программный инструмент для автоматизированного извлечения и анализа метаданных цифровых документов в рамках компьютерно-технической экспертизы.

Инструмент позволяет эксперту быстро установить:
- **авторство** документа и историю его редактирования
- **временны́е метки** создания, изменения и печати
- **GPS-координаты** из встроенных изображений
- **признаки фальсификации** — подмену дат, сброс истории, скрытый текст
- **угрозы безопасности** — макросы, OLE-объекты, Template Injection

---

## ⚙️ Возможности

| Модуль | Описание |
|--------|----------|
| 📄 **Метаданные документов** | DOCX, PDF, PPTX — автор, редактор, даты, приложение, статистика |
| 🖼️ **EXIF изображений** | GPS-координаты, модель камеры, серийный номер, дата съёмки, ПО |
| 👁️ **Скрытый текст** | Обнаружение фрагментов с флагом `w:vanish` в DOCX |
| 🛡️ **Статический анализ угроз** | Макросы VBA, OLE, Template Injection, polyglot-файлы |
| 🔗 **URL и гиперссылки** | Извлечение и OSINT-проверка всех ссылок документа |
| 🌍 **Определение языка** | Установление вероятного происхождения документа |
| ⚠️ **Детектор аномалий** | Несоответствия дат, сброс редакций, пустой автор |
| ☁️ **Google Drive** | Метаданные, права доступа, EXIF изображений через API |
| 🟡 **Яндекс.Диск** | Анализ публичных файлов и папок |
| 🔐 **Криптохэши** | MD5 и SHA-256 для доказательной базы (FIPS 180-4) |
| 📊 **Отчёты** | HTML-отчёт для эксперта + CSV-экспорт |

---

## 🖥️ Интерфейс

Инструмент поддерживает два режима запуска:

```
▶  python main.py     — консольный режим (CLI)
▶  python gui.py      — графический интерфейс (GUI)
```

**GUI** построен на `CustomTkinter` с тёмной темой:
- левая панель: выбор режима и источника файлов
- правая панель: лог анализа, результаты, прогресс
- кнопка открытия HTML-отчёта прямо в браузере

---

## 🚀 Установка

### 1. Клонировать репозиторий
```bash
git clone https://github.com/L13be/Forensic_tool.git
cd Forensic_tool
```

### 2. Создать виртуальное окружение
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
```

### 3. Установить зависимости
```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения
```bash
# Скопируй шаблон и заполни свои токены
copy .env.example .env
```

Содержимое `.env`:
```env
YANDEX_TOKEN=your_yandex_oauth_token_here
GDRIVE_CREDENTIALS=credentials.json
GDRIVE_TOKEN=token.json
```

> **Google Drive:** положи `credentials.json` из Google Cloud Console рядом с `main.py`.  
> При первом запуске откроется браузер для OAuth2-авторизации.

---

## 📂 Структура проекта

```
docx_forensic_analyzer/
│
├── main.py                        # CLI: точка входа, основной поток анализа
├── gui.py                         # GUI: графический интерфейс (CustomTkinter)
├── requirements.txt               # Зависимости
├── .env.example                   # Шаблон переменных окружения
│
├── modules/
│   ├── extractor.py               # Извлечение метаданных DOCX (core.xml, app.xml)
│   ├── anomaly_detector.py        # Детектор аномалий в метаданных
│   ├── hidden_text.py             # Обнаружение скрытого текста (w:vanish)
│   ├── image_extractor.py         # EXIF анализ: GPS, камера, временны́е метки
│   ├── virus_scanner.py           # Статический анализ угроз
│   ├── xml_analyzer.py            # Анализ ZIP/XML структуры DOCX
│   ├── url_extractor.py           # Извлечение и проверка гиперссылок
│   ├── lang_detector.py           # Определение языка документа
│   ├── reporter.py                # Генерация HTML-отчёта
│   ├── exporter.py                # CSV-экспорт результатов
│   ├── hasher.py                  # MD5 / SHA-256 (чанковое чтение 64 КБ)
│   ├── logger.py                  # Журнал действий эксперта
│   │
│   └── cloud/
│       ├── google_drive.py        # Google Drive API v3 (OAuth2)
│       ├── yandex_disk.py         # Яндекс.Диск REST API
│       ├── file_scanner.py        # EXIF-сканирование облачных файлов
│       └── office365.py           # TODO: Microsoft Graph API (OneDrive)
│
├── reports/                       # Генерируемые отчёты (в .gitignore)
├── logs/                          # Журналы сессий (в .gitignore)
└── test_docs/                     # Тестовые документы
```

---

## 🔬 Поддерживаемые форматы

| Формат | Метаданные | EXIF/GPS | Скрытый текст | Угрозы |
|--------|:---------:|:--------:|:-------------:|:------:|
| DOCX   | ✅ | ✅ (из вложений) | ✅ | ✅ |
| PDF    | ✅ | ✅ (из вложений) | — | ✅ |
| PPTX   | ✅ | ✅ (из вложений) | — | ✅ |
| JPG / JPEG | ✅ | ✅ | — | ✅ |
| PNG    | ✅ | — | — | ✅ |
| TIFF   | ✅ | ✅ | — | ✅ |
| BMP    | ✅ | — | — | ✅ |

---

## 📖 Использование

### Консольный режим
```
python main.py
```
```
╔══════════════════════════════════════════════════════════╗
║         Forensic File Metadata Analyzer v2.0             ║
║   Инструмент компьютерной экспертизы, форензики, OSINT   ║
╚══════════════════════════════════════════════════════════╝

  Выберите режим работы:

  1 — 📁 Анализ локальных файлов (DOCX, PDF, PPTX, JPG, PNG...)
  2 — ☁️  Анализ документа Google Drive по ссылке
  3 — 🟡 Анализ документа Яндекс.Диска по ссылке

  Ваш выбор ( 1 - 3 ):
```

### Результаты анализа DOCX
После анализа в папке `reports/` появятся:
- `forensic_report_YYYYMMDD_HHMMSS.html` — HTML-отчёт для эксперта
- `forensic_export_YYYYMMDD_HHMMSS.csv` — таблица для дальнейшей обработки

Лог сессии сохраняется в `logs/YYYY-MM-DD_session.log`.

---

## 🔐 Безопасность

- Токены и credentials **никогда не хранятся в коде** — только в `.env`
- `.gitignore` исключает: `.env`, `credentials.json`, `token.json`, `reports/`, `logs/`
- HTML-отчёт защищён от XSS — все метаданные экранируются через `html.escape()`
- Хэши вычисляются чанковым чтением (64 КБ) — безопасно для больших файлов

---

## 📚 Технологии

| Библиотека | Версия | Назначение |
|-----------|--------|-----------|
| `python-docx` | 1.2.0 | Чтение метаданных DOCX |
| `PyMuPDF` | 1.27.2 | Анализ PDF |
| `python-pptx` | 1.0.2 | Анализ PPTX |
| `Pillow` | 12.1.1 | EXIF, GPS из изображений |
| `google-api-python-client` | 2.192.0 | Google Drive API v3 |
| `yadisk` | 3.4.0 | Яндекс.Диск API |
| `customtkinter` | 5.2.2 | Современный GUI |
| `langdetect` | 1.0.9 | Определение языка |
| `python-dotenv` | 1.2.2 | Загрузка .env |
| `colorama` | 0.4.6 | Цветной вывод в терминале |

---

## 📜 Стандарты и нормативная база

- **ISO/IEC 27037:2012** — руководство по сбору цифровых доказательств
- **RFC 3227** — порядок сбора и хранения цифровых улик
- **FIPS 180-4** — стандарт SHA-256 (NIST)
- **OOXML / ISO 29500** — формат Office Open XML (DOCX)
- **CIPA DC-008-2019** — стандарт EXIF для цифровых камер
- **ФЗ-149** — об информации и информационных технологиях
- **ст. 74.1 УПК РФ** — компьютерная информация как доказательство

---

<div align="center">


</div>
