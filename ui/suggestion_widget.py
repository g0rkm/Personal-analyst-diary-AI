"""
ui/suggestion_widget.py
-----------------------
Açılır-kapanır öneri kartları widget'ı.
RatingWidget'ın sol alt kısmındaki buton ile toggle edilir.
Kullanıcı boş bir gün seçtiğinde görünür, dolu günlerde gizlenir.
Karta tıklanınca ilgili soruyu editöre ekler.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QScrollArea,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QFont, QCursor

from ui.styles import (
    BG_WIDGET, BG_CARD, BG_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BORDER_COLOR,
    GLASS_BG, GLASS_BORDER
)

# Öneri kartı verileri: (başlık, şablon metni, renk tonu, açıklama)
SUGGESTION_CARDS = [
    {
        "title": "Hissiyat",
        "prompt": "Bugün ne hissettim:\n",
        "color": "#5B7CFA",
        "desc": "Duygularını keşfet"
    },
    {
        "title": "Günün Özeti",
        "prompt": "Ne yaptım:\n",
        "color": "#F0C060",
        "desc": "Bugün ne oldu?"
    },
    {
        "title": "Ertelemeler",
        "prompt": "Neyi erteledim:\n",
        "color": ACCENT_RED,
        "desc": "Kaçırdıkların"
    },
    {
        "title": "İyi Gelenler",
        "prompt": "Ne iyi geldi:\n",
        "color": "#5EE87A",
        "desc": "Seni iyi hissettiren"
    },
    {
        "title": "Minnet",
        "prompt": "Bugün minnettar olduğum şeyler:\n",
        "color": "#C87EFF",
        "desc": "Şükran listesi"
    },
    {
        "title": "Öğrendiklerim",
        "prompt": "Bugün öğrendiğim bir şey:\n",
        "color": "#3DD6F5",
        "desc": "Yeni keşifler"
    },
    {
        "title": "Yarın",
        "prompt": "Yarın yapmak istediğim:\n",
        "color": "#FF9F43",
        "desc": "Planlar ve hedefler"
    },
]


class SuggestionCard(QPushButton):
    """Tek bir öneri kartı — tıklanınca editöre metin ekler."""

    clicked_with_prompt = pyqtSignal(str)  # Şablon metnini gönderir

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._setup_ui()
        self.clicked.connect(lambda: self.clicked_with_prompt.emit(data["prompt"]))

    def _setup_ui(self) -> None:
        """Kart görünümünü oluşturur."""
        color = self.data["color"]
        self.setFixedSize(130, 90)
        self.setToolTip(f"{self.data['desc']} — Eklemek için tıkla")
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,0.04),
                    stop:1 rgba(255,255,255,0.02)
                );
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                color: {TEXT_PRIMARY};
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color}22,
                    stop:1 {color}11
                );
                border: 1px solid {color}55;
            }}
            QPushButton:pressed {{
                background: {color}33;
            }}
        """)

        # Kart içeriği
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(4)

        # Başlık — renk çubuğu ile vurgulanmış
        title_label = QLabel(self.data["title"])
        title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 700; "
            f"color: {color}; background: transparent; "
            f"letter-spacing: 0.2px;"
        )
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label)

        # Açıklama
        desc_label = QLabel(self.data["desc"])
        desc_label.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;"
        )
        desc_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(desc_label)

        layout.addStretch()


class SuggestionWidget(QWidget):
    """
    Açılır-kapanır öneri kartları paneli.
    prompt_selected sinyali ile seçilen şablonu editöre gönderir.
    toggle_btn: Dışarıdan (RatingWidget altında) yerleştirilecek toggle butonu referansı.
    """

    prompt_selected = pyqtSignal(str)  # Editöre eklenecek metin

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel_visible = False
        self._setup_ui()
        # Başlangıçta gizli
        self._panel.setVisible(False)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Açılır panel ──────────────────────────────────────────────────
        self._panel = QWidget()
        self._panel.setStyleSheet("background: transparent;")
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 8, 0, 4)
        panel_layout.setSpacing(6)

        # Scroll area ile yatay kart serisi
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(106)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 4px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255,255,255,0.15);
                border-radius: 2px;
            }
        """)

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background: transparent;")
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 8, 0)
        cards_layout.setSpacing(8)

        for card_data in SUGGESTION_CARDS:
            card = SuggestionCard(card_data)
            card.clicked_with_prompt.connect(self.prompt_selected.emit)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        panel_layout.addWidget(scroll)

        main_layout.addWidget(self._panel)

    def create_toggle_button(self) -> QPushButton:
        """
        Rating widget'ın altında konumlandırılmak üzere toggle butonu oluşturur.
        Dönen buton dışarıdan layout'a eklenir.
        """
        self._toggle_btn = QPushButton("💡 Öneriler")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                font-size: 11px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {ACCENT_RED};
                border-color: {ACCENT_RED};
                background: {ACCENT_RED_BG};
            }}
            QPushButton:checked {{
                color: {ACCENT_RED};
                border-color: {ACCENT_RED};
                background: {ACCENT_RED_BG};
            }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_panel)
        return self._toggle_btn

    def _toggle_panel(self) -> None:
        """Öneri panelini açar/kapatır."""
        self._panel_visible = not self._panel_visible
        self._panel.setVisible(self._panel_visible)
        if hasattr(self, "_toggle_btn"):
            self._toggle_btn.setChecked(self._panel_visible)

    def _add_all_prompts(self) -> None:
        """Tüm şablon sorularını birleştirip editöre gönderir."""
        full_template = "\n\n".join(
            c['prompt'] for c in SUGGESTION_CARDS
        )
        self.prompt_selected.emit(full_template)

    def show_with_animation(self) -> None:
        """Widget'ı göster (boş gün açıldığında)."""
        self.setVisible(True)

    def hide_with_animation(self) -> None:
        """Widget'ı gizle (dolu gün açıldığında)."""
        self._panel_visible = False
        self._panel.setVisible(False)
        if hasattr(self, "_toggle_btn"):
            self._toggle_btn.setChecked(False)
        self.setVisible(False)
