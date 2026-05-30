"""
ui/ai_chat_panel.py
-------------------
AI asistan chat paneli — sağ tarafta açılır-kapanır sidebar.
Şu an için placeholder yanıtlar üretir.
Gelecekte RAG/LLM entegrasyonuna hazır mimari:
  - send_message() → AI motoruna gönderilecek
  - receive_response() → AI yanıtını ekrana basacak
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QCursor

from ui.styles import (
    BG_DARK, BG_WIDGET, BG_CARD, BG_SIDEBAR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BORDER_COLOR, GLASS_BG, GLASS_BORDER,
    BG_GRADIENT_TOP, BG_GRADIENT_BOTTOM
)

# Yapay zeka için örnek soru önerileri (placeholder dönemde gösterilir)
SAMPLE_QUESTIONS = [
    "Geçen ay en çok neyi erteledim?",
    "Stresli olduğumda bana ne iyi geliyor?",
    "Bu ay genel ruh halim nasıldı?",
    "En mutlu olduğum günlerde ortak ne var?",
]

# Placeholder yanıt mesajları (AI gelene kadar)
PLACEHOLDER_RESPONSES = [
    "AI asistan yakin zamanda burada! Bu ozellik gelistirme asamasinda.",
    "Gecmis gunluklerini analiz edebilmem icin AI entegrasyonu bekleniyor.",
    "Sorularini kaydediyorum. AI aktif oldugunda sana detayli yanit verecegim!",
    "RAG sistemi kuruldugunda gunluklerini gercek zamanli analiz edecegim.",
]

_response_index = 0


class ChatBubble(QWidget):
    """Tek bir chat mesajı balonu."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self._setup_ui(text, is_user)

    def _setup_ui(self, text: str, is_user: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 12))
        bubble.setMaximumWidth(220)

        if is_user:
            # Kullanıcı mesajı — sağda, kırmızı
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {ACCENT_RED},
                        stop:1 #C03535
                    );
                    color: #FFFFFF;
                    border-radius: 14px 14px 4px 14px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            # AI mesajı — solda, koyu widget rengi
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {BG_CARD};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 14px 14px 14px 4px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addWidget(bubble)
            layout.addStretch()


