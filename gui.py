import customtkinter as ctk
import threading
import os
import sys
import webbrowser
from datetime import datetime
from tkinter import filedialog

# ── Настройка темы ────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":      "#0a0e17",
    "bg2":     "#0f1520",
    "bg3":     "#161d2e",
    "bg4":     "#1c2539",
    "border":  "#1e2d45",
    "blue":    "#4d9eff",
    "blue2":   "#2d7dd2",
    "green":   "#3ddc84",
    "red":     "#ff4d6a",
    "yellow":  "#ffc44d",
    "text":    "#c8d6f0",
    "text2":   "#7a8fb5",
    "text3":   "#3d5280",
}


class ForensicApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Forensic File Metadata Analyzer v2.0")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS["bg"])

        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass  # icon.ico не найден — продолжаем без иконки

        self._last_report_path = None
        self._analysis_running = False
        self._start_time       = None

        self._build_ui()

        # Показываем локальный режим по умолчанию
        self._on_mode_change()

    # ──────────────────────────────────────────────────────
    # ПОСТРОЕНИЕ ИНТЕРФЕЙСА
    # ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Левая панель
        self.left_panel = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg2"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            width=340
        )
        self.left_panel.pack(side="left", fill="y", padx=(0, 12))
        self.left_panel.pack_propagate(False)

        # Правая панель
        self.right_panel = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.right_panel.pack(side="left", fill="both", expand=True)

        self._build_left_panel()
        self._build_right_panel()

    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=COLORS["bg3"],
            corner_radius=0, height=62
        )
        header.pack(fill="x", padx=0, pady=(0, 16))
        header.pack_propagate(False)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=12)

        ctk.CTkLabel(
            title_frame, text="🔍",
            font=ctk.CTkFont(size=26),
            text_color=COLORS["blue"]
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            title_frame,
            text="FORENSIC METADATA ANALYZER",
            font=ctk.CTkFont(family="Courier", size=17, weight="bold"),
            text_color=COLORS["blue"]
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text="  v2.0",
            font=ctk.CTkFont(family="Courier", size=14),
            text_color=COLORS["text2"]
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            header,
            text="● Готов к работе",
            font=ctk.CTkFont(family="Courier", size=12),
            text_color=COLORS["green"]
        )
        self.status_label.pack(side="right", padx=24)

    def _build_left_panel(self):
        # ── Режим работы ──────────────────────────────────
        self._section_label(self.left_panel, "РЕЖИМ АНАЛИЗА", top=16)

        self.mode_var = ctk.StringVar(value="local")
        modes = [
            ("📁   Локальные файлы", "local"),
            ("☁️   Google Drive",    "google"),
            ("🟡   Яндекс.Диск",     "yandex"),
        ]
        for text, value in modes:
            ctk.CTkRadioButton(
                self.left_panel,
                text=text,
                variable=self.mode_var,
                value=value,
                command=self._on_mode_change,
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text"],
                fg_color=COLORS["blue"],
                hover_color=COLORS["blue2"],
                radiobutton_width=18,
                radiobutton_height=18,
            ).pack(anchor="w", padx=18, pady=5)

        self._divider(self.left_panel)

        # ── Локальный режим ───────────────────────────────
        self.local_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")

        self._section_label(self.local_frame, "ПАПКА С ФАЙЛАМИ")

        folder_row = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        folder_row.pack(fill="x", padx=16, pady=(0, 10))

        self.folder_entry = ctk.CTkEntry(
            folder_row,
            placeholder_text="Путь к папке...",
            fg_color=COLORS["bg4"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text3"],
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            folder_row,
            text="📂",
            width=40, height=36,
            fg_color=COLORS["bg3"],
            hover_color=COLORS["border"],
            text_color=COLORS["blue"],
            border_width=1,
            border_color=COLORS["border"],
            font=ctk.CTkFont(size=16),
            command=self._browse_folder
        ).pack(side="left")

        # ── Облачный режим ────────────────────────────────
        self.cloud_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")

        self._section_label(self.cloud_frame, "ССЫЛКА НА ДОКУМЕНТ")

        # Поле ввода ссылки с поддержкой вставки
        self.url_entry = ctk.CTkEntry(
            self.cloud_frame,
            placeholder_text="Вставьте ссылку (Ctrl+V)...",
            fg_color=COLORS["bg4"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text3"],
            font=ctk.CTkFont(size=12),
            height=36
        )
        self.url_entry.pack(fill="x", padx=16, pady=(0, 4))

        # Подсказка про вставку
        ctk.CTkLabel(
            self.cloud_frame,
            text="💡 Ctrl+V для вставки из буфера обмена",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text3"]
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Кнопка вставить из буфера
        ctk.CTkButton(
            self.cloud_frame,
            text="📋  Вставить из буфера",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["bg3"],
            hover_color=COLORS["bg4"],
            text_color=COLORS["text2"],
            border_width=1,
            border_color=COLORS["border"],
            height=32,
            command=self._paste_from_clipboard
        ).pack(fill="x", padx=16, pady=(0, 10))

        self._divider(self.left_panel)

        # ── Кнопка запуска ────────────────────────────────
        self.run_btn = ctk.CTkButton(
            self.left_panel,
            text="▶   ЗАПУСТИТЬ АНАЛИЗ",
            font=ctk.CTkFont(family="Courier", size=14, weight="bold"),
            fg_color=COLORS["blue2"],
            hover_color=COLORS["blue"],
            text_color="white",
            height=46,
            corner_radius=8,
            command=self._run_analysis
        )
        self.run_btn.pack(fill="x", padx=16, pady=(10, 6))

        # ── Кнопка открытия отчёта ────────────────────────
        self.report_btn = ctk.CTkButton(
            self.left_panel,
            text="📊   Открыть отчёт в браузере",
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg3"],
            hover_color=COLORS["bg4"],
            text_color=COLORS["blue"],
            border_width=1,
            border_color=COLORS["border"],
            height=38,
            corner_radius=8,
            command=self._open_report,
            state="disabled"
        )
        self.report_btn.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkButton(
            self.left_panel,
            text="🗑   Очистить лог",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=COLORS["bg3"],
            text_color=COLORS["text3"],
            height=30,
            command=self._clear_log
        ).pack(fill="x", padx=16, pady=(0, 6))

        self._divider(self.left_panel)

        # ── Прогресс ──────────────────────────────────────
        self._section_label(self.left_panel, "ПРОГРЕСС")

        self.progress_bar = ctk.CTkProgressBar(
            self.left_panel,
            fg_color=COLORS["bg4"],
            progress_color=COLORS["blue"],
            height=10,
            corner_radius=5
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.left_panel,
            text="Ожидание...",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS["text3"]
        )
        self.progress_label.pack(anchor="w", padx=16)

        self._divider(self.left_panel)

        # ── Статистика ────────────────────────────────────
        self._section_label(self.left_panel, "ПОСЛЕДНИЙ АНАЛИЗ")

        stats = ctk.CTkFrame(
            self.left_panel,
            fg_color=COLORS["bg3"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        stats.pack(fill="x", padx=16, pady=(0, 16))

        self.stat_files = self._stat_row(stats, "Файлов",   "0")
        self.stat_anom  = self._stat_row(stats, "Аномалий", "0")
        self.stat_time  = self._stat_row(stats, "Время",    "—")

    def _section_label(self, parent, text, top=6):
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Courier", size=10, weight="bold"),
            text_color=COLORS["text3"]
        ).pack(anchor="w", padx=18, pady=(top, 4))

    def _divider(self, parent):
        ctk.CTkFrame(
            parent, height=1, fg_color=COLORS["border"]
        ).pack(fill="x", padx=16, pady=8)

    def _stat_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(
            row, text=label + ":",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text3"],
            width=80, anchor="w"
        ).pack(side="left")
        lbl = ctk.CTkLabel(
            row, text=value,
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
            text_color=COLORS["blue"]
        )
        lbl.pack(side="left")
        return lbl

    def _build_right_panel(self):
        self.tabview = ctk.CTkTabview(
            self.right_panel,
            fg_color=COLORS["bg2"],
            segmented_button_fg_color=COLORS["bg3"],
            segmented_button_selected_color=COLORS["blue2"],
            segmented_button_selected_hover_color=COLORS["blue"],
            segmented_button_unselected_color=COLORS["bg3"],
            segmented_button_unselected_hover_color=COLORS["bg4"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=10
        )
        self.tabview.pack(fill="both", expand=True)

        self.tabview.add("📋   Лог анализа")
        self.tabview.add("📊   Результаты")
        self.tabview.add("ℹ️    О программе")

        self._build_log_tab()
        self._build_results_tab()
        self._build_about_tab()

    def _build_log_tab(self):
        tab = self.tabview.tab("📋   Лог анализа")

        self.log_text = ctk.CTkTextbox(
            tab,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Courier", size=13),
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        self._log("╔══════════════════════════════════════════════════════╗")
        self._log("║      Forensic File Metadata Analyzer  v2.0           ║")
        self._log("║      Инструмент компьютерной экспертизы              ║")
        self._log("╚══════════════════════════════════════════════════════╝")
        self._log("")
        self._log("✅ Программа готова к работе")
        self._log("   Выберите режим анализа слева и нажмите ЗАПУСТИТЬ")
        self._log("")

    def _build_results_tab(self):
        tab = self.tabview.tab("📊   Результаты")

        self.results_summary = ctk.CTkFrame(
            tab,
            fg_color=COLORS["bg3"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.results_summary.pack(fill="x", padx=10, pady=(10, 6))

        self.summary_label = ctk.CTkLabel(
            self.results_summary,
            text="Анализ ещё не запускался",
            font=ctk.CTkFont(family="Courier", size=13),
            text_color=COLORS["text2"]
        )
        self.summary_label.pack(pady=14)

        self.results_text = ctk.CTkTextbox(
            tab,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Courier", size=13),
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            wrap="none"
        )
        self.results_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.results_text.configure(state="disabled")

    def _build_about_tab(self):
        tab = self.tabview.tab("ℹ️    О программе")

        scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent"
        )
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll,
            text="🔍  Forensic File Metadata Analyzer",
            font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
            text_color=COLORS["blue"]
        ).pack(pady=(20, 6))

        ctk.CTkLabel(
            scroll,
            text="Версия 2.0  |  Тема №26 — Компьютерная экспертиза",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text2"]
        ).pack(pady=(0, 20))

        features = [
            ("📄", "Анализ DOCX, PDF, PPTX",      "Метаданные, статистика, XML структура"),
            ("🖼️", "EXIF изображений",              "GPS координаты, устройство, даты съёмки"),
            ("👁️", "Скрытый текст (w:vanish)",      "Обнаружение скрытых фрагментов в DOCX"),
            ("🛡️", "Вирусное сканирование",          "Статический анализ без внешних антивирусов"),
            ("☁️", "Google Drive",                   "Метаданные, права доступа, EXIF"),
            ("🟡", "Яндекс.Диск",                   "Анализ публичных документов"),
            ("🔗", "URL и гиперссылки",              "OSINT по внешним ссылкам документа"),
            ("📊", "HTML отчёт",                     "Профессиональный отчёт для эксперта"),
            ("🔐", "MD5 / SHA256",                   "Криптографические хэши для доказательной базы"),
        ]

        for icon, title, desc in features:
            row = ctk.CTkFrame(
                scroll,
                fg_color=COLORS["bg3"],
                corner_radius=8,
                border_width=1,
                border_color=COLORS["border"]
            )
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(
                row, text=icon,
                font=ctk.CTkFont(size=18), width=46
            ).pack(side="left", padx=12, pady=10)

            ctk.CTkLabel(
                row, text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["text"],
                width=220, anchor="w"
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=desc,
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text2"],
                anchor="w"
            ).pack(side="left", padx=10)

        ctk.CTkLabel(
            scroll,
            text="\nАнализ метаданных облачных документов (Google Docs, Office 365)\n",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text3"]
        ).pack(pady=(16, 0))

    # ──────────────────────────────────────────────────────
    # ЛОГИКА
    # ──────────────────────────────────────────────────────

    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "local":
            self.cloud_frame.pack_forget()
            self.local_frame.pack(fill="x")
        else:
            self.local_frame.pack_forget()
            self.cloud_frame.pack(fill="x")
            placeholder = {
                "google": "https://drive.google.com/...",
                "yandex": "https://disk.yandex.ru/d/...",
            }
            self.url_entry.configure(
                placeholder_text=placeholder.get(mode, "Вставьте ссылку...")
            )

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с файлами")
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _paste_from_clipboard(self):
        """Вставляет текст из буфера обмена в поле ссылки"""
        try:
            text = self.clipboard_get()
            if text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, text.strip())
                self._log(f"📋 Вставлено из буфера: {text.strip()[:60]}...")
        except Exception:
            self._log("⚠️  Буфер обмена пуст или недоступен")

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}]  {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log("🗑  Лог очищен")

    def _set_status(self, text: str, color: str = None):
        self.status_label.configure(
            text=text,
            text_color=color or COLORS["text2"]
        )

    def _run_analysis(self):
        if self._analysis_running:
            return

        mode = self.mode_var.get()

        if mode == "local":
            path = self.folder_entry.get().strip()
            if not path or not os.path.isdir(path):
                self._log("❌ Укажите корректный путь к папке")
                return
        else:
            path = self.url_entry.get().strip()
            if not path or not path.startswith("http"):
                self._log("❌ Укажите корректную ссылку (начинается с http)")
                return

        self._analysis_running = True
        self.run_btn.configure(state="disabled", text="⏳  Анализ...")
        self.report_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Запуск...")
        self._set_status("● Анализ запущен...", COLORS["yellow"])
        self._start_time = datetime.now()

        thread = threading.Thread(
            target=self._run_in_thread,
            args=(mode, path),
            daemon=True
        )
        thread.start()

    def _run_in_thread(self, mode: str, path: str):
        try:
            self.after(0, lambda: self._log(f"🚀 Запуск | Режим: {mode}"))
            self.after(0, lambda: self._log(f"   Цель: {path}"))
            self.after(0, lambda: self._log("─" * 52))

            if mode == "local":
                self._run_local(path)
            elif mode == "google":
                self._run_google(path)
            elif mode == "yandex":
                self._run_yandex(path)

        except Exception as e:
            self.after(0, lambda err=str(e): self._log(f"❌ Критическая ошибка: {err}"))
        finally:
            self.after(0, self._analysis_done)

    def _run_local(self, folder_path: str):
        from modules.reporter         import generate_html_report
        from modules.exporter         import export_to_csv

        SUPPORTED = {
            ".docx": "Word",  ".pdf":  "PDF",
            ".pptx": "PPTX",  ".jpg":  "JPEG",
            ".jpeg": "JPEG",  ".png":  "PNG",
            ".tiff": "TIFF",  ".bmp":  "BMP",
        }

        all_files = []
        for f in os.listdir(folder_path):
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED:
                all_files.append(
                    (os.path.join(folder_path, f), ext, SUPPORTED[ext])
                )

        if not all_files:
            self.after(0, lambda: self._log("❌ Поддерживаемые файлы не найдены"))
            return

        self.after(0, lambda n=len(all_files): self._log(f"📁 Найдено файлов: {n}"))

        all_results      = []
        anomalies_map    = {}
        local_images_map = {}
        local_scan_map   = {}
        local_hidden_map = {}
        total_anomalies  = 0

        for idx, (filepath, ext, ftype) in enumerate(all_files):
            fname    = os.path.basename(filepath)
            progress = (idx + 1) / len(all_files)

            self.after(0, lambda p=progress: self.progress_bar.set(p * 0.9))
            self.after(0, lambda f=fname: self.progress_label.configure(
                text=f"Анализ: {f[:28]}..."
            ))
            self.after(0, lambda f=fname, t=ftype: self._log(f"  📄 {f}  [{t}]"))

            try:
                if ext == ".docx":
                    from main import analyze_file
                    result = analyze_file(filepath)
                    all_results.append(result["metadata"])
                    key = result["metadata"]["Файл"]
                    anomalies_map[key]    = result["anomalies"]
                    local_images_map[key] = result.get("images", [])
                    local_scan_map[key]   = result.get("scan",   {})
                    local_hidden_map[key] = result.get("hidden", {})
                    n = len(result["anomalies"])
                else:
                    from main import analyze_other_file
                    result = analyze_other_file(filepath, ext)
                    if result:
                        all_results.append(result["metadata"])
                        key = result["metadata"]["Файл"]
                        anomalies_map[key]    = result.get("anomalies", [])
                        local_images_map[key] = result.get("images",    [])
                        local_scan_map[key]   = result.get("scan",      {})
                        local_hidden_map[key] = result.get("hidden",    {})
                        n = len(result.get("anomalies", []))
                    else:
                        n = 0

                total_anomalies += n
                msg = f"     ⚠️  Аномалий: {n}" if n > 0 else "     ✅ Чисто"
                self.after(0, lambda m=msg: self._log(m))

            except Exception as e:
                self.after(0, lambda err=str(e): self._log(f"     ❌ Ошибка: {err}"))

        # Генерация отчёта
        self.after(0, lambda: self._log("─" * 52))
        self.after(0, lambda: self._log("📊 Генерация HTML отчёта..."))
        self.after(0, lambda: self.progress_label.configure(text="Генерация отчёта..."))

        report_path = generate_html_report(
            all_results, anomalies_map,
            local_images_map=local_images_map,
            local_scan_map=local_scan_map,
            local_hidden_map=local_hidden_map
        )
        export_to_csv(all_results)

        self._last_report_path = report_path
        elapsed = int((datetime.now() - self._start_time).total_seconds())

        self.after(0, lambda p=report_path: self._log(f"✅ Отчёт сохранён: {p}"))
        self.after(0, lambda n=len(all_results), a=total_anomalies, t=elapsed: (
            self.stat_files.configure(text=str(n)),
            self.stat_anom.configure(
                text=str(a),
                text_color=COLORS["red"] if a > 0 else COLORS["green"]
            ),
            self.stat_time.configure(text=f"{t} с"),
            self.summary_label.configure(
                text=f"✅  Файлов: {n}   |   ⚠️  Аномалий: {a}   |   ⏱  {t} с",
                text_color=COLORS["red"] if a > 0 else COLORS["green"]
            )
        ))
        self.after(0, lambda r=all_results, a=anomalies_map:
            self._update_results_tab(r, a)
        )

    def _run_google(self, url: str):
        self.after(0, lambda: self._log("☁️  Подключение к Google Drive..."))
        self.after(0, lambda: self.progress_bar.set(0.15))
        try:
            from modules.cloud.google_drive import (
                authenticate, extract_file_id,
                is_folder, analyze_google_folder, analyze_google_doc
            )
            from modules.reporter import generate_html_report

            service = authenticate()
            file_id = extract_file_id(url)
            folder  = is_folder(service, file_id) if file_id else False

            self.after(0, lambda: self.progress_bar.set(0.4))

            if folder:
                self.after(0, lambda: self._log("📁 Папка — анализируем файлы..."))
                results = analyze_google_folder(url)
            else:
                self.after(0, lambda: self._log("📄 Одиночный файл..."))
                results = [analyze_google_doc(url)]

            self.after(0, lambda: self.progress_bar.set(0.85))
            self.after(0, lambda: self._log("📊 Генерация отчёта..."))

            report_path = generate_html_report([], {}, google_results=results)
            self._last_report_path = report_path
            elapsed = int((datetime.now() - self._start_time).total_seconds())

            self.after(0, lambda n=len(results), t=elapsed: (
                self._log(f"✅ Готово! Файлов: {n}  |  Время: {t} с"),
                self.stat_files.configure(text=str(n)),
                self.stat_time.configure(text=f"{t} с"),
                self.summary_label.configure(
                    text=f"✅  Google Drive: {n} файлов  |  ⏱  {t} с",
                    text_color=COLORS["green"]
                )
            ))
            self.after(0, lambda r=results: self._update_cloud_results(r))

        except Exception as e:
            self.after(0, lambda err=str(e): self._log(f"❌ Ошибка Google Drive: {err}"))

    def _run_yandex(self, url: str):
        self.after(0, lambda: self._log("🟡 Подключение к Яндекс.Диску..."))
        self.after(0, lambda: self.progress_bar.set(0.15))
        try:
            from modules.cloud.yandex_disk import (
                analyze_yandex_file, analyze_yandex_folder, is_folder
            )
            from modules.reporter import generate_html_report

            self.after(0, lambda: self.progress_bar.set(0.4))

            if is_folder(url):
                self.after(0, lambda: self._log("📁 Папка Яндекс.Диска..."))
                results = analyze_yandex_folder(url)
            else:
                self.after(0, lambda: self._log("📄 Файл Яндекс.Диска..."))
                results = [analyze_yandex_file(url)]

            self.after(0, lambda: self.progress_bar.set(0.85))
            self.after(0, lambda: self._log("📊 Генерация отчёта..."))

            report_path = generate_html_report([], {}, google_results=results)
            self._last_report_path = report_path
            elapsed = int((datetime.now() - self._start_time).total_seconds())

            self.after(0, lambda n=len(results), t=elapsed: (
                self._log(f"✅ Готово! Файлов: {n}  |  Время: {t} с"),
                self.stat_files.configure(text=str(n)),
                self.stat_time.configure(text=f"{t} с"),
                self.summary_label.configure(
                    text=f"✅  Яндекс.Диск: {n} файлов  |  ⏱  {t} с",
                    text_color=COLORS["green"]
                )
            ))
            self.after(0, lambda r=results: self._update_cloud_results(r))

        except Exception as e:
            self.after(0, lambda err=str(e): self._log(f"❌ Ошибка Яндекс.Диска: {err}"))

    def _update_results_tab(self, results: list, anomalies_map: dict):
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")

        for meta in results:
            fname = meta.get("Файл", "—")
            anoms = anomalies_map.get(fname, [])

            self.results_text.insert("end", f"{'='*58}\n")
            self.results_text.insert("end", f"  📄 {fname}\n")
            self.results_text.insert("end", f"{'='*58}\n")

            fields = [
                "Автор", "Последний редактор", "Организация",
                "Дата создания", "Дата изменения",
                "Время редактирования", "Номер редакции",
                "Приложение", "Версия приложения",
                "Язык документа",
                "Страниц", "Слов", "MD5", "SHA256",
            ]
            for key in fields:
                val = meta.get(key, "")
                skip = ("—", "Нет данных", "Не указан",
                        "Не указана", "Нет", "", None)
                if val not in skip:
                    self.results_text.insert(
                        "end", f"  {key:<26}: {val}\n"
                    )

            if anoms:
                self.results_text.insert(
                    "end", f"\n  ⚠️  АНОМАЛИИ ({len(anoms)}):\n"
                )
                for a in anoms:
                    self.results_text.insert("end", f"     → {a}\n")

            self.results_text.insert("end", "\n")

        self.results_text.configure(state="disabled")
        # Переключаемся на вкладку результатов
        self.tabview.set("📊   Результаты")

    def _update_cloud_results(self, results: list):
        """Отображает результаты облачного анализа во вкладке Результаты"""
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")

        for r in results:
            if "Ошибка" in r:
                self.results_text.insert("end", f"❌ Ошибка: {r['Ошибка']}\n")
                continue

            name = r.get("Название", "—")
            self.results_text.insert("end", f"{'=' * 58}\n")
            self.results_text.insert("end", f"  📄 {name}\n")
            self.results_text.insert("end", f"{'=' * 58}\n")

            # Основные поля
            fields = [
                "Название", "Тип файла (MIME)", "Размер",
                "Владелец", "Email владельца",
                "Последний редактор", "Email редактора",
                "Дата создания", "Дата изменения",
                "Общий доступ", "MD5 (Яндекс)", "SHA256 (Яндекс)",
                "Владелец (логин)",
            ]
            skip = ("—", "Нет данных", "Не указан", "Не указана", "Нет", "", None)
            for key in fields:
                val = r.get(key, "")
                if val not in skip:
                    self.results_text.insert("end", f"  {key:<26}: {val}\n")

            # Сканирование
            scan = r.get("Сканирование файла", {})
            if scan:
                imgs = scan.get("Изображений найдено", 0)
                gps = scan.get("GPS обнаружен", False)
                self.results_text.insert(
                    "end",
                    f"\n  🖼️  Изображений: {imgs}  |  "
                    f"{'📍 GPS ОБНАРУЖЕН' if gps else 'GPS нет'}\n"
                )

                # Скрытый текст
                hidden = scan.get("Скрытый текст", {})
                if hidden and hidden.get("Скрытых фрагментов", 0) > 0:
                    self.results_text.insert(
                        "end",
                        f"  👁️  Скрытых фрагментов: {hidden['Скрытых фрагментов']}\n"
                    )
                    for frag in hidden.get("Скрытый текст", []):
                        self.results_text.insert(
                            "end",
                            f"     → Параграф №{frag['Параграф №']}: "
                            f"{frag['Скрытый текст'][:80]}\n"
                        )

                # Аномалии
                anom = scan.get("Все аномалии", [])
                if anom:
                    self.results_text.insert(
                        "end", f"\n  ⚠️  Аномалии ({len(anom)}):\n"
                    )
                    for a in anom:
                        self.results_text.insert("end", f"     → {a}\n")

            self.results_text.insert("end", "\n")

        self.results_text.configure(state="disabled")
        self.tabview.set("📊   Результаты")

    def _analysis_done(self):
        self._analysis_running = False
        self.run_btn.configure(state="normal", text="▶   ЗАПУСТИТЬ АНАЛИЗ")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="Завершено ✅")
        self._set_status("● Анализ завершён", COLORS["green"])
        if self._last_report_path:
            self.report_btn.configure(state="normal")

    def _open_report(self):
        if self._last_report_path and os.path.exists(self._last_report_path):
            webbrowser.open(
                f"file:///{os.path.abspath(self._last_report_path).replace(os.sep, '/')}"
            )
        else:
            self._log("❌ Отчёт не найден — сначала запустите анализ")


# ── Точка входа ───────────────────────────────────────────
if __name__ == "__main__":
    app = ForensicApp()
    app.mainloop()