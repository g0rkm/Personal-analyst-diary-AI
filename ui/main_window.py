"""
ui/main_window.py
-----------------
Ana uygulama penceresi.
İki sekme sistemi:
  Tab 0 — Yazı görünümü (sidebar takvim + editör + AI panel)
  Tab 1 — Tam ekran takvim

Sol sidebar açılır-kapanır; toggle butonu her zaman görünür şeritte kalır.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, QDate, QTimer, QSize
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QLinearGradient, QColor, QPainter

from database import Database
from ui.calendar_widget import DiaryCalendar
from ui.editor_panel import EditorPanel
from ui.search_dialog import SearchResultDialog
from ui.ai_chat_panel import AIChatPanel
from settings import load_settings
from ui.full_calendar_view import FullCalendarView
from ai.rag_engine import RAGEngine
from ai.worker import IndexWorker, MoodAnalysisWorker
import os
from ui.styles import (
    MAIN_STYLESHEET,
    BG_DARK, BG_WIDGET, BG_WIDGET_ALT, BG_SIDEBAR, BG_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BORDER_COLOR, GLASS_BG, GLASS_BORDER,
    BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM
)

# Sidebar genişlikleri
SIDEBAR_EXPANDED  = 300
# Toggle şeridinin genişliği — her zaman görünür
TOGGLE_STRIP_WIDTH = 36


class GradientWidget(QWidget):
    """Gradient arka planlı ana widget."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(BG_GRADIENT_TOP))
        gradient.setColorAt(1.0, QColor(BG_GRADIENT_BOTTOM))
        painter.fillRect(self.rect(), gradient)
        super().paintEvent(event)


