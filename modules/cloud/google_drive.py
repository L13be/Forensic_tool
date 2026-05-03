import os
import re
from colorama import Fore
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from modules.logger import log_action

SCOPES           = ["https://www.googleapis.com/auth/drive.readonly"]
CREDENTIALS_FILE = os.environ.get("GDRIVE_CREDENTIALS", "credentials.json")
TOKEN_FILE       = os.environ.get("GDRIVE_TOKEN",       "token.json")


def authenticate() -> object:
    """
    Авторизация в Google Drive через OAuth2.
    При первом запуске откроется браузер для входа в аккаунт.
    После входа токен сохраняется в token.json.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    log_action("Авторизация в Google Drive выполнена успешно")
    return build("drive", "v3", credentials=creds)


def extract_file_id(url: str) -> str:
    """
    Извлекает ID документа или папки из ссылки Google Drive.
    Поддерживает форматы:
    - docs.google.com/document/d/ID/edit
    - drive.google.com/file/d/ID/view
    - drive.google.com/drive/folders/ID
    - drive.google.com/open?id=ID
    """
    patterns = [
        r"/folders/([a-zA-Z0-9_-]{25,})",  # ← папки
        r"/d/([a-zA-Z0-9_-]{25,})",         # ← файлы
        r"id=([a-zA-Z0-9_-]{25,})",         # ← open?id=
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def parse_image_metadata(image_meta: dict) -> dict:
    """
    Разбирает imageMediaMetadata из Google Drive API.
    Содержит GPS, модель камеры, время съёмки, параметры съёмки.
    """
    if not image_meta:
        return {}

    result = {}

    result["Ширина (px)"]  = image_meta.get("width",    "—")
    result["Высота (px)"]  = image_meta.get("height",   "—")
    result["Поворот"]      = image_meta.get("rotation", "0")

    result["Модель камеры"]          = image_meta.get("cameraModel",  "—")
    result["Производитель"]          = image_meta.get("cameraMake",   "—")
    result["Время съёмки"]           = image_meta.get("time",         "—")
    result["Выдержка"]               = image_meta.get("exposureTime", "—")
    result["Диафрагма"]              = image_meta.get("aperture",     "—")
    result["ISO"]                    = image_meta.get("isoSpeed",     "—")
    result["Фокусное расстояние"]    = image_meta.get("focalLength",  "—")
    result["Вспышка"]                = "Да" if image_meta.get("flashUsed") else "Нет"

    location = image_meta.get("location", {})
    if location:
        lat = location.get("latitude",  None)
        lon = location.get("longitude", None)
        alt = location.get("altitude",  None)

        if lat and lon:
            result["GPS Широта"]      = lat
            result["GPS Долгота"]     = lon
            result["GPS Высота"]      = alt or "—"
            result["Google Maps"]     = (
                f"https://www.google.com/maps?q={lat},{lon}"
            )
            result["⚠️ GPS ОБНАРУЖЕН"] = (
                f"Координаты: {lat}, {lon} — "
                f"возможно установить место съёмки!"
            )
    else:
        result["GPS"] = "Не обнаружен"

    return result


def analyze_sharing(file: dict) -> dict:
    """
    Анализирует тип публичного доступа к файлу.
    Определяет насколько широко был доступен документ.
    """
    result = {}

    shared       = file.get("shared", False)
    link_share   = file.get("linkShareMetadata", {})
    capabilities = file.get("capabilities", {})

    if not shared:
        result["Тип доступа"] = "🔒 Закрытый — только владелец"
        result["Риск утечки"] = "Низкий"
        result["Описание"]    = "Файл не имеет публичного доступа"
    else:
        security_applied = link_share.get("securityUpdateEnabled", False)
        result["Общий доступ включён"] = "Да"
        result["Обновление безопасности применено"] = (
            "Да" if security_applied else "Нет"
        )

        can_download = capabilities.get("canDownload", False)
        can_copy     = capabilities.get("canCopy",     False)
        can_edit     = capabilities.get("canEdit",     False)
        can_share    = capabilities.get("canShare",    False)

        result["Можно скачать"]          = "Да" if can_download else "Нет"
        result["Можно копировать"]       = "Да" if can_copy     else "Нет"
        result["Можно редактировать"]    = "Да" if can_edit     else "Нет"
        result["Можно расшарить дальше"] = "Да" if can_share    else "Нет"

        if can_edit and can_share:
            result["Тип доступа"] = "🔴 КРИТИЧЕСКИЙ — редактирование и расшаривание"
            result["Риск утечки"] = "Критический"
        elif can_edit:
            result["Тип доступа"] = "🟠 ВЫСОКИЙ — открыто редактирование"
            result["Риск утечки"] = "Высокий"
        elif can_download:
            result["Тип доступа"] = "🟡 СРЕДНИЙ — можно скачать"
            result["Риск утечки"] = "Средний"
        else:
            result["Тип доступа"] = "🟢 НИЗКИЙ — только просмотр"
            result["Риск утечки"] = "Низкий"

    return result


def get_file_metadata(service, file_id: str) -> dict:
    """
    Получает полные метаданные файла через Google Drive API.
    Включает базовые поля, GPS из фото, анализ типа доступа.
    """
    fields = (
        "id, name, mimeType, size, "
        "createdTime, modifiedTime, "
        "owners, lastModifyingUser, "
        "sharingUser, shared, "
        "webViewLink, version, "
        "originalFilename, parents, "
        "trashed, starred, description, "
        "imageMediaMetadata, "
        "videoMediaMetadata, "
        "linkShareMetadata, "
        "capabilities, "
        "exportLinks, "
        "headRevisionId, "
        "spaces"
    )

    file = service.files().get(
        fileId=file_id,
        fields=fields,
        supportsAllDrives=True
    ).execute()

    owners         = file.get("owners", [])
    owner_name     = owners[0].get("displayName",  "Не указан") if owners else "Не указан"
    owner_email    = owners[0].get("emailAddress", "Не указан") if owners else "Не указан"
    last_modifier  = file.get("lastModifyingUser", {})
    modifier_name  = last_modifier.get("displayName",  "Не указан")
    modifier_email = last_modifier.get("emailAddress", "Не указан")
    sharing_user   = file.get("sharingUser", {})
    sharer_name    = sharing_user.get("displayName",  "Не указан")
    sharer_email   = sharing_user.get("emailAddress", "Не указан")

    size     = file.get("size", 0)
    size_str = (
        f"{size} байт ({round(int(size) / 1024, 2)} КБ)"
        if size else "Нет данных (Google Docs формат)"
    )

    spaces     = file.get("spaces", [])
    spaces_str = ", ".join(spaces) if spaces else "—"

    export_links   = file.get("exportLinks", {})
    export_formats = list(export_links.keys()) if export_links else []

    video_meta = file.get("videoMediaMetadata", {})
    video_info = ""
    if video_meta:
        video_info = (
            f"{video_meta.get('width','?')}x"
            f"{video_meta.get('height','?')} px, "
            f"{video_meta.get('durationMillis','?')} мс"
        )

    metadata = {
        # ── ИДЕНТИФИКАЦИЯ ─────────────────────────────────
        "ID документа":         file.get("id",               "—"),
        "Название":             file.get("name",             "—"),
        "Тип файла (MIME)":     file.get("mimeType",         "—"),
        "Оригинальное имя":     file.get("originalFilename", "—"),
        "Размер":               size_str,
        "Версия":               file.get("version",          "—"),
        "ID последней ревизии": file.get("headRevisionId",   "—"),
        "Хранилище":            spaces_str,

        # ── АВТОРСТВО ─────────────────────────────────────
        "Владелец":             owner_name,
        "Email владельца":      owner_email,
        "Последний редактор":   modifier_name,
        "Email редактора":      modifier_email,

        # ── OSINT ─────────────────────────────────────────
        "Поделился (имя)":      sharer_name,
        "Поделился (email)":    sharer_email,

        # ── ВРЕМЕННЫ́Е МЕТКИ ──────────────────────────────
        "Дата создания":        file.get("createdTime",  "—"),
        "Дата изменения":       file.get("modifiedTime", "—"),

        # ── ДОСТУП ────────────────────────────────────────
        "Общий доступ":         "Да" if file.get("shared")  else "Нет",
        "В корзине":            "Да" if file.get("trashed") else "Нет",
        "Избранное":            "Да" if file.get("starred") else "Нет",

        # ── ЭКСПОРТ ───────────────────────────────────────
        "Доступные форматы экспорта": (
            ", ".join(export_formats) if export_formats
            else "Нет (не Google Docs формат)"
        ),

        # ── ВИДЕО ─────────────────────────────────────────
        "Видео параметры":      video_info or "Не видеофайл",

        # ── ССЫЛКИ ────────────────────────────────────────
        "Ссылка на документ":   file.get("webViewLink", "—"),
        "Описание":             file.get("description", "Нет"),
    }

    # Анализ типа публичного доступа
    sharing_analysis = analyze_sharing(file)
    for k, v in sharing_analysis.items():
        metadata[f"[Доступ] {k}"] = v

    # GPS и фото метаданные (если это фото напрямую в Drive)
    image_meta = file.get("imageMediaMetadata", {})
    if image_meta:
        photo_data = parse_image_metadata(image_meta)
        for k, v in photo_data.items():
            metadata[f"[Фото] {k}"] = v

    log_action(
        f"Метаданные Google Drive получены: {metadata['Название']} | "
        f"Владелец: {owner_email} | "
        f"Доступ: {sharing_analysis.get('Тип доступа', '—')} | "
        f"GPS: {'Да' if image_meta and image_meta.get('location') else 'Нет'}"
    )

    return metadata


def get_permissions(service, file_id: str) -> list:
    """
    Получает список всех пользователей у которых есть доступ к документу.
    """
    permissions = []
    try:
        result = service.permissions().list(
            fileId=file_id,
            fields="permissions(id,type,role,emailAddress,displayName)",
            supportsAllDrives=True
        ).execute()

        for perm in result.get("permissions", []):
            permissions.append({
                "Тип":   perm.get("type",         "—"),
                "Роль":  perm.get("role",         "—"),
                "Email": perm.get("emailAddress", "Публичный доступ"),
                "Имя":   perm.get("displayName",  "—"),
            })

        log_action(f"Получены права доступа: {len(permissions)} записей")

    except Exception as e:
        log_action(f"Не удалось получить права доступа: {e}")
        permissions.append({
            "Примечание": f"Недостаточно прав: {e}"
        })

    return permissions

FOLDER_MIME = "application/vnd.google-apps.folder"

def is_folder(service, file_id: str) -> bool:
    """Проверяет является ли ссылка папкой Google Drive"""
    try:
        file = service.files().get(
            fileId=file_id,
            fields="mimeType"
        ).execute()
        return file.get("mimeType") == FOLDER_MIME
    except Exception:
        return False


def list_folder_files(service, folder_id: str) -> list:
    """
    Получает список всех файлов в папке Google Drive.
    Поддерживаемые типы — DOCX, PDF, PPTX, изображения.
    """
    from modules.cloud.file_scanner import DOWNLOADABLE_MIME, EXPORT_MIME
    supported = list(DOWNLOADABLE_MIME.keys()) + list(EXPORT_MIME.keys())

    results  = []
    page_token = None

    print(f"  📂 Сканирование папки...")

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields=(
                "nextPageToken, "
                "files(id, name, mimeType, size, "
                "createdTime, modifiedTime, owners, "
                "lastModifyingUser, shared, webViewLink)"
            ),
            pageToken=page_token,
            supportsAllDrives=True
        ).execute()

        for file in response.get("files", []):
            mime = file.get("mimeType", "")
            if mime in supported:
                results.append(file)
                print(
                    f"     ✅ {file['name']} "
                    f"({mime.split('.')[-1]})"
                )
            elif mime == FOLDER_MIME:
                print(f"     📁 Подпапка пропущена: {file['name']}")
            else:
                print(f"     ⏭️  Пропущен: {file['name']} ({mime})")

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    log_action(
        f"Папка просканирована: найдено {len(results)} поддерживаемых файлов"
    )
    return results


def analyze_google_folder(url: str) -> list:
    """
    Анализирует все файлы в папке Google Drive.
    Возвращает список результатов для каждого файла.
    """
    print("\n  🔐 Авторизация в Google Drive...")
    service = authenticate()

    folder_id = extract_file_id(url)
    if not folder_id:
        return [{"Ошибка": "Не удалось извлечь ID папки из ссылки"}]

    print(f"  📁 ID папки: {folder_id}")
    log_action(f"Анализ папки Google Drive: {folder_id}")

    files = list_folder_files(service, folder_id)

    if not files:
        print(Fore.RED + "  ❌ Поддерживаемых файлов в папке не найдено")
        return []

    print(f"\n  Найдено файлов для анализа: {len(files)}")
    results = []

    for i, file in enumerate(files, 1):
        print(Fore.CYAN + f"\n  [{i}/{len(files)}] {file['name']}")
        result = analyze_google_doc(
            f"https://drive.google.com/file/d/{file['id']}/view"
        )
        results.append(result)

    return results


def analyze_google_doc(url: str) -> dict:
    """
    Главная функция модуля.
    Принимает ссылку на Google Doc → возвращает полный forensic-анализ.
    """
    try:
        print("\n  🔐 Авторизация в Google Drive...")
        service = authenticate()

        file_id = extract_file_id(url)
        if not file_id:
            log_action(f"Не удалось извлечь ID из ссылки: {url}")
            return {"Ошибка": "Не удалось извлечь ID документа из ссылки"}

        print(f"  📄 ID документа: {file_id}")
        log_action(f"Анализ Google Doc: {url} | ID: {file_id}")

        print("  📥 Получение метаданных...")
        metadata = get_file_metadata(service, file_id)

        print("  👥 Получение прав доступа...")
        permissions = get_permissions(service, file_id)
        metadata["Права доступа"] = permissions

        # Сканирование вложенных изображений
        mime_type = metadata.get("Тип файла (MIME)", "")
        filename  = metadata.get("Название", "unknown")

        from modules.cloud.file_scanner import (
            scan_cloud_file, DOWNLOADABLE_MIME, EXPORT_MIME
        )
        scannable = list(DOWNLOADABLE_MIME.keys()) + list(EXPORT_MIME.keys())

        if mime_type in scannable:
            print(f"\n  🖼️  Сканирование вложенных изображений...")
            scan_result = scan_cloud_file(
                service, file_id, mime_type, filename
            )
            metadata["Сканирование файла"] = scan_result

            if scan_result.get("GPS обнаружен"):
                coords = scan_result["Координаты"]
                print(
                    f"\n  🚨 ВНИМАНИЕ: Найдено {len(coords)} "
                    f"изображений с GPS координатами!"
                )
                for c in coords:
                    print(f"     📍 {c['Файл']}: {c['Координаты']}")
                    print(f"     🗺️  {c['Google Maps']}")
        else:
            print(
                f"\n  ⚠️  MIME тип '{mime_type}' "
                f"не поддерживается для сканирования"
            )
            print(f"     Поддерживаемые: {scannable}")

        return metadata

    except Exception as e:
        log_action(f"Критическая ошибка в analyze_google_doc: {e}")
        print(f"\n  ❌ Ошибка: {e}")
        return {"Ошибка": str(e)}