class AIChatPanel(QWidget):
    """
    Sağ kenar AI chat paneli.
    Başlangıçta dar (sadece ikon + başlık görünür),
    toggle ile tam genişliğe açılır.
    """

    # Gelecekte AI motoruna bağlanacak sinyal
    message_sent = pyqtSignal(str)

    COLLAPSED_WIDTH = 52
    EXPANDED_WIDTH  = 280

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self._message_count = 0
        self._setup_ui()
        self.setFixedWidth(self.COLLAPSED_WIDTH)

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BG_SIDEBAR},
                    stop:1 #0F0F20
                );
                border-left: 1px solid {BORDER_COLOR};
            }}
        """)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # ── Toggle butonu (her zaman görünür) ─────────────────────────────
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedHeight(36)
        self._toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle_btn.setToolTip("AI Asistanı Aç/Kapat")
        self._toggle_btn.clicked.connect(self.toggle)
        self._update_toggle_style(expanded=False)
        self._main_layout.addWidget(self._toggle_btn)

        # ── İnce ayırıcı ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        self._main_layout.addWidget(sep)

        # ── Genişletilmiş içerik (başlangıçta gizli) ──────────────────────
        self._content_widget = QWidget()
        self._content_widget.setVisible(False)
        self._content_widget.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # Baslik
        header_label = QLabel("AI Asistan")
        header_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 700; "
            f"letter-spacing: 0.5px;"
        )
        content_layout.addWidget(header_label)

        # Beta badge
        beta_label = QLabel("Yakın Zamanda Aktif")
        beta_label.setStyleSheet(f"""
            QLabel {{
                background: {ACCENT_RED}22;
                color: {ACCENT_RED};
                border: 1px solid {ACCENT_RED}44;
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
        """)
        beta_label.setFixedHeight(22)
        content_layout.addWidget(beta_label)

        # Öneri soruları
        hint_label = QLabel("Örnek sorular:")
        hint_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; margin-top: 4px;")
        content_layout.addWidget(hint_label)

        for q in SAMPLE_QUESTIONS:
            q_btn = QPushButton(q)
            q_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            q_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {GLASS_BG};
                    color: {TEXT_SECONDARY};
                    border: 1px solid {GLASS_BORDER};
                    border-radius: 8px;
                    padding: 6px 8px;
                    text-align: left;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {ACCENT_RED}15;
                    border-color: {ACCENT_RED}44;
                    color: {TEXT_PRIMARY};
                }}
            """)
            q_btn.clicked.connect(lambda _, q=q: self._set_input_text(q))
            content_layout.addWidget(q_btn)

        content_layout.addStretch()

        # ── Chat geçmişi scroll alanı ─────────────────────────────────────
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
        """)
        self._chat_scroll.setVisible(False)  # İlk mesaja kadar gizli

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()
        self._chat_scroll.setWidget(self._chat_container)
        content_layout.addWidget(self._chat_scroll)

        # ── Giriş alanı ───────────────────────────────────────────────────
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        self._chat_input = QLineEdit()
        self._chat_input.setObjectName("chatInput")
        self._chat_input.setPlaceholderText("Günlüğüne sor...")
        self._chat_input.setFixedHeight(36)
        self._chat_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._chat_input, stretch=1)

        send_btn = QPushButton(">")
        send_btn.setFixedSize(36, 36)
        send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_RED};
                color: #FFFFFF;
                border: none;
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #F05555;
            }}
            QPushButton:pressed {{
                background: #A02828;
            }}
        """)
        send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(send_btn)

        content_layout.addLayout(input_layout)

        self._main_layout.addWidget(self._content_widget, stretch=1)

    def _update_toggle_style(self, expanded: bool) -> None:
        """Toggle butonunu açık/kapalı durumuna göre günceller."""
        if expanded:
            self._toggle_btn.setText("✕")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_RED_BG};
                    color: {ACCENT_RED};
                    border: 1px solid rgba(232,69,69,0.3);
                    border-radius: 0;
                    font-size: 15px;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: rgba(232,69,69,0.2);
                    color: #FF6666;
                }}
            """)
        else:
            self._toggle_btn.setText("🤖")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_MUTED};
                    border: none;
                    border-radius: 0;
                    font-size: 20px;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: {ACCENT_RED};
                    background: {ACCENT_RED_BG};
                }}
            """)

    def toggle(self) -> None:
        """Paneli açar veya kapatır (animasyonlu)."""
        self._is_expanded = not self._is_expanded

        if self._is_expanded:
            self.setFixedWidth(self.EXPANDED_WIDTH)
            self._content_widget.setVisible(True)
        else:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self._content_widget.setVisible(False)

        self._update_toggle_style(self._is_expanded)

    def _set_input_text(self, text: str) -> None:
        """Örnek soruyu giriş alanına yazar."""
        self._chat_input.setText(text)
        self._chat_input.setFocus()

    def _send_message(self) -> None:
        """Kullanıcı mesajını gönderir ve placeholder yanıt üretir."""
        global _response_index
        text = self._chat_input.text().strip()
        if not text:
            return

        # Chat geçmişini göster
        self._chat_scroll.setVisible(True)

        # Kullanıcı balonunu ekle
        self._add_bubble(text, is_user=True)
        self._chat_input.clear()
        self.message_sent.emit(text)

        # Placeholder AI yanıtını gecikmeli ekle
        response = PLACEHOLDER_RESPONSES[_response_index % len(PLACEHOLDER_RESPONSES)]
        _response_index += 1
        QTimer.singleShot(600, lambda: self._add_bubble(response, is_user=False))

    def _add_bubble(self, text: str, is_user: bool) -> None:
        """Chat geçmişine mesaj balonu ekler."""
        # Stretch'i kaldır, balonu ekle, tekrar ekle
        count = self._chat_layout.count()
        if count > 0:
            stretch_item = self._chat_layout.takeAt(count - 1)

        bubble = ChatBubble(text, is_user)
        self._chat_layout.addWidget(bubble)
        self._chat_layout.addStretch()

        # En alta kaydır
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def is_expanded(self) -> bool:
        return self._is_expanded
