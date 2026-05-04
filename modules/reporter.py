import os
import datetime
import html as _html
from modules.logger import log_action

REPORTS_DIR = "reports"


def _e(value: str) -> str:
    """Экранирует строку для безопасной вставки в HTML-атрибуты и текст."""
    return _html.escape(str(value), quote=True)


def _badges(traces: int, anomalies: int) -> str:
    parts = []
    if anomalies == 0:
        parts.append("<span class='badge badge-ok'>✓ Аномалий нет</span>")
    elif anomalies <= 3:
        parts.append(f"<span class='badge badge-warn'>⚠ {anomalies} аномалии</span>")
    else:
        parts.append(f"<span class='badge badge-crit'>🔴 {anomalies} аномалий</span>")
    if traces > 0:
        parts.append(f"<span class='badge badge-trace'>🔵 {traces} следов</span>")
    return " ".join(parts)


def _field(label: str, value: str, cls: str = "") -> str:
    if not value or value in ("—", "Нет", "Не указан", "Не видеофайл",
                               "Нет (не Google Docs формат)"):
        return ""
    # label — статическая строка из кода, value — данные из документа
    safe_value = _e(value) if not value.startswith("<") else value
    return f"""
        <div class="field">
            <span class="field-label">{_e(label)}</span>
            <span class="field-value {_e(cls)}">{safe_value}</span>
        </div>"""


def _build_images_detail(images: list, index: str) -> tuple:
    """
    Строит раскрывающийся блок деталей изображений.
    Возвращает (images_summary_html, images_detail_html, all_traces, coords, devices)
    """
    all_traces = []
    coords     = []
    devices    = []
    gps_found  = False

    for img in images:
        for t in img.get("Следы",    []): all_traces.append(t)
        gps = img.get("GPS", {})
        if gps.get("Координаты"):
            gps_found = True
            coords.append({
                "Файл":        img["Файл"],
                "Координаты":  gps["Координаты"],
                "Google Maps": gps.get("Google Maps", ""),
                "Yandex Maps": gps.get("Yandex Maps", ""),
                "Высота":      gps.get("Высота над уровнем моря", "—"),
                "Скорость":    gps.get("Скорость", "—"),
                "Время GPS":   gps.get("Время GPS (UTC)", "—"),
            })
        device = img.get("Камера", {}).get("Устройство", "")
        if device and device not in devices:
            devices.append(device)

    img_count = len(images)

    gps_blocks = ""
    for coord in coords:
        speed_html = (
            f'<span class="small" style="margin-left:8px">🚗 {_e(coord["Скорость"])}</span>'
            if coord.get("Скорость", "—") != "—" else ""
        )
        gps_time_html = (
            f'<span class="small" style="margin-left:8px">🕐 {_e(coord["Время GPS"])}</span>'
            if coord.get("Время GPS", "—") != "—" else ""
        )
        gps_blocks += f"""
            <div class="gps-alert">
                <div class="gps-title">📍 GPS в файле: {_e(coord['Файл'])}</div>
                <div class="gps-coords">{_e(coord['Координаты'])}</div>
                <div style="margin-top:6px">
                    <a href="{_e(coord['Google Maps'])}" target="_blank" class="btn-link">🗺️ Google Maps</a>
                    <a href="{_e(coord.get('Yandex Maps','#'))}" target="_blank" class="btn-link">🗺️ Яндекс</a>
                    {speed_html}
                    {gps_time_html}
                </div>
            </div>"""

    images_summary = f"""
    <div class="card-section">
        <div class="section-header">
            🖼️ Изображения
            <span class="img-count">{img_count} шт.</span>
            {'<span class="badge badge-crit">📍 GPS</span>' if gps_found else '<span class="badge badge-ok">GPS нет</span>'}
        </div>
        <div class="img-summary-grid">
            <div class="img-stat"><b>{img_count}</b><span>изображений</span></div>
            <div class="img-stat"><b class="{'anomaly' if gps_found else 'ok'}">{len(coords)}</b><span>с GPS</span></div>
            <div class="img-stat"><b class="{'warn' if devices else ''}">{len(devices)}</b><span>устройств</span></div>
            <div class="img-stat"><b class="trace">{len(all_traces)}</b><span>следов</span></div>
        </div>
        {f'<div class="devices-list">📱 {", ".join(devices)}</div>' if devices else ""}
        {gps_blocks}
    </div>"""

    # Детальные карточки изображений
    img_cards = ""
    for img in images:
        if "Ошибка" in img or "Примечание" in img:
            note = img.get("Примечание", img.get("Ошибка", ""))
            img_cards += f"""
                <div class="img-mini-card">
                    <div class="img-mini-name">{img.get('Файл','—')}</div>
                    <div class="small warn">{note}</div>
                </div>"""
            continue

        camera = img.get("Камера", {})
        times  = img.get("Временные метки", {})
        soft   = img.get("Программное обеспечение", {})
        gps    = img.get("GPS", {})
        base   = img.get("Основное", {})
        следы  = img.get("Следы", [])
        аном   = img.get("Аномалии", [])

        gps_html = ""
        if gps.get("Координаты"):
            alt_html = (
                f'&nbsp;| Высота: {_e(gps.get("Высота над уровнем моря",""))}'
                if gps.get("Высота над уровнем моря") else ""
            )
            gps_html = f"""
                <div class="img-gps">
                    📍 {_e(gps['Координаты'])}<br>
                    <a href="{_e(gps['Google Maps'])}" target="_blank" class="btn-link">Google Maps</a>
                    {alt_html}
                </div>"""

        traces_html = ""
        if следы:
            items = "".join(f"<li>{_e(t)}</li>" for t in следы)
            traces_html = f"""
                <div class="img-block-title trace">🔵 Следы файла</div>
                <ul class="img-traces-list">{items}</ul>"""

        anom_html = ""
        if аном:
            items = "".join(f"<li>{_e(a)}</li>" for a in аном)
            anom_html = f"""
                <div class="img-block-title anomaly">⚠️ Аномалии</div>
                <ul class="img-anomalies">{items}</ul>"""

        img_cards += f"""
            <div class="img-mini-card">
                <div class="img-mini-name">
                    🖼️ {_e(img.get('Файл','—'))}
                    <span class="small">{_e(img.get('Источник','—'))}</span>
                </div>
                <div class="img-mini-grid">
                    <div>{_field("Разрешение", base.get("Разрешение",""))}</div>
                    <div>{_field("Размер", base.get("Размер файла",""))}</div>
                    <div>{_field("Устройство", camera.get("Устройство",""), "trace")}</div>
                    <div>{_field("Серийный №", camera.get("Серийный номер камеры",""), "trace")}</div>
                    <div>{_field("Дата съёмки", times.get("Дата и время съёмки",""))}</div>
                    <div>{_field("Часовой пояс", times.get("Часовой пояс съёмки",""), "trace")}</div>
                    <div>{_field("ПО обработки", soft.get("ПО обработки",""))}</div>
                    <div>{_field("Artist", soft.get("Автор (Artist)",""), "trace")}</div>
                </div>
                {gps_html}
                {traces_html}
                {anom_html}
            </div>"""

    images_detail = ""
    if img_cards:
        images_detail = f"""
        <div class="collapsible" id="imgs-{index}">
            <button class="collapse-btn" onclick="toggle('imgs-{index}')">
                🖼️ Детали изображений ({img_count} шт.) ▼
            </button>
            <div class="collapse-body" style="display:none">
                {img_cards}
            </div>
        </div>"""

    return images_summary, images_detail, all_traces, coords, devices


