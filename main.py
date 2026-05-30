"""
main.py
-------
Uygulamanın giriş noktası.
QApplication'ı başlatır, ana pencereyi oluşturur ve event loop'u çalıştırır.
"""

import sys
import os

# Proje kök dizinini Python yoluna ekle
# (ui ve diğer modüllerin doğru import edilmesi için)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def main() -> None:
    """Uygulamayı başlatır."""
    # Yüksek DPI ekran desteği (4K monitörler için)
    app = QApplication(sys.argv)

    # ── Uygulama meta bilgileri ────────────────────────────────────────────
    app.setApplicationName("Günlük")
    app.setApplicationDisplayName("Günlük — Kişisel Günlük")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DiaryApp")

    # ── Global varsayılan font ─────────────────────────────────────────────
    default_font = QFont("Segoe UI", 13)
    app.setFont(default_font)

    # ── Ana pencereyi oluştur ve göster ───────────────────────────────────
    window = MainWindow()
    window.show()

    # ── Event loop ────────────────────────────────────────────────────────
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
