"""
ui/full_calendar_view.py
------------------------
Tam ekran takvim sekmesi görünümü.
Büyük bir takvim gösterir; bir güne tıklandığında
ana pencereye sinyal göndererek o güne geçilir.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSizePolicy, QGridLayout,
    QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor

from ui.calendar_widget import DiaryCalendar
from ui.styles import (
    BG_DARK, BG_WIDGET, BG_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, BORDER_COLOR, GLASS_BG, GLASS_BORDER,
    BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM
)


class FullCalendarView(QWidget):
    """
    Tam ekran takvim sekmesi.
    date_selected sinyali: Günlük yazı sekmesine geçmeye tetikler.
    """

    date_selected = pyqtSignal(str)   # YYYY-MM-DD — yazı sekmesine git

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BG_GRADIENT_TOP},
                    stop:1 {BG_GRADIENT_BOTTOM}
                );
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 24, 32, 24)
        root_layout.setSpacing(20)

        # ── Üst başlık ─────────────────────────────────────────────────────
        header_layout = QHBoxLayout()

        title = QLabel("Takvim Görünümü")
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 20px; font-weight: 700; "
            f"letter-spacing: 0.5px; background: transparent;"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()

        # İstatistik etiketleri
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
        )
        header_layout.addWidget(self.stats_label)

        root_layout.addLayout(header_layout)

        # ── İnce ayırıcı ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR}; border: none;")
        root_layout.addWidget(sep)

        # ── İçerik: büyük takvim + sağda bilgi paneli ─────────────────────
        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        # Büyük takvim
        self.calendar = DiaryCalendar()
        self.calendar.setMinimumSize(500, 420)
        self.calendar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        # Çift tıkla yazı sekmesine git
        self.calendar.activated.connect(self._on_date_activated)
        # Tek tıkla sağ paneli güncelle
        self.calendar.selectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self.calendar, stretch=2)

        # Sağ bilgi paneli
        self._info_panel = self._build_info_panel()
        content_layout.addWidget(self._info_panel, stretch=1)

        root_layout.addLayout(content_layout, stretch=1)

        # ── Alt açıklama ──────────────────────────────────────────────────
        hint = QLabel(
            "Bir güne çift tıklayarak yazı yazmaya başlayın"
        )
        hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent; "
            f"padding: 8px 12px; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 8px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(hint)

    def _build_info_panel(self) -> QWidget:
        """Seçili gün bilgisini gösteren sağ panel."""
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget {{
                background: rgba(255,255,255,0.03);
                border: 1px solid {BORDER_COLOR};
                border-radius: 16px;
            }}
        """)
        panel.setMaximumWidth(300)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Seçili gün başlığı
        self._selected_date_label = QLabel("Bir gün seçin")
        self._selected_date_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 16px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        self._selected_date_label.setWordWrap(True)
        layout.addWidget(self._selected_date_label)

        # Günlük durumu göstergesi
        self._status_badge = QLabel("Kayıt yok")
        self._status_badge.setFixedHeight(26)
        self._status_badge.setStyleSheet(f"""
            QLabel {{
                background: {BORDER_COLOR};
                color: {TEXT_MUTED};
                border-radius: 10px;
                padding: 2px 12px;
                font-size: 11px;
                font-weight: 500;
                border: none;
            }}
        """)
        layout.addWidget(self._status_badge)

        # İçerik önizleme
        preview_title = QLabel("Önizleme")
        preview_title.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600; "
            f"letter-spacing: 0.8px; text-transform: uppercase; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(preview_title)

        self._preview_label = QLabel("—")
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.5; "
            f"background: transparent; border: none;"
        )
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._preview_label)

        layout.addStretch()

        # Yazıya git butonu
        self._go_btn = QPushButton("Bu Güne Git")
        self._go_btn.setFixedHeight(38)
        self._go_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT_RED},
                    stop:1 #C03535
                );
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #F05555,
                    stop:1 {ACCENT_RED}
                );
            }}
            QPushButton:pressed {{
                background: #A02828;
            }}
        """)
        self._go_btn.clicked.connect(self._emit_selected_date)
        layout.addWidget(self._go_btn)

        return panel

    def _on_date_activated(self, date: QDate) -> None:
        """Çift tıkla yazı sekmesine git."""
        self.date_selected.emit(date.toString("yyyy-MM-dd"))

    def _on_selection_changed(self) -> None:
        """Tek tıkla sağ bilgi panelini güncelle."""
        date_str = self.calendar.get_selected_date_str()
        qdate = QDate.fromString(date_str, "yyyy-MM-dd")

        # Türkçe tarih formatı
        turkish_months = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
        ]
        day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

        if qdate.isValid():
            day_name = day_names[qdate.dayOfWeek() - 1]
            month    = turkish_months[qdate.month() - 1]
            friendly = f"{day_name}\n{qdate.day()} {month} {qdate.year()}"
            self._selected_date_label.setText(friendly)

        # Kayıt durumu
        entry = self.db.get_entry(date_str)
        if entry and entry["content"]:
            self._status_badge.setText("Kayıt Mevcut")
            self._status_badge.setStyleSheet(f"""
                QLabel {{
                    background: rgba(232, 69, 69, 0.15);
                    color: {ACCENT_RED};
                    border: 1px solid rgba(232, 69, 69, 0.3);
                    border-radius: 10px;
                    padding: 2px 12px;
                    font-size: 11px;
                    font-weight: 500;
                }}
            """)
            # Önizleme
            preview = entry["content"].strip().replace("\n", " ")
            if len(preview) > 120:
                preview = preview[:120] + "..."
            self._preview_label.setText(preview)

            # Mutluluk skoru varsa göster
            score = entry["happiness_score"] if entry["happiness_score"] else 0
            if score > 0:
                from ui.rating_widget import MOOD_LABELS
                label = MOOD_LABELS.get(score, "")
                self._go_btn.setText(f"Bu Güne Git  —  {label} ({score}/10)")
            else:
                self._go_btn.setText("Bu Güne Git")
        else:
            self._status_badge.setText("Boş Gün")
            self._status_badge.setStyleSheet(f"""
                QLabel {{
                    background: rgba(255,255,255,0.04);
                    color: {TEXT_MUTED};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 10px;
                    padding: 2px 12px;
                    font-size: 11px;
                    font-weight: 500;
                }}
            """)
            self._preview_label.setText("Bu güne ait henüz bir yazı yok.")
            self._go_btn.setText("Yazmaya Başla")

    def _emit_selected_date(self) -> None:
        """'Bu güne git' butonuna basılınca sinyal gönder."""
        date_str = self.calendar.get_selected_date_str()
        self.date_selected.emit(date_str)

    def refresh_heatmap(self, filled_dates: list[str]) -> None:
        """Takvim ısı haritasını günceller."""
        self.calendar.refresh_heatmap(filled_dates)

    def update_stats(self, stats: dict) -> None:
        """İstatistik etiketini günceller."""
        total = stats.get("total_entries", 0)
        avg   = stats.get("avg_happiness", 0)
        text  = f"Toplam {total} yazı"
        if avg:
            text += f"  ·  Ortalama mutluluk: {avg}/10"
        self.stats_label.setText(text)