def _build_image_card(meta: dict, anomalies: list, images: list, index: int, scan_result: dict = None) -> str:
    """Строит карточку для автономного изображения (JPG/PNG/TIFF/BMP) с полным EXIF."""
    fname  = meta.get("Файл", "—")
    fpath  = meta.get("Полный путь", "")
    fsize  = meta.get("Размер", "—")
    md5    = meta.get("MD5", "—")
    sha256 = str(meta.get("SHA256", "—"))

    total_traces = sum(len(img.get("Следы", [])) for img in images) if images else 0
    badge = _badges(total_traces, len(anomalies))

    # ── СЕКЦИЯ: ФАЙЛ ─────────────────────────────────────
    file_section = f"""
        <div class="card-section">
            <div class="section-header">📄 Файл</div>
            {_field("Имя файла", fname)}
            {_field("Путь", f'<span class="small">{_e(fpath)}</span>')}
            {_field("Размер", fsize)}
            {_field("Формат", meta.get("Формат", ""))}
            {_field("Разрешение", meta.get("Разрешение", ""))}
            {_field("MD5", f'<code class="hash">{md5}</code>')}
            {_field("SHA256", f'<code class="hash">{sha256[:40]}...</code>' if len(sha256) > 40 else f'<code class="hash">{sha256}</code>')}
        </div>"""

    # ── СЕКЦИЯ: КАМЕРА ────────────────────────────────────
    camera_section = f"""
        <div class="card-section">
            <div class="section-header">📷 Камера</div>
            {_field("Устройство", meta.get("Устройство", ""), "trace")}
            {_field("Производитель", meta.get("Производитель", ""))}
            {_field("Модель", meta.get("Модель камеры", ""))}
            {_field("Серийный №", meta.get("Серийный номер камеры", ""), "anomaly" if meta.get("Серийный номер камеры") else "")}
            {_field("Объектив", meta.get("Объектив", ""))}
        </div>"""

    # ── СЕКЦИЯ: ПАРАМЕТРЫ СЪЁМКИ ─────────────────────────
    shoot_section = f"""
        <div class="card-section">
            <div class="section-header">🎯 Параметры съёмки</div>
            {_field("ISO", meta.get("ISO", ""))}
            {_field("Диафрагма", meta.get("Диафрагма", ""))}
            {_field("Выдержка", meta.get("Выдержка", ""))}
            {_field("Фокусное расст.", meta.get("Фокусное расстояние", ""))}
            {_field("Вспышка", meta.get("Вспышка", ""))}
        </div>"""

    # ── СЕКЦИЯ: ВРЕМЕННЫЕ МЕТКИ ──────────────────────────
    time_section = f"""
        <div class="card-section">
            <div class="section-header">📅 Временные метки</div>
            {_field("Дата съёмки", meta.get("Дата создания", ""), "warn" if meta.get("Дата создания") else "")}
            {_field("Оцифровка", meta.get("Дата оцифровки", ""))}
            {_field("Изменение файла", meta.get("Дата изменения", ""))}
            {_field("Часовой пояс", meta.get("Часовой пояс", ""), "trace" if meta.get("Часовой пояс") else "")}
        </div>"""

    # ── СЕКЦИЯ: ПО И АВТОРСТВО ────────────────────────────
    soft_section = f"""
        <div class="card-section">
            <div class="section-header">💻 ПО и авторство</div>
            {_field("ПО обработки", meta.get("ПО обработки", ""), "warn" if meta.get("ПО обработки") else "")}
            {_field("Artist", meta.get("Автор (Artist)", ""), "trace" if meta.get("Автор (Artist)") else "")}
            {_field("Авторские права", meta.get("Авторские права", ""))}
        </div>"""

    # ── СЕКЦИЯ: GPS ────────────────────────────────────────
    gps_coords = meta.get("GPS Координаты", "")
    maps_link  = meta.get("Google Maps", "")
    gps_link_html = (
        f'<div style="margin-top:6px"><a href="{_e(maps_link)}" target="_blank" class="btn-link">🗺️ Google Maps</a></div>'
        if maps_link else ""
    )
    if gps_coords:
        gps_section = f"""
        <div class="card-section">
            <div class="section-header">📍 GPS</div>
            {_field("Координаты", gps_coords, "anomaly")}
            {_field("Высота", meta.get("GPS Высота", ""))}
            {_field("Скорость", meta.get("GPS Скорость", ""), "warn" if meta.get("GPS Скорость") else "")}
            {_field("Время GPS", meta.get("GPS Время", ""))}
            {gps_link_html}
        </div>"""
    else:
        gps_section = """
        <div class="card-section">
            <div class="section-header">📍 GPS</div>
            <div class="ok" style="padding:8px;font-size:11px">✅ GPS не обнаружен</div>
        </div>"""

    # ── СЕКЦИЯ: БЕЗОПАСНОСТЬ ─────────────────────────────
    security_section = ""
    if scan_result:
        risk     = scan_result.get("Риск", "—")
        findings = scan_result.get("Находки", [])
        red      = scan_result.get("Красных", 0)
        yellow   = scan_result.get("Жёлтых", 0)
        risk_cls = "anomaly" if red > 0 else "warn" if yellow > 0 else "ok"
        findings_html = "".join(
            f"<div class='scan-finding {'anomaly' if '🔴' in f else 'warn'}'>{_e(f)}</div>"
            for f in findings
        )
        security_section = f"""
            <div class="card-section">
                <div class="section-header">🛡️ Безопасность</div>
                {_field("Риск", risk, risk_cls)}
                {f'<div style="margin-top:8px">{findings_html}</div>' if findings_html else ""}
            </div>"""

    # ── СЛЕДЫ EXIF (раскрывающийся) ──────────────────────
    traces_detail = ""
    makernotes_detail = ""
    if images:
        exif_data = images[0]
        exif_traces = exif_data.get("Следы", [])
        if exif_traces:
            items = "".join(f"<li>{_e(t)}</li>" for t in exif_traces)
            traces_detail = f"""
        <div class="collapsible" id="traces-img-{index}">
            <button class="collapse-btn" onclick="toggle('traces-img-{index}')">
                🔵 Следы EXIF ({len(exif_traces)} шт.) ▼
            </button>
            <div class="collapse-body" style="display:none">
                <ul class="img-traces-list" style="column-count:2;column-gap:20px">
                    {items}
                </ul>
            </div>
        </div>"""

        # ── MakerNotes (раскрывающийся) ──────────────────
        makernotes = exif_data.get("MakerNotes", {})
        if makernotes:
            mn_rows = "".join(
                f"""<tr>
                    <td style="padding:3px 8px;color:var(--text3);font-size:10px;
                               white-space:nowrap;border-bottom:1px solid var(--border)">{_e(k)}</td>
                    <td style="padding:3px 8px;color:var(--text);font-size:10px;
                               word-break:break-all;border-bottom:1px solid var(--border)">{_e(v)}</td>
                </tr>"""
                for k, v in makernotes.items()
            )
            total_tags = exif_data.get("Основное", {}).get("Тегов EXIF (exifread)", "")
            header_extra = f" &nbsp;·&nbsp; {_e(total_tags)} тегов всего" if total_tags else ""
            makernotes_detail = f"""
        <div class="collapsible" id="mn-img-{index}">
            <button class="collapse-btn" onclick="toggle('mn-img-{index}')">
                🔬 MakerNotes — проприетарные теги ({len(makernotes)} шт.){header_extra} ▼
            </button>
            <div class="collapse-body" style="display:none">
                <div style="font-size:10px;color:var(--text3);margin-bottom:8px;padding:6px 8px;
                            background:rgba(77,158,255,.06);border-radius:4px;border-left:2px solid var(--blue2)">
                    MakerNotes — проприетарный блок EXIF (IFD4), который каждый производитель
                    (Canon, Nikon, Sony, Apple…) заполняет по собственному формату.
                    Содержит данные, недоступные через стандартный парсинг.
                </div>
                <table style="width:100%;border-collapse:collapse">
                    <thead>
                        <tr>
                            <th style="text-align:left;padding:4px 8px;font-size:9px;
                                       text-transform:uppercase;letter-spacing:1px;
                                       color:var(--text3);border-bottom:1px solid var(--border2)">Тег</th>
                            <th style="text-align:left;padding:4px 8px;font-size:9px;
                                       text-transform:uppercase;letter-spacing:1px;
                                       color:var(--text3);border-bottom:1px solid var(--border2)">Значение</th>
                        </tr>
                    </thead>
                    <tbody>{mn_rows}</tbody>
                </table>
            </div>
        </div>"""

    # ── АНОМАЛИИ ─────────────────────────────────────────
    if anomalies:
        items = "".join(f"<li>{_e(a)}</li>" for a in anomalies)
        anomaly_section = f"""
        <div class="bottom-section anomaly-section">
            <div class="bottom-header anomaly">⚠️ Аномалии ({len(anomalies)})</div>
            <ul class="anomaly-list">{items}</ul>
        </div>"""
    else:
        anomaly_section = """
        <div class="bottom-section">
            <div class="ok" style="padding:8px">✅ Аномалий не обнаружено</div>
        </div>"""

    return f"""
    <div class="doc-card">
        <div class="card-header">
            <div class="card-title">
                <span class="doc-icon">🖼️</span>
                <span class="doc-name">{_e(fname)}</span>
            </div>
            <div class="card-badges">{badge}
                {'<span class="badge badge-crit">📍 GPS</span>' if gps_coords else ""}
            </div>
        </div>
        <div class="card-grid">
            {file_section}
            {camera_section}
            {shoot_section}
            {time_section}
            {soft_section}
            {gps_section}
            {security_section}
        </div>
        {traces_detail}
        {makernotes_detail}
        {anomaly_section}
    </div>"""


