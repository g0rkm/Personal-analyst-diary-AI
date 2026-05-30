"""
ui/styles.py
------------
Modern gradient tema — tüm renk sabitleri ve QSS tanımları.
Glassmorphism yüzeyler, yumuşak geçişler, derin gölgeler.
"""

# ── Gradient Renk Paleti ────────────────────────────────────────────────────

# Arka plan gradyanı (koyu lacivert-siyah)
BG_GRADIENT_TOP    = "#0D0D1A"
BG_GRADIENT_BOTTOM = "#1A1A2E"

# Widget yüzeyleri (glassmorphism)
GLASS_BG           = "rgba(255, 255, 255, 0.04)"
GLASS_BORDER       = "rgba(255, 255, 255, 0.08)"
GLASS_HOVER        = "rgba(255, 255, 255, 0.08)"

# Solid widget arka planları
BG_DARK            = "#0D0D1A"
BG_WIDGET          = "#16162A"
BG_WIDGET_ALT      = "#1E1E35"
BG_SIDEBAR         = "#12121F"
BG_CARD            = "#1C1C30"
BG_HOVER           = "#252540"
BG_HEADER          = "#0D0D1A"

# Metin renkleri
TEXT_PRIMARY       = "#F0F0FF"
TEXT_SECONDARY     = "#9090B0"
TEXT_MUTED         = "#5A5A7A"
TEXT_ACCENT        = "#FFFFFF"

# Vurgu renkleri
ACCENT_RED         = "#E84545"
ACCENT_RED_DIM     = "#C03535"
ACCENT_RED_GLOW    = "rgba(232, 69, 69, 0.25)"
ACCENT_RED_BG      = "rgba(232, 69, 69, 0.12)"

# Sınır renkleri
BORDER_COLOR       = "rgba(255, 255, 255, 0.07)"
BORDER_FOCUS       = "#E84545"
BORDER_SUBTLE      = "rgba(255, 255, 255, 0.04)"

# Başarı / nötr
SUCCESS_GREEN      = "#2ECC71"
NEUTRAL_BLUE       = "#5B7CFA"


# ── Ana QSS Stil Sayfası ────────────────────────────────────────────────────

MAIN_STYLESHEET = f"""
/* ── Genel ─────────────────────────────────────────────── */
QMainWindow {{
    background-color: {BG_DARK};
}}
QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Arial', sans-serif;
    font-size: 13px;
}}

/* ── Ana içerik widget'ı ───────────────────────────────── */
QWidget#centralWidget {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {BG_GRADIENT_TOP},
        stop:1 {BG_GRADIENT_BOTTOM}
    );
}}

/* ── Arama Çubuğu ──────────────────────────────────────── */
QLineEdit#searchBar {{
    background-color: #16162A;
    color: #F0F0FF;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 13px;
    selection-background-color: #E84545;
}}
QLineEdit#searchBar:focus {{
    border: 2px solid #E84545;
    background-color: #1E1E35;
    padding: 7px 15px; /* Sınır 1px arttığı için, padding'i 1px azalttık */
}}

/* ── Metin Editörü ─────────────────────────────────────── */
QTextEdit#diaryEditor {{
    background-color: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 16px;
    padding: 20px;
    font-size: 14px;
    line-height: 1.8;
    selection-background-color: {ACCENT_RED};
}}
QTextEdit#diaryEditor:focus {{
    border: 1px solid rgba(232, 69, 69, 0.4);
    background-color: {BG_WIDGET_ALT};
}}

/* ── Kaydet Butonu ─────────────────────────────────────── */
QPushButton#saveButton {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_RED},
        stop:1 #C03535
    );
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QPushButton#saveButton:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #F05555,
        stop:1 {ACCENT_RED}
    );
}}
QPushButton#saveButton:pressed {{
    background-color: #A02828;
}}

/* ── Splitter ──────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {BORDER_COLOR};
    width: 1px;
}}

/* ── Scroll Bar ────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_RED};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_RED};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Dialog ────────────────────────────────────────────── */
QDialog {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {BG_GRADIENT_TOP},
        stop:1 {BG_GRADIENT_BOTTOM}
    );
    color: {TEXT_PRIMARY};
}}
QListWidget {{
    background-color: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 0;
}}
QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT_RED_BG};
    color: {TEXT_PRIMARY};
    border-left: 2px solid {ACCENT_RED};
}}

/* ── Mesaj Kutuları ────────────────────────────────────── */
QMessageBox {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
}}
QMessageBox QPushButton {{
    background-color: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    padding: 6px 16px;
    min-width: 60px;
}}
QMessageBox QPushButton:hover {{
    background-color: {ACCENT_RED};
    border-color: {ACCENT_RED};
}}

/* ── Tooltip ───────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ── Chat giriş alanı ──────────────────────────────────── */
QLineEdit#chatInput {{
    background-color: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 20px;
    padding: 8px 14px;
    font-size: 12px;
}}
QLineEdit#chatInput:focus {{
    border: 1px solid rgba(232, 69, 69, 0.5);
}}
"""
