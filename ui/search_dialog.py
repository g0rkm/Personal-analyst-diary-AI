"""
ui/search_dialog.py
-------------------
Arama diyaloğu penceresi.
Kullanıcının girdiği kelimeye göre veritabanını tarar
ve sonuçları bir liste halinde gösterir.
Listedeki bir tarihe tıklandığında ana pencereye sinyal gönderilir.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from ui.styles import (
    BG_DARK, BG_WIDGET, BG_WIDGET_ALT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, BORDER_COLOR
)


class SearchResultDialog(QDialog):
    """
    Arama sonuçlarını gösteren modal diyalog.
    date_selected sinyali ile seçilen tarihi ana pencereye bildirir.
    """

    # Ana pencere bu sinyali dinleyerek ilgili tarihe gider
    date_selected = pyqtSignal(str)  # YYYY-MM-DD formatında tarih

    def __init__(self, keyword: str, results: list[dict], parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.results = results

        self.setWindowTitle("Arama Sonuçları")
        self.setMinimumSize(520, 420)
        self.setModal(True)
        self._setup_ui()
        self._apply_stylesheet()

    def _setup_ui(self) -> None:
        """Diyalog arayüzünü oluşturur."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Başlık ────────────────────────────────────────────────────────
        header_layout = QHBoxLayout()

        title_label = QLabel("Arama Sonuclari")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Kaç sonuç bulundu bilgisi
        count_label = QLabel(f"{len(self.results)} kayıt bulundu")
        count_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        header_layout.addWidget(count_label)

        layout.addLayout(header_layout)

        # Aranan kelimeyi göster
        keyword_label = QLabel(f'"{self.keyword}" için sonuçlar:')
        keyword_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; "
            f"padding: 6px 10px; background: {BG_WIDGET}; "
            f"border-radius: 6px; border-left: 3px solid {ACCENT_RED};"
        )
        layout.addWidget(keyword_label)

        # ── Ayırıcı çizgi ─────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER_COLOR};")
        layout.addWidget(line)

        # ── Sonuç listesi ─────────────────────────────────────────────────
        if self.results:
            self.list_widget = QListWidget()
            self.list_widget.setObjectName("resultList")

            for result in self.results:
                date_str = result["date"]
                content  = result["content"]

                # Tarihi daha okunabilir formata çevir
                qdate = QDate.fromString(date_str, "yyyy-MM-dd")
                friendly_date = qdate.toString("d MMMM yyyy") if qdate.isValid() else date_str

                # İçerikten kısa önizleme oluştur
                preview = content.replace("\n", " ").strip()
                if len(preview) > 80:
                    preview = preview[:80] + "..."

                item = QListWidgetItem()
                item.setText(f"{friendly_date}\n    {preview}")
                item.setData(Qt.ItemDataRole.UserRole, date_str)  # Tarihi item'a ekle
                item.setFont(QFont("Segoe UI", 12))
                self.list_widget.addItem(item)

            # Listedeki ögeye çift tıklama ile tarihe git
            self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
            self.list_widget.itemClicked.connect(self._on_item_clicked)
            layout.addWidget(self.list_widget)

            # Bilgi notu
            hint_label = QLabel("Tarihe çift tıklayarak o güne gidin")
            hint_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; padding: 2px 0;")
            layout.addWidget(hint_label)
        else:
            # Sonuç yoksa bilgilendirme mesajı
            empty_label = QLabel("Bu kelimeyle eslesen kayit bulunamadi.")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;"
            )
            layout.addWidget(empty_label)

        # ── Kapat butonu ──────────────────────────────────────────────────
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Listedeki ögeye tıklandığında 'Git' butonu aktif hale gelir (görsel geri bildirim)."""
        pass  # Seçim güncellendi, ileride genişletilebilir

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Listedeki ögeye çift tıklandığında ilgili tarihe gider."""
        date_str = item.data(Qt.ItemDataRole.UserRole)
        if date_str:
            self.date_selected.emit(date_str)
            self.close()

    def _apply_stylesheet(self) -> None:
        """Diyalog stil ayarları."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
            }}
            QListWidget#resultList {{
                background-color: {BG_WIDGET};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 10px;
                padding: 6px;
                outline: none;
            }}
            QListWidget#resultList::item {{
                padding: 10px 12px;
                border-radius: 8px;
                margin: 3px 2px;
                line-height: 1.5;
                min-height: 48px;
            }}
            QListWidget#resultList::item:hover {{
                background-color: #2A2A2A;
            }}
            QListWidget#resultList::item:selected {{
                background-color: {BG_WIDGET_ALT};
                border-left: 3px solid {ACCENT_RED};
            }}
            QPushButton#closeButton {{
                background-color: {BG_WIDGET};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 13px;
                min-width: 80px;
            }}
            QPushButton#closeButton:hover {{
                background-color: {BG_WIDGET_ALT};
                border-color: {TEXT_SECONDARY};
            }}
        """)