def _build_local_card(meta: dict, anomalies: list, images: list, index: int, scan_result: dict = None, hidden_result: dict = None) -> str:
    """Строит карточку локального файла в том же стиле что и Google Drive"""
    fname    = meta.get("Файл", "—")
    fpath    = meta.get("Полный путь", "")
    author   = meta.get("Автор", "—")
    editor   = meta.get("Последний редактор", "—")
    org      = meta.get("Организация", "—")
    manager  = meta.get("Менеджер", "—")
    created  = meta.get("Дата создания", "—")
    modified = meta.get("Дата изменения", "—")
    edit_time= meta.get("Время редактирования", "—")
    revision = meta.get("Номер редакции", "—")
    app      = meta.get("Приложение", "—")
    app_ver  = meta.get("Версия приложения", "—")
    template = meta.get("Шаблон документа", "—")
    title    = meta.get("Название", "—")
    subject  = meta.get("Тема", "—")
    category = meta.get("Категория", "—")
    keywords = meta.get("Ключевые слова", "—")
    comment  = meta.get("Комментарий", "—")
    language = meta.get("Язык", "—")
    pages    = meta.get("Страниц", "—")
    words    = meta.get("Слов", "—")
    paragraphs = meta.get("Абзацев", "—")
    lines    = meta.get("Строк", "—")
    chars    = meta.get("Символов", "—")
    protect  = meta.get("Защита документа", "0")
    shared   = meta.get("Общий документ", "—")
    fsize    = meta.get("Размер файла", "—")
    md5      = meta.get("MD5", "—")
    sha256   = str(meta.get("SHA256", "—"))

    total_traces = 0
    if images:
        for img in images:
            total_traces += len(img.get("Следы", []))

    badge = _badges(total_traces, len(anomalies))

    # Изображения
    images_summary = ""
    images_detail  = ""
    if images:
        images_summary, images_detail, all_traces, coords, devices = \
            _build_images_detail(images, f"local-{index}")

    # ── СЕКЦИЯ: ФАЙЛ ─────────────────────────────────────
    file_section = f"""
        <div class="card-section">
            <div class="section-header">📄 Файл</div>
            {_field("Имя файла", fname)}
            {_field("Путь", f'<span class="small">{fpath}</span>')}
            {_field("Размер", fsize)}
            {_field("Дата создания", created)}
            {_field("Дата изменения", modified)}
            {_field("Время редактирования", edit_time, "warn" if edit_time not in ("—","Нет данных") else "")}
            {_field("Редакция №", str(revision))}
            {_field("MD5", f'<code class="hash">{md5}</code>')}
            {_field("SHA256", f'<code class="hash">{sha256[:40]}...</code>' if len(sha256) > 40 else f'<code class="hash">{sha256}</code>')}
        </div>"""

    # ── СЕКЦИЯ: АВТОРСТВО ────────────────────────────────
    author_section = f"""
        <div class="card-section">
            <div class="section-header">👤 Авторство</div>
            {_field("Автор", author, "warn" if author not in ("—","Не указан") else "")}
            {_field("Последний редактор", editor, "warn" if editor != author and editor not in ("—","Не указан") else "")}
            {_field("Организация", org, "trace" if org not in ("—","Не указана","Не указан") else "")}
            {_field("Менеджер", manager, "trace" if manager not in ("—","Не указан") else "")}
            {_field("Язык", language)}
        </div>"""

    # ── СЕКЦИЯ: ПРИЛОЖЕНИЕ ───────────────────────────────
    protect_cls = "anomaly" if protect not in ("0","Нет данных","—") else "ok"
    shared_cls  = "anomaly" if shared == "true" else ""

    app_section = f"""
        <div class="card-section">
            <div class="section-header">💻 Приложение</div>
            {_field("Приложение", app)}
            {_field("Версия", app_ver)}
            {_field("Шаблон", template, "warn" if template not in ("—","Не указан","Normal.dotm","Normal") else "")}
            {_field("Защита", protect, protect_cls)}
            {_field("Общий документ", shared, shared_cls)}
        </div>"""

    # ── СЕКЦИЯ: СОДЕРЖИМОЕ ───────────────────────────────
    content_section = f"""
        <div class="card-section">
            <div class="section-header">📝 Содержимое</div>
            {_field("Название", title)}
            {_field("Тема", subject)}
            {_field("Категория", category)}
            {_field("Ключевые слова", keywords, "trace" if keywords not in ("—","Не указаны") else "")}
            {_field("Комментарий", comment, "warn" if comment not in ("—","Нет") else "")}
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
                <div class="field-label" style="margin-bottom:6px">Статистика</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
                    {_field("Страниц", str(pages))}
                    {_field("Слов", str(words))}
                    {_field("Абзацев", str(paragraphs))}
                    {_field("Строк", str(lines))}
                    {_field("Символов", str(chars))}
                </div>
            </div>
        </div>"""

    # ── СЕКЦИЯ: СКРЫТЫЙ ТЕКСТ ────────────────────────────
    hidden_section = ""
    if hidden_result and hidden_result.get("Скрытых фрагментов", 0) > 0:
        fragments = hidden_result.get("Скрытый текст", [])
        hidden_anoms = hidden_result.get("Аномалии", [])

        fragments_html = ""
        for f in fragments:
            raw_text    = f.get("Скрытый текст", "")
            text_preview = _e(raw_text[:150]) + ("..." if len(raw_text) > 150 else "")
            context = _e(f.get("Контекст", ""))
            tip     = _e(f.get("Тип сокрытия", ""))

            fragments_html += f"""
                    <div style="margin-bottom:8px;padding:6px 8px;
                                background:rgba(255,77,106,.06);
                                border:1px solid rgba(255,77,106,.2);
                                border-radius:4px">
                        <div style="font-size:9px;color:var(--text3);margin-bottom:3px">
                            Параграф №{_e(str(f.get('Параграф №', '—')))} &nbsp;·&nbsp;
                            <span class="warn">{tip}</span> &nbsp;·&nbsp;
                            {_e(str(f.get('Длина (симв.)', '—')))} символов
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;
                                    font-size:10px;color:var(--red);
                                    word-break:break-all;margin-bottom:3px">
                            {text_preview}
                        </div>
                        {f'<div style="font-size:9px;color:var(--text3)">Контекст: {context}</div>' if context else ''}
                    </div>"""

        anoms_html = ""
        for a in hidden_anoms:
            cls = "anomaly" if "🔴" in a else "warn"
            anoms_html += f"<div class='scan-finding {cls}' style='margin-top:4px'>{_e(a)}</div>"

        hidden_section = f"""
                <div class="card-section">
                    <div class="section-header">👁️ Скрытый текст
                        <span class="badge badge-crit" style="margin-left:auto">
                            {hidden_result['Скрытых фрагментов']} фрагм.
                        </span>
                    </div>
                    {fragments_html}
                    {anoms_html}
                </div>"""

    # ── СЕКЦИЯ: БЕЗОПАСНОСТЬ (вирусное сканирование) ─────
    security_section = ""
    if scan_result:
        risk = scan_result.get("Риск", "—")
        findings = scan_result.get("Находки", [])
        red = scan_result.get("Красных", 0)
        yellow = scan_result.get("Жёлтых", 0)

        risk_cls = "anomaly" if red > 0 else "warn" if yellow > 0 else "ok"

        findings_html = ""
        for f in findings:
            cls = "anomaly" if "🔴" in f else "warn"
            findings_html += f"<div class='scan-finding {cls}'>{_e(f)}</div>"

        security_section = f"""
                    <div class="card-section">
                        <div class="section-header">🛡️ Безопасность</div>
                        {_field("Риск", risk, risk_cls)}
                        {f'<div style="margin-top:8px">{findings_html}</div>' if findings_html else ""}
                    </div>"""



    # ── СЕТКА ────────────────────────────────────────────
    grid = f"""
            <div class="card-grid">
                {file_section}
                {author_section}
                {app_section}
                {content_section}
                {hidden_section}
                {security_section}
                {images_summary}
            </div>"""

    # ── АНОМАЛИИ ─────────────────────────────────────────
    anomaly_section = ""
    if anomalies:
        items = "".join(f"<li>{_e(a)}</li>" for a in anomalies)
        anomaly_section = f"""
        <div class="bottom-section anomaly-section">
            <div class="bottom-header anomaly">⚠️ Аномалии ({len(anomalies)})</div>
            <ul class="anomaly-list">{items}</ul>
        </div>"""
    else:
        anomaly_section = """
        <div class="bottom-section">
            <div class="ok" style="padding:8px">✅ Аномалий не обнаружено</div>
        </div>"""

    return f"""
    <div class="doc-card">
        <div class="card-header">
            <div class="card-title">
                <span class="doc-icon">📁</span>
                <span class="doc-name">{_e(fname)}</span>
            </div>
            <div class="card-badges">{badge}</div>
        </div>
        {grid}
        {images_detail}
        {anomaly_section}
    </div>"""