class TabButton(QPushButton):
    """Özel sekme butonu."""
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFixedHeight(36)
        self._apply_style(active=False)

    def _apply_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(232, 69, 69, 0.2),
                        stop:1 rgba(232, 69, 69, 0.08)
                    );
                    color: {TEXT_PRIMARY};
                    border: 1px solid rgba(232, 69, 69, 0.4);
                    border-radius: 10px;
                    padding: 6px 18px;
                    font-size: 13px;
                    font-weight: 600;
                    letter-spacing: 0.2px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_MUTED};
                    border: 1px solid transparent;
                    border-radius: 10px;
                    padding: 6px 18px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.05);
                    color: {TEXT_SECONDARY};
                    border: 1px solid {BORDER_COLOR};
                }}
            """)

    def setActive(self, active: bool) -> None:
        self._apply_style(active)


class MainWindow(QMainWindow):
    """Ana uygulama penceresi — Tab sistemi, collapsible sidebar, AI panel."""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self._sidebar_expanded = True
        self._current_tab = 0
        self.rag_engine = None
        self.index_worker = None
        self.mood_worker = None

        self.setWindowTitle("Günlük — Kişisel Günlük")
        self.setMinimumSize(960, 640)
        self.resize(1200, 740)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._setup_ui()
        self._setup_shortcuts()
        self._load_initial_data()

    # ── Arayüz Kurulumu ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = GradientWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        # Tab 0: Yazı görünümü
        self._stack.addWidget(self._build_writing_view())

        # Tab 1: Tam ekran takvim
        self.full_calendar_view = FullCalendarView(db=self.db)
        self.full_calendar_view.date_selected.connect(self._navigate_to_date_and_switch_tab)
        self._stack.addWidget(self.full_calendar_view)

        root.addWidget(self._stack, stretch=1)
        root.addWidget(self._build_status_bar())

    def _build_header(self) -> QWidget:
        """Gradient üst başlık çubuğu: logo + sekme butonları + arama."""
        header = QWidget()
        header.setObjectName("mainHeader")
        header.setFixedHeight(65)
        header.setStyleSheet(f"""
            QWidget#mainHeader {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(13,13,26,0.98),
                    stop:1 rgba(18,18,35,0.98)
                );
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Sekme butonları — kutu olmadan yan yana
        self._tab_writing = TabButton("Yazı")
        self._tab_writing.setActive(True)
        self._tab_writing.clicked.connect(lambda: self._switch_tab(0))

        self._tab_calendar = TabButton("Takvim")
        self._tab_calendar.setActive(False)
        self._tab_calendar.clicked.connect(lambda: self._switch_tab(1))

        layout.addWidget(self._tab_writing)
        layout.addWidget(self._tab_calendar)
        layout.addStretch()

        # Arama çubuğu — QFrame container içinde (tam border render için)
        self._search_frame = QFrame()
        self._search_frame.setObjectName("searchBarFrame")
        self._search_frame.setFixedWidth(260)
        self._search_frame.setFixedHeight(34)
        search_frame_layout = QHBoxLayout(self._search_frame)
        search_frame_layout.setContentsMargins(0, 0, 0, 0)
        search_frame_layout.setSpacing(0)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Günlüklerde ara...")
        self.search_bar.returnPressed.connect(self._do_search)

        # Focus eventleri ile container border'nı değiştir
        self.search_bar.focusInEvent  = self._on_search_focus_in
        self.search_bar.focusOutEvent = self._on_search_focus_out

        search_frame_layout.addWidget(self.search_bar)
        layout.addWidget(self._search_frame)

        search_btn = QPushButton("Ara")
        search_btn.setFixedSize(52, 34)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 10px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {ACCENT_RED};
                color: #FFFFFF;
                border-color: {ACCENT_RED};
            }}
        """)
        search_btn.clicked.connect(self._do_search)
        layout.addWidget(search_btn)

        return header

    def _build_writing_view(self) -> QWidget:
        """
        Tab 0 — Yazı görünümü.
        Yapı: [toggle_strip | sidebar_content | separator | editor | ai_panel]
        toggle_strip her zaman görünür kalır; sidebar_content açılıp kapanır.
        """
        container = QWidget()
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Her zaman görünür toggle şeridi ───────────────────────────────
        self._toggle_strip = self._build_toggle_strip()
        layout.addWidget(self._toggle_strip)

        # ── Toggle şeridi ile sidebar içeriği arasındaki ince çizgi ───────
        self._strip_sep = QFrame()
        self._strip_sep.setFrameShape(QFrame.Shape.VLine)
        self._strip_sep.setFixedWidth(1)
        self._strip_sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        layout.addWidget(self._strip_sep)

        # ── Sidebar içeriği (takvim + istatistik — açılıp kapanır) ─────────
        self._sidebar_content = self._build_sidebar_content()
        layout.addWidget(self._sidebar_content)

        # ── Sidebar ile editör arasındaki ince çizgi ───────────────────────
        self._sidebar_sep = QFrame()
        self._sidebar_sep.setFrameShape(QFrame.Shape.VLine)
        self._sidebar_sep.setFixedWidth(1)
        self._sidebar_sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        layout.addWidget(self._sidebar_sep)

        # ── Editör paneli ──────────────────────────────────────────────────
        editor_container = QWidget()
        editor_container.setStyleSheet("background: transparent;")
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(16, 16, 16, 16)
        editor_layout.setSpacing(0)

        self.editor_panel = EditorPanel(db=self.db)
        self.editor_panel.entry_saved.connect(self._on_entry_saved)
        self.editor_panel.entry_deleted.connect(lambda _: self._refresh_heatmap())
        editor_layout.addWidget(self.editor_panel)

        layout.addWidget(editor_container, stretch=1)

        # ── Sağ AI paneli ─────────────────────────────────────────────────
        self.ai_panel = AIChatPanel()
        
        # Panel açılırken RAGEngine yoksa yükle (Tembel Yükleme)
        self.ai_panel._toggle_btn.clicked.connect(self._check_ai_init)
        
        layout.addWidget(self.ai_panel)

        return container

    def _check_ai_init(self):
        """AI Paneli açılırken model varsa RAGEngine'i başlatır."""
        settings = load_settings()
        model_path = settings.get("model_path", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
        if self.ai_panel._is_expanded and not self.rag_engine and os.path.exists(model_path):
            self.rag_engine = RAGEngine()
            self.ai_panel.set_rag_engine(self.rag_engine)
            
            # SQLite ile LanceDB arasında senkronizasyon (Eksik kayıtları indeksle)
            entries = self.db.get_all_entries_content()
            existing_dates = set()
            if self.rag_engine.vector_store.table:
                # Tüm mevcut tarihleri lanceDB'den çek
                res = self.rag_engine.vector_store.table.search().limit(10000).to_list()
                existing_dates = {r['date'] for r in res}
            
            missing_entries = [e for e in entries if e['date'] not in existing_dates]
            
            if missing_entries:
                self.index_worker = IndexWorker(
                    self.rag_engine.embedder,
                    self.rag_engine.vector_store,
                    missing_entries
                )
                self.index_worker.start()

            # Henüz mood_score hesaplanmamış günlükler için toplu mood analizi başlat
            entries = self.db.get_all_entries_content()
            if entries:
                self.mood_worker = MoodAnalysisWorker(
                    self.rag_engine.llm,
                    self.db,
                    entries
                )
                self.mood_worker.start()

    def _build_toggle_strip(self) -> QWidget:
        """
        Her zaman görünür, sabit genişlikteki toggle şeridi.
        İçinde sadece açma/kapama butonu bulunur.
        """
        strip = QWidget()
        strip.setFixedWidth(TOGGLE_STRIP_WIDTH)
        strip.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {BG_SIDEBAR},
                    stop:1 rgba(18,18,30,0.9)
                );
            }}
        """)

        layout = QVBoxLayout(strip)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._sidebar_toggle_btn = QPushButton("◄")
        self._sidebar_toggle_btn.setFixedSize(34, 34)
        self._sidebar_toggle_btn.setToolTip("Takvimi Gizle / Göster  (Ctrl+B)")
        self._sidebar_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.05);
                color: {TEXT_MUTED};
                border: 1px solid {BORDER_COLOR};
                border-radius: 17px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {ACCENT_RED_BG};
                color: {ACCENT_RED};
                border-color: {ACCENT_RED};
            }}
        """)
        self._sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._sidebar_toggle_btn)

        return strip

    def _build_sidebar_content(self) -> QWidget:
        """Takvim içeriği — açılıp kapanabilen kısım."""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_EXPANDED)
        sidebar.setStyleSheet(f"""
            QWidget#sidebar {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {BG_SIDEBAR},
                    stop:1 rgba(18,18,30,0.95)
                );
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Takvim başlığı etiketi
        cal_label = QLabel("Takvim")
        cal_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; "
            f"font-weight: 600; letter-spacing: 0.8px; background: transparent;"
        )
        layout.addWidget(cal_label)

        # Takvim bileşeni
        self.calendar = DiaryCalendar()
        self.calendar.selectionChanged.connect(self._on_date_selected)
        layout.addWidget(self.calendar)

        layout.addStretch()

        return sidebar

    def _build_status_bar(self) -> QWidget:
        """Alt durum çubuğu — sade bar."""
        status = QWidget()
        status.setFixedHeight(26)
        status.setStyleSheet(
            f"background: rgba(0,0,0,0.4); border-top: 1px solid {BORDER_COLOR};"
        )
        return status

    # ── Sekme Yönetimi ────────────────────────────────────────────────────────

    def _switch_tab(self, index: int) -> None:
        """Sekme geçişi yapar."""
        self._current_tab = index
        self._stack.setCurrentIndex(index)
        self._tab_writing.setActive(index == 0)
        self._tab_calendar.setActive(index == 1)

        if index == 1:
            self.full_calendar_view.refresh_heatmap(self.db.get_all_entry_dates())
            self.full_calendar_view.update_stats(self.db.get_stats())

    def _navigate_to_date_and_switch_tab(self, date_str: str) -> None:
        """Tam takvimden tarih seçilince Yazı sekmesine geç."""
        self._switch_tab(0)
        self._navigate_to_date(date_str)

    # ── Sidebar Toggle ────────────────────────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        """
        Sol sidebar içeriğini açar veya kapatır.
        Toggle butonu her zaman görünür toggle şeridinde kalır.
        """
        self._sidebar_expanded = not self._sidebar_expanded

        if self._sidebar_expanded:
            self._sidebar_content.setFixedWidth(SIDEBAR_EXPANDED)
            self._sidebar_content.setVisible(True)
            self._sidebar_sep.setVisible(True)
            self._sidebar_toggle_btn.setText("◄")
        else:
            self._sidebar_content.setFixedWidth(0)
            self._sidebar_content.setVisible(False)
            self._sidebar_sep.setVisible(False)
            self._sidebar_toggle_btn.setText("►")

    # ── Klavye Kısayolları ────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            self.editor_panel.save_entry
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            self._focus_search
        )
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            self._toggle_sidebar
        )
        QShortcut(QKeySequence("Escape"), self.search_bar).activated.connect(
            self.search_bar.clear
        )

    def _focus_search(self) -> None:
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def _on_search_focus_in(self, event) -> None:
        """Arama çubuğuna odaklanıldığında container border'ını kırmızı yap."""
        from PyQt6.QtWidgets import QLineEdit
        QLineEdit.focusInEvent(self.search_bar, event)
        self._search_frame.setProperty("focused", "true")
        self._search_frame.style().unpolish(self._search_frame)
        self._search_frame.style().polish(self._search_frame)

    def _on_search_focus_out(self, event) -> None:
        """Arama çubuğundan çıkılınca container border'ını normale döndür."""
        from PyQt6.QtWidgets import QLineEdit
        QLineEdit.focusOutEvent(self.search_bar, event)
        self._search_frame.setProperty("focused", "false")
        self._search_frame.style().unpolish(self._search_frame)
        self._search_frame.style().polish(self._search_frame)

    # ── Olay İşleyicileri ────────────────────────────────────────────────────

    def _on_date_selected(self) -> None:
        """Takvimde farklı bir güne tıklandığında editörü günceller."""
        date_str = self.calendar.get_selected_date_str()
        self.editor_panel.load_entry(date_str)

    def _on_entry_saved(self, date_str: str, content: str) -> None:
        """Kayıt sonrası ısı haritasını yeniler, vektörleri indeksler ve duygu puanını hesaplar."""
        self._refresh_heatmap()
        
        # AI İndeksleme & Duygu Analizi (Model indirilmişse)
        settings = load_settings()
        model_path = settings.get("model_path", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
        if os.path.exists(model_path):
            if not self.rag_engine:
                self.rag_engine = RAGEngine()
                self.ai_panel.set_rag_engine(self.rag_engine)
                
            self.index_worker = IndexWorker(
                self.rag_engine.embedder,
                self.rag_engine.vector_store,
                [{"date": date_str, "content": content}]
            )
            self.index_worker.start()

            # Arka planda mood_score hesabı
            self.mood_worker = MoodAnalysisWorker(
                self.rag_engine.llm,
                self.db,
                [{"date": date_str, "content": content}]
            )
            self.mood_worker.start()

    def _do_search(self) -> None:
        """Veritabanında arama yapar ve sonuç diyaloğu açar."""
        keyword = self.search_bar.text().strip()
        if not keyword:
            self.search_bar.setPlaceholderText("Aranacak kelimeyi girin...")
            QTimer.singleShot(2000, lambda: self.search_bar.setPlaceholderText("Günlüklerde ara..."))
            return

        results = self.db.search_entries(keyword)
        dialog = SearchResultDialog(keyword=keyword, results=results, parent=self)
        dialog.date_selected.connect(self._navigate_to_date)
        dialog.exec()

    def _navigate_to_date(self, date_str: str) -> None:
        """Belirtilen tarihe gider."""
        qdate = QDate.fromString(date_str, "yyyy-MM-dd")
        if qdate.isValid():
            self._switch_tab(0)
            self.calendar.setCurrentPage(qdate.year(), qdate.month())
            self.calendar.setSelectedDate(qdate)

    # ── Veri Yükleme ─────────────────────────────────────────────────────────

    def _load_initial_data(self) -> None:
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self._refresh_heatmap()
        self.editor_panel.load_entry(today.toString("yyyy-MM-dd"))

    def _refresh_heatmap(self) -> None:
        """Tüm takvim ısı haritalarını günceller."""
        filled_dates = self.db.get_all_entry_dates()
        self.calendar.refresh_heatmap(filled_dates)

        if self._current_tab == 1:
            stats = self.db.get_stats()
            self.full_calendar_view.refresh_heatmap(filled_dates)
            self.full_calendar_view.update_stats(stats)
