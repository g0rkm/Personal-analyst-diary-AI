"""
ui/rating_widget.py
-------------------
1–10 arası yuvarlak butonlardan oluşan mutluluk puanlama widget'ı.
Seçilen puan kırmızı vurgu rengiyle öne çıkar.
Editör panelinin en üstünde, günlük metinden bağımsız çalışır.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.styles import (
    BG_WIDGET, BG_WIDGET_ALT, BG_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BORDER_COLOR,
    GLASS_BG, GLASS_BORDER
)

# Ruh hali etiketleri (1-10 aralığı için) — emoji olmadan
MOOD_LABELS = {
    0:  "Puanlanmadı",
    1:  "Çok Kötü",
    2:  "Kötü",
    3:  "Yorgun",
    4:  "Sıradan",
    5:  "İdare Eder",
    6:  "İyi",
    7:  "Güzel",
    8:  "Harika",
    9:  "Müthiş",
    10: "Mükemmel",
}


class RatingWidget(QWidget):
    """
    1–10 arası yuvarlak butonlarla mutluluk puanı seçme widget'ı.
    rating_changed sinyali: Kullanıcı puan değiştirince yeni puanı yayar.
    """

    rating_changed = pyqtSignal(int)  # 0 = puanlanmadı, 1-10 arası puan

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_rating: int = 0
        self._buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # ── Başlık satırı ─────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        question_label = QLabel("Bugün ne kadar mutluydun?")
        question_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; "
            f"font-weight: 500; letter-spacing: 0.3px;"
        )
        header_layout.addWidget(question_label)
        header_layout.addStretch()

        # Ruh hali göstergesi
        self.mood_indicator = QLabel("Puanlanmadı")
        self.mood_indicator.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px;"
        )
        header_layout.addWidget(self.mood_indicator)

        main_layout.addLayout(header_layout)

        # ── Buton serisi ──────────────────────────────────────────────────
        btn_container = QWidget()
        btn_container.setStyleSheet(
            f"background: {GLASS_BG}; "
            f"border: 1px solid {GLASS_BORDER}; "
            f"border-radius: 16px; "
        )
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(12, 10, 12, 10)
        btn_layout.setSpacing(6)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for i in range(1, 11):
            btn = QPushButton(str(i))
            btn.setFixedSize(36, 36)
            btn.setCheckable(True)
            btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            btn.setToolTip(f"{i}/10 — {MOOD_LABELS[i]}")
            self._apply_btn_style(btn, selected=False)

            # Tıklama ile puan seçimi
            btn.clicked.connect(lambda checked, score=i: self._on_button_clicked(score))
            self._btn_group.addButton(btn, i)
            self._buttons.append(btn)
            btn_layout.addWidget(btn)

        # Sıfırlama butonu
        reset_btn = QPushButton("✕")
        reset_btn.setFixedSize(28, 28)
        reset_btn.setToolTip("Puanı sıfırla")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: none;
                border-radius: 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {ACCENT_RED};
                background: {ACCENT_RED_BG};
            }}
        """)
        reset_btn.clicked.connect(self._reset_rating)
        btn_layout.addStretch()
        btn_layout.addWidget(reset_btn)

        main_layout.addWidget(btn_container)

    def _apply_btn_style(self, btn: QPushButton, selected: bool) -> None:
        """Butona seçili veya seçili değil stilini uygular."""
        if selected:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 {ACCENT_RED},
                        stop:1 #C03535
                    );
                    color: #FFFFFF;
                    border: 2px solid {ACCENT_RED};
                    border-radius: 18px;
                    font-weight: 700;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_SECONDARY};
                    border: 1.5px solid rgba(255,255,255,0.12);
                    border-radius: 18px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {ACCENT_RED_BG};
                    color: {TEXT_PRIMARY};
                    border-color: {ACCENT_RED};
                }}
            """)

    def _on_button_clicked(self, score: int) -> None:
        """Puan butonuna tıklandığında çağrılır."""
        self._current_rating = score
        self._update_button_visuals()
        self._update_mood_indicator()
        self.rating_changed.emit(score)

    def _reset_rating(self) -> None:
        """Puanı sıfırlar."""
        self._current_rating = 0
        self._btn_group.setExclusive(False)
        for btn in self._buttons:
            btn.setChecked(False)
            self._apply_btn_style(btn, selected=False)
        self._btn_group.setExclusive(True)
        self.mood_indicator.setText("Puanlanmadı")
        self.mood_indicator.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self.rating_changed.emit(0)

    def flash_warning(self) -> None:
        """Puan verilmeden kaydedilmeye çalışıldığında görsel uyarı gösterir."""
        from PyQt6.QtCore import QTimer
        original_style = self.mood_indicator.styleSheet()
        original_text  = self.mood_indicator.text()
        self.mood_indicator.setText("⚠ Önce puanlama yapın!")
        self.mood_indicator.setStyleSheet(f"color: #F0C060; font-size: 12px; font-weight: 600;")
        QTimer.singleShot(2000, lambda: (
            self.mood_indicator.setText(original_text),
            self.mood_indicator.setStyleSheet(original_style)
        ))

    def _update_button_visuals(self) -> None:
        """Seçili butonu vurgular, diğerlerini normale döndürür."""
        for i, btn in enumerate(self._buttons, start=1):
            self._apply_btn_style(btn, selected=(i == self._current_rating))

    def _update_mood_indicator(self) -> None:
        """Ruh hali göstergesini günceller."""
        label = MOOD_LABELS.get(self._current_rating, "Puanlanmadi")
        self.mood_indicator.setText(f"{label}  ({self._current_rating}/10)")
        if self._current_rating >= 7:
            color = "#5EE87A"
        elif self._current_rating >= 4:
            color = "#F0C060"
        else:
            color = ACCENT_RED
        self.mood_indicator.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 500;")

    def set_rating(self, score: int) -> None:
        """Dışarıdan puan ayarlamak için (DB'den yükleme)."""
        if score == 0:
            self._reset_rating()
            return
        self._current_rating = max(0, min(10, score))
        self._update_button_visuals()
        self._update_mood_indicator()

    def get_rating(self) -> int:
        """Mevcut puanı döner."""
        return self._current_rating