def _build_doc_card(g: dict, index: int) -> str:
    name         = g.get("Название", "—")
    mime         = g.get("Тип файла (MIME)", "—")
    doc_id       = g.get("ID документа", "—")
    size         = g.get("Размер", "—")
    version      = g.get("Версия", "—")
    rev_id       = g.get("ID последней ревизии", "—")
    link         = g.get("Ссылка на документ", "#")
    storage      = g.get("Хранилище", "—")
    owner_name   = g.get("Владелец", "—")
    owner_email  = g.get("Email владельца", "—")
    editor_name  = g.get("Последний редактор", "—")
    editor_email = g.get("Email редактора", "—")
    sharer_name  = g.get("Поделился (имя)", "—")
    sharer_email = g.get("Поделился (email)", "—")
    created      = g.get("Дата создания", "—")
    modified     = g.get("Дата изменения", "—")
    shared       = g.get("Общий доступ", "Нет")
    trashed      = g.get("В корзине", "Нет")
    access_type  = g.get("[Доступ] Тип доступа", "—")
    access_risk  = g.get("[Доступ] Риск утечки", "—")
    can_download = g.get("[Доступ] Можно скачать", "—")
    can_edit     = g.get("[Доступ] Можно редактировать", "—")
    can_share    = g.get("[Доступ] Можно расшарить дальше", "—")
    can_copy     = g.get("[Доступ] Можно копировать", "—")
    perms        = g.get("Права доступа", [])
    scan         = g.get("Сканирование файла", {})

    all_traces    = []
    all_anomalies = []
    if scan:
        all_traces    = scan.get("Все следы",    [])
        all_anomalies = scan.get("Все аномалии", [])
    if trashed == "Да":
        all_anomalies.append("Файл находится в корзине")

    badge    = _badges(len(all_traces), len(all_anomalies))
    risk_cls = ("anomaly" if "Критический" in access_risk
                else "warn" if "Высокий" in access_risk else "ok")

    doc_section = f"""
        <div class="card-section">
            <div class="section-header">📄 Документ</div>
            {_field("ID", f'<code>{doc_id[:40]}...</code>' if len(doc_id)>40 else f'<code>{doc_id}</code>')}
            {_field("MIME тип", f'<code>{mime}</code>')}
            {_field("Размер", size)}
            {_field("Версия", version)}
            {_field("ID ревизии", f'<code class="small-code">{rev_id[:35]}...</code>' if len(rev_id)>35 else f'<code>{rev_id}</code>')}
            {_field("Хранилище", storage)}
            {_field("Дата создания", created)}
            {_field("Дата изменения", modified)}
            {_field("В корзине", trashed, "anomaly" if trashed=="Да" else "")}
            {_field("MD5 (Яндекс)", g.get("MD5 (Яндекс)", ""))}
            {_field("SHA256 (Яндекс)", g.get("SHA256 (Яндекс)", ""))}
            {_field("Владелец (логин)", g.get("Владелец (логин)", ""), "trace" if g.get("Владелец (логин)","—") != "—" else "")}
        </div>"""

    osint_section = f"""
            <div class="card-section">
                <div class="section-header">👤 Авторство & OSINT</div>
                {_field("Владелец", owner_name)}
                {_field("Email владельца", f'<a href="mailto:{owner_email}" class="email-link">{owner_email}</a>')}
                {_field("Последний редактор", editor_name)}
                {_field("Email редактора", f'<a href="mailto:{editor_email}" class="email-link">{editor_email}</a>')}
                {_field("Поделился (имя)", sharer_name, "warn" if sharer_name not in ("—", "Не указан") else "")}
                {_field("Поделился (email)", sharer_email, "warn" if sharer_email not in ("—", "Не указан") else "")}
            </div>"""

    perm_rows = ""
    for p in perms:
        if "Примечание" in p:
            perm_rows += "<div class='perm-row warn'>⚠️ Недостаточно прав</div>"
        else:
            role_cls   = "anomaly" if p.get("Роль") in ("writer","owner") else "ok"
            perm_rows += f"""
                <div class='perm-row'>
                    <span class='{role_cls}'>{p.get("Роль","—")}</span>
                    <span>{p.get("Тип","—")}</span>
                    <span class='small'>{p.get("Email","—")}</span>
                </div>"""

    security_section = f"""
        <div class="card-section">
            <div class="section-header">🔐 Безопасность</div>
            {_field("Общий доступ", shared, "anomaly" if shared=="Да" else "ok")}
            {_field("Тип доступа", access_type, risk_cls)}
            {_field("Риск утечки", access_risk, risk_cls)}
            {_field("Можно скачать", can_download, "warn" if can_download=="Да" else "")}
            {_field("Можно редактировать", can_edit, "anomaly" if can_edit=="Да" else "")}
            {_field("Можно копировать", can_copy, "warn" if can_copy=="Да" else "")}
            {_field("Можно расшарить", can_share, "anomaly" if can_share=="Да" else "")}
            <div class="perm-list">
                <div class="field-label" style="margin-bottom:6px">Права доступа ({len(perms)}):</div>
                {perm_rows if perm_rows else '<div class="small">Нет данных</div>'}
            </div>
        </div>"""

    # Скрытый текст из Google Drive DOCX
    hidden_gdrive_section = ""
    scan_hidden = scan.get("Скрытый текст", {}) if scan else {}
    if scan_hidden and scan_hidden.get("Скрытых фрагментов", 0) > 0:
        fragments = scan_hidden.get("Скрытый текст", [])
        hidden_anoms = scan_hidden.get("Аномалии", [])

        fragments_html = ""
        for f in fragments:
            text_preview = f.get("Скрытый текст", "")[:150]
            if len(f.get("Скрытый текст", "")) > 150:
                text_preview += "..."
            fragments_html += f"""
                    <div style="margin-bottom:8px;padding:6px 8px;
                                background:rgba(255,77,106,.06);
                                border:1px solid rgba(255,77,106,.2);
                                border-radius:4px">
                        <div style="font-size:9px;color:var(--text3);margin-bottom:3px">
                            Параграф №{f.get('Параграф №', '—')} &nbsp;·&nbsp;
                            <span class="warn">{f.get('Тип сокрытия', '—')}</span> &nbsp;·&nbsp;
                            {f.get('Длина (симв.)', '—')} символов
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;
                                    font-size:10px;color:var(--red);
                                    word-break:break-all">
                            {text_preview}
                        </div>
                    </div>"""

        anoms_html = ""
        for a in hidden_anoms:
            cls = "anomaly" if "🔴" in a else "warn"
            anoms_html += f"<div class='scan-finding {cls}'>{a}</div>"

        hidden_gdrive_section = f"""
                <div class="card-section">
                    <div class="section-header">👁️ Скрытый текст
                        <span class="badge badge-crit" style="margin-left:auto">
                            {scan_hidden['Скрытых фрагментов']} фрагм.
                        </span>
                    </div>
                    {fragments_html}
                    {anoms_html}
                </div>"""

    images_summary = ""
    images_detail  = ""
    if scan:
        img_count   = scan.get("Изображений найдено", 0)
        gps_found   = scan.get("GPS обнаружен", False)
        devices     = scan.get("Устройства", [])
        coords      = scan.get("Координаты", [])
        scan_status = scan.get("Статус скачивания", "—")

        gps_blocks = ""
        for coord in coords:
            gps_blocks += f"""
                <div class="gps-alert">
                    <div class="gps-title">📍 GPS в файле: {coord['Файл']}</div>
                    <div class="gps-coords">{coord['Координаты']}</div>
                    <div style="margin-top:6px">
                        <a href="{coord['Google Maps']}" target="_blank" class="btn-link">🗺️ Google Maps</a>
                        <a href="{coord.get('Yandex Maps','#')}" target="_blank" class="btn-link">🗺️ Яндекс</a>
                        {f'<span class="small" style="margin-left:8px">🚗 {coord["Скорость"]}</span>' if coord.get("Скорость","—")!="—" else ""}
                        {f'<span class="small" style="margin-left:8px">🕐 {coord["Время GPS"]}</span>' if coord.get("Время GPS","—")!="—" else ""}
                    </div>
                </div>"""

        images_summary = f"""
        <div class="card-section">
            <div class="section-header">
                🖼️ Изображения
                <span class="img-count">{img_count} шт.</span>
                {'<span class="badge badge-crit">📍 GPS</span>' if gps_found else '<span class="badge badge-ok">GPS нет</span>'}
            </div>
            <div class="img-summary-grid">
                <div class="img-stat"><b>{img_count}</b><span>изображений</span></div>
                <div class="img-stat"><b class="{'anomaly' if gps_found else 'ok'}">{len(coords)}</b><span>с GPS</span></div>
                <div class="img-stat"><b class="{'warn' if devices else ''}">{len(devices)}</b><span>устройств</span></div>
                <div class="img-stat"><b class="trace">{len(all_traces)}</b><span>следов</span></div>
            </div>
            {f'<div class="devices-list">📱 {", ".join(devices)}</div>' if devices else ""}
            {gps_blocks}
            <div style="margin-top:8px"><span class="small">Статус: {scan_status}</span></div>
        </div>"""

        img_cards = ""
        for img in scan.get("Изображения", []):
            if "Ошибка" in img or "Примечание" in img:
                note = img.get("Примечание", img.get("Ошибка",""))
                img_cards += f"""
                    <div class="img-mini-card">
                        <div class="img-mini-name">{img.get('Файл','—')}</div>
                        <div class="small warn">{note}</div>
                    </div>"""
                continue

            camera = img.get("Камера", {})
            times  = img.get("Временные метки", {})
            soft   = img.get("Программное обеспечение", {})
            gps    = img.get("GPS", {})
            base   = img.get("Основное", {})
            следы  = img.get("Следы", [])
            аном   = img.get("Аномалии", [])

            gps_html = ""
            if gps.get("Координаты"):
                gps_html = f"""
                    <div class="img-gps">
                        📍 {gps['Координаты']}<br>
                        <a href="{gps['Google Maps']}" target="_blank" class="btn-link">Google Maps</a>
                        {f'&nbsp;| Высота: {gps.get("Высота над уровнем моря","")}' if gps.get("Высота над уровнем моря") else ""}
                    </div>"""

            traces_html = ""
            if следы:
                items = "".join(f"<li>{t}</li>" for t in следы)
                traces_html = f"""
                    <div class="img-block-title trace">🔵 Следы файла</div>
                    <ul class="img-traces-list">{items}</ul>"""

            anom_html = ""
            if аном:
                items = "".join(f"<li>{a}</li>" for a in аном)
                anom_html = f"""
                    <div class="img-block-title anomaly">⚠️ Аномалии</div>
                    <ul class="img-anomalies">{items}</ul>"""

            img_cards += f"""
                <div class="img-mini-card">
                    <div class="img-mini-name">
                        🖼️ {img.get('Файл','—')}
                        <span class="small">{img.get('Источник','—')}</span>
                    </div>
                    <div class="img-mini-grid">
                        <div>{_field("Разрешение", base.get("Разрешение",""))}</div>
                        <div>{_field("Размер", base.get("Размер файла",""))}</div>
                        <div>{_field("Устройство", camera.get("Устройство",""), "trace")}</div>
                        <div>{_field("Серийный №", camera.get("Серийный номер камеры",""), "trace")}</div>
                        <div>{_field("Дата съёмки", times.get("Дата и время съёмки",""))}</div>
                        <div>{_field("Часовой пояс", times.get("Часовой пояс съёмки",""), "trace")}</div>
                        <div>{_field("ПО обработки", soft.get("ПО обработки",""))}</div>
                        <div>{_field("Artist", soft.get("Автор (Artist)",""), "trace")}</div>
                    </div>
                    {gps_html}
                    {traces_html}
                    {anom_html}
                </div>"""

        if img_cards:
            images_detail = f"""
            <div class="collapsible" id="imgs-{index}">
                <button class="collapse-btn" onclick="toggle('imgs-{index}')">
                    🖼️ Детали изображений ({img_count} шт.) ▼
                </button>
                <div class="collapse-body" style="display:none">
                    {img_cards}
                </div>
            </div>"""

    anomaly_section = ""
    if all_anomalies:
        items = "".join(f"<li>{_e(a)}</li>" for a in all_anomalies)
        anomaly_section = f"""
        <div class="bottom-section anomaly-section">
            <div class="bottom-header anomaly">⚠️ Аномалии ({len(all_anomalies)})</div>
            <ul class="anomaly-list">{items}</ul>
        </div>"""
    else:
        anomaly_section = """
        <div class="bottom-section">
            <div class="ok" style="padding:8px">✅ Аномалий не обнаружено</div>
        </div>"""

    return f"""
    <div class="doc-card">
        <div class="card-header">
            <div class="card-title">
                <span class="doc-icon">📄</span>
                <span class="doc-name">{_e(name)}</span>
                <a href="{_e(link)}" target="_blank" class="btn-link">🔗 Открыть</a>
            </div>
            <div class="card-badges">
                {badge}
                {'<span class="badge badge-warn">☁️ Общий доступ</span>' if shared=="Да" else ""}
                {'<span class="badge badge-crit">🗑️ В корзине</span>' if trashed=="Да" else ""}
            </div>
        </div>
        <div class="card-grid">
            {doc_section}
            {osint_section}
            {security_section}
            {hidden_gdrive_section}
            {images_summary}
        </div>
        {images_detail}
        {anomaly_section}
    </div>"""


def generate_html_report(
    results: list,
    anomalies_map: dict,
    google_results: list = None,
    local_images_map: dict = None,
    local_scan_map: dict = None,
    local_hidden_map: dict = None
):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    filename    = os.path.join(REPORTS_DIR, f"forensic_report_{timestamp}.html")

    total_files   = len(results)
    total_google  = len(google_results) if google_results else 0
    total_anomaly = sum(len(v) for v in anomalies_map.values())

    if local_images_map is None:
        local_images_map = {}
    if local_scan_map is None:
        local_scan_map = {}
    if local_hidden_map is None:
        local_hidden_map = {}

    # ── GOOGLE DRIVE КАРТОЧКИ ─────────────────────────────
    google_cards_html = ""
    if google_results:
        for i, g in enumerate(google_results):
            if "Ошибка" in g:
                google_cards_html += f"""
                <div class="doc-card error-card">
                    <div class="card-header">
                        <span class="anomaly">❌ Ошибка: {g['Ошибка']}</span>
                    </div>
                </div>"""
            else:
                google_cards_html += _build_doc_card(g, i)

    # ── ЛОКАЛЬНЫЕ КАРТОЧКИ ────────────────────────────────
    local_cards_html = ""
    for i, meta in enumerate(results):
        fname = meta.get("Файл", "")
        anomalies = anomalies_map.get(fname, [])
        images = local_images_map.get(fname, [])
        scan_result = local_scan_map.get(fname)
        hidden_result = local_hidden_map.get(fname)
        if meta.get("_тип") == "image":
            local_cards_html += _build_image_card(meta, anomalies, images, i, scan_result)
        else:
            local_cards_html += _build_local_card(meta, anomalies, images, i, scan_result, hidden_result)

    # ── СТАТИСТИКА СЕКЦИЙ ─────────────────────────────────
    google_section_html = ""
    if google_results:
        total_images = sum(g.get("Сканирование файла",{}).get("Изображений найдено",0)
                           for g in google_results if "Ошибка" not in g)
        total_gps    = sum(len(g.get("Сканирование файла",{}).get("Координаты",[]))
                           for g in google_results if "Ошибка" not in g)
        total_traces = sum(len(g.get("Сканирование файла",{}).get("Все следы",[]))
                           for g in google_results if "Ошибка" not in g)
        total_anom   = sum(len(g.get("Сканирование файла",{}).get("Все аномалии",[]))
                           for g in google_results if "Ошибка" not in g)

        google_section_html = f"""
        <h2 class="section-title">☁️ Анализ Google Drive</h2>
        <div class="summary-bar">
            <div class="sum-stat"><b>{total_google}</b><span>документов</span></div>
            <div class="sum-stat"><b>{total_images}</b><span>изображений</span></div>
            <div class="sum-stat"><b class="{'anomaly' if total_gps else 'ok'}">{total_gps}</b><span>с GPS</span></div>
            <div class="sum-stat"><b class="trace">{total_traces}</b><span>следов</span></div>
            <div class="sum-stat"><b class="{'anomaly' if total_anom else 'ok'}">{total_anom}</b><span>аномалий</span></div>
        </div>
        {google_cards_html}"""

    local_section_html = ""
    if results:
        local_section_html = f"""
        <h2 class="section-title">📁 Локальные файлы</h2>
        <div class="summary-bar">
            <div class="sum-stat"><b>{total_files}</b><span>файлов</span></div>
            <div class="sum-stat"><b class="{'anomaly' if total_anomaly else 'ok'}">{total_anomaly}</b><span>аномалий</span></div>
        </div>
        {local_cards_html}"""

    css = """
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');
        :root{--bg:#0a0e17;--bg2:#0f1520;--bg3:#161d2e;--bg4:#1c2539;--border:#1e2d45;--border2:#243450;--blue:#4d9eff;--blue2:#2d7dd2;--green:#3ddc84;--red:#ff4d6a;--yellow:#ffc44d;--text:#c8d6f0;--text2:#7a8fb5;--text3:#3d5280;}
        *{box-sizing:border-box;margin:0;padding:0;}
        body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);padding:24px 32px;background-image:radial-gradient(ellipse at 20% 0%,rgba(45,125,210,.08) 0%,transparent 60%),radial-gradient(ellipse at 80% 100%,rgba(61,220,132,.04) 0%,transparent 60%);}
        .report-header{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:20px;margin-bottom:28px;border-bottom:1px solid var(--border2);}
        .report-title{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:var(--blue);letter-spacing:1px;}
        .report-title span{color:var(--text2);font-weight:400;}
        .report-meta{font-size:11px;color:var(--text3);text-align:right;line-height:1.8;font-family:'JetBrains Mono',monospace;}
        .section-title{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:var(--blue);letter-spacing:2px;text-transform:uppercase;margin:28px 0 16px;padding:8px 12px;background:var(--bg3);border-left:3px solid var(--blue2);border-radius:0 4px 4px 0;}
        .summary-bar{display:flex;gap:2px;margin-bottom:20px;background:var(--bg3);border:1px solid var(--border);border-radius:8px;overflow:hidden;}
        .sum-stat{flex:1;padding:14px 16px;text-align:center;border-right:1px solid var(--border);}
        .sum-stat:last-child{border-right:none;}
        .sum-stat b{display:block;font-family:'JetBrains Mono',monospace;font-size:24px;color:var(--blue);line-height:1;margin-bottom:4px;}
        .sum-stat span{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;}
        .doc-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;margin-bottom:20px;overflow:hidden;}
        .card-header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:var(--bg3);border-bottom:1px solid var(--border);flex-wrap:wrap;gap:8px;}
        .card-title{display:flex;align-items:center;gap:10px;}
        .doc-icon{font-size:18px;}
        .doc-name{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:var(--text);}
        .card-badges{display:flex;gap:6px;flex-wrap:wrap;}
        .badge{font-size:10px;font-weight:600;padding:3px 8px;border-radius:20px;font-family:'JetBrains Mono',monospace;letter-spacing:.5px;}
        .badge-ok{background:rgba(61,220,132,.12);color:var(--green);border:1px solid rgba(61,220,132,.25);}
        .badge-warn{background:rgba(255,196,77,.12);color:var(--yellow);border:1px solid rgba(255,196,77,.25);}
        .badge-crit{background:rgba(255,77,106,.12);color:var(--red);border:1px solid rgba(255,77,106,.25);}
        .badge-trace{background:rgba(77,158,255,.12);color:var(--blue);border:1px solid rgba(77,158,255,.25);}
        .card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));border-bottom:1px solid var(--border);}
        .card-section{padding:14px 16px;border-right:1px solid var(--border);}
        .card-section:last-child{border-right:none;}
        .section-header{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:6px;}
        .img-count{margin-left:auto;font-family:'JetBrains Mono',monospace;color:var(--blue);}
        .field{display:flex;flex-direction:column;margin-bottom:7px;}
        .field-label{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--text3);margin-bottom:1px;}
        .field-value{font-size:11px;color:var(--text);word-break:break-all;line-height:1.4;}
        .email-link{color:var(--blue);text-decoration:none;font-size:11px;}
        .email-link:hover{text-decoration:underline;}
        .perm-list{margin-top:8px;}
        .perm-row{display:flex;gap:8px;font-size:10px;padding:3px 0;border-bottom:1px solid var(--border);align-items:center;}
        .perm-row:last-child{border-bottom:none;}
        .img-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px;}
        .img-stat{background:var(--bg4);border:1px solid var(--border);border-radius:6px;padding:8px 6px;text-align:center;}
        .img-stat b{display:block;font-family:'JetBrains Mono',monospace;font-size:18px;color:var(--blue);line-height:1;}
        .img-stat span{font-size:9px;color:var(--text3);text-transform:uppercase;}
        .devices-list{font-size:11px;color:var(--yellow);padding:5px 8px;background:rgba(255,196,77,.06);border-radius:4px;margin-bottom:8px;}
        .gps-alert{background:rgba(255,77,106,.08);border:1px solid rgba(255,77,106,.3);border-radius:6px;padding:10px 12px;margin:8px 0;}
        .gps-title{font-size:11px;font-weight:600;color:var(--red);margin-bottom:4px;}
        .gps-coords{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text);margin-bottom:6px;}
        .bottom-section{padding:12px 18px;border-top:1px solid var(--border);}
        .bottom-header{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;}
        .anomaly-section{background:rgba(255,77,106,.04);}
        .anomaly-list{list-style:none;padding:0;}
        .anomaly-list li{font-size:11px;padding:4px 0;border-bottom:1px solid var(--border);color:var(--text);}
        .anomaly-list li:last-child{border-bottom:none;}
        .anomaly-list li::before{content:"→ ";color:var(--red);}
        .collapsible{margin:0;}
        .collapse-btn{width:100%;background:var(--bg3);border:none;border-top:1px solid var(--border);color:var(--blue);font-family:'JetBrains Mono',monospace;font-size:11px;padding:10px 18px;text-align:left;cursor:pointer;transition:background .2s;}
        .collapse-btn:hover{background:var(--bg4);}
        .collapse-body{padding:12px 16px;background:var(--bg);}
        .img-mini-card{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:8px;}
        .img-mini-name{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--blue);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;}
        .img-mini-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:4px;margin-bottom:6px;}
        .img-gps{margin-top:8px;padding:6px 8px;background:rgba(255,77,106,.08);border-radius:4px;font-size:11px;color:var(--red);}
        .img-block-title{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px;}
        .img-traces-list{list-style:none;padding:0;}
        .img-traces-list li{font-size:10px;color:var(--text2);padding:2px 0;}
        .img-traces-list li::before{content:"→ ";color:var(--blue);}
        .img-anomalies{list-style:none;padding:0;}
        .img-anomalies li{font-size:10px;color:var(--yellow);padding:2px 0;}
        .img-anomalies li::before{content:"⚠ ";}
        .anomaly{color:var(--red)!important;}
        .ok{color:var(--green)!important;}
        .warn{color:var(--yellow)!important;}
        .trace{color:var(--blue)!important;}
        .small{color:var(--text3);font-size:10px;}
        .small-code{font-size:9px;}
        code{font-family:'JetBrains Mono',monospace;font-size:10px;background:var(--bg4);padding:1px 4px;border-radius:3px;color:var(--text2);word-break:break-all;}
        .hash{font-size:9px;}
        .btn-link{color:var(--blue);text-decoration:none;padding:2px 8px;border:1px solid var(--border2);border-radius:4px;font-size:10px;font-family:'JetBrains Mono',monospace;white-space:nowrap;transition:all .15s;}
        .btn-link:hover{background:var(--blue2);color:white;border-color:var(--blue2);}
        .error-card{border-color:rgba(255,77,106,.3);}
        .report-footer{margin-top:32px;padding-top:16px;border-top:1px solid var(--border);font-size:10px;color:var(--text3);text-align:center;font-family:'JetBrains Mono',monospace;letter-spacing:1px;}
        .scan-finding{font-size:10px;padding:3px 0;border-bottom:1px solid var(--border);}
        .scan-finding:last-child{border-bottom:none;}
    """

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forensic Report</title>
    <style>{css}</style>
</head>
<body>
    <div class="report-header">
        <div><div class="report-title">🔍 FORENSIC METADATA REPORT <span>v2.0</span></div></div>
        <div class="report-meta">
            Сгенерировано: {report_time}<br>
            Локальных файлов: {total_files} &nbsp;|&nbsp; Google Drive: {total_google}<br>
            Аномалий (локальные): {total_anomaly}
        </div>
    </div>
    {google_section_html}
    {local_section_html}
    <div class="report-footer">FORENSIC FILE METADATA ANALYZER &nbsp;·&nbsp; {report_time}</div>
    <script>
        function toggle(id) {{
            const body = document.querySelector('#' + id + ' .collapse-body');
            const btn  = document.querySelector('#' + id + ' .collapse-btn');
            if (body.style.display === 'none') {{
                body.style.display = 'block';
                btn.textContent = btn.textContent.replace('▼','▲');
            }} else {{
                body.style.display = 'none';
                btn.textContent = btn.textContent.replace('▲','▼');
            }}
        }}
    </script>
</body>
</html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    log_action(f"HTML-отчёт сгенерирован: {filename}")
    print(f"  ✅ HTML-отчёт сохранён: {filename}")
    return filename