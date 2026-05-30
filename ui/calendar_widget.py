"""
ui/calendar_widget.py
---------------------
Özelleştirilmiş QCalendarWidget.
paintCell() override ile her gün yuvarlak daire içinde gösterilir:
  - Boş gün:    beyaz kenarlıklı daire, koyu arka plan
  - Dolu gün:   kırmızı dolgulu daire, beyaz rakam
  - Bugün:      kırmızı noktalı gösterge
  - Seçili gün: parlak kenarlık ve hafif glow efekti
"""

from PyQt6.QtWidgets import QCalendarWidget, QAbstractItemView, QTableView, QFrame
from PyQt6.QtGui import (
    QColor, QTextCharFormat, QBrush, QPainter,
    QPen, QFont, QRadialGradient, QLinearGradient
)
from PyQt6.QtCore import QDate, Qt, QRect, QSize, QRectF

from ui.styles import (
    BG_DARK, BG_WIDGET, BG_WIDGET_ALT, BG_SIDEBAR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, BORDER_COLOR
)


class DiaryCalendar(QCalendarWidget):
    """
    Özelleştirilmiş takvim bileşeni.
    Tüm günler yuvarlak daireler içinde gösterilir.
    Dolu günlerde daire kırmızı renkle doldurulur.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Dolu günler kümesi (YYYY-MM-DD)
        self._filled_dates: set[str] = set()

        self._configure_calendar()
        self._apply_stylesheet()

    def _configure_calendar(self) -> None:
        """Takvim davranış ayarları."""
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setNavigationBarVisible(True)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setGridVisible(False)
        # Minimum boyut
        self.setMinimumSize(280, 260)

        # İç QTableView'ın focus çerçevesini kapat (mor/mavi çubuk)
        table_view = self.findChild(QTableView)
        if table_view:
            table_view.setFrameShape(QFrame.Shape.NoFrame)
            table_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _apply_stylesheet(self) -> None:
        """
        QSS ile takvim stillendirmesi.
        paintCell() custom paint yapacağı için hücre renkleri burada değil,
        sadece navigasyon çubuğu ve genel arka plan stilleştirilir.
        """
        self.setStyleSheet(f"""
            /* Ana widget */
            QCalendarWidget {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: none;
            }}

            /* Navigasyon çubuğu */
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.06),
                    stop:1 rgba(255,255,255,0.02)
                );
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                min-height: 48px;
                padding: 4px;
                margin-bottom: 8px;
            }}

            /* İleri/Geri ok butonları */
            QCalendarWidget QToolButton {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 15px;
                font-weight: bold;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: rgba(232, 69, 69, 0.15);
                color: {ACCENT_RED};
            }}
            QCalendarWidget QToolButton:pressed {{
                background-color: rgba(232, 69, 69, 0.3);
            }}

            /* Ay/Yıl butonları */
            QCalendarWidget QToolButton#qt_calendar_monthbutton,
            QCalendarWidget QToolButton#qt_calendar_yearbutton {{
                font-size: 14px;
                font-weight: 700;
                color: {TEXT_PRIMARY};
                padding: 4px 8px;
                letter-spacing: 0.3px;
            }}
            /* Ay/Yıl düşme ok işaretini gizle */
            QCalendarWidget QToolButton::menu-indicator {{
                image: none;
                width: 0;
                height: 0;
            }}

            /* Açılır menü */
            QCalendarWidget QMenu {{
                background-color: {BG_WIDGET_ALT};
                color: {TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.1);
            }}
            QCalendarWidget QMenu::item {{
                padding: 4px 16px;
            }}
            QCalendarWidget QMenu::item:selected {{
                background-color: {ACCENT_RED};
                color: white;
            }}

            /* Yıl spin box */
            QCalendarWidget QSpinBox {{
                background-color: rgba(255,255,255,0.06);
                color: {TEXT_PRIMARY};
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 2px 6px;
                selection-background-color: {ACCENT_RED};
            }}

            /* Tablo görünümü — paintCell() kendi çizimini yapıyor,
               Qt'nin varsayılan seçim arka planını tamamen gizle */
            QCalendarWidget QAbstractItemView {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                selection-background-color: transparent;
                selection-color: {TEXT_PRIMARY};
                outline: none;
            }}
            QCalendarWidget QAbstractItemView::item {{
                background-color: transparent;
                outline: none;
                border: none;
            }}
            QCalendarWidget QAbstractItemView::item:selected {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QCalendarWidget QAbstractItemView::item:focus {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            /* QTableView focus çerçevesini gizle */
            QCalendarWidget QTableView {{
                outline: none;
                border: none;
            }}

            /* Haftanın günleri başlığı */
            QCalendarWidget QWidget {{
                alternate-background-color: transparent;
            }}
        """)

    # ── Custom Paint ────────────────────────────────────────────────────────

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate) -> None:
        """
        Her takvim hücresini yuvarlak daire içinde çizer.
        - Dolu gün    → kırmızı dolgulu daire
        - Bugün       → kırmızı nokta göstergesi
        - Seçili gün  → parlak kenarlık
        - Boş gün     → soluk beyaz kenarlıklı daire
        - Farklı ay   → çok soluk
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        date_str    = date.toString("yyyy-MM-dd")
        is_filled   = date_str in self._filled_dates
        is_today    = date == QDate.currentDate()
        is_selected = date == self.selectedDate()
        is_other_month = date.month() != self.monthShown()
        is_weekend  = date.dayOfWeek() in (6, 7)  # Cumartesi, Pazar

        # Daire boyutu ve konumu
        size = min(rect.width(), rect.height()) - 6
        size = min(size, 42)  # Maksimum 42px daire
        cx = rect.center().x()
        cy = rect.center().y()
        circle_rect = QRectF(cx - size/2, cy - size/2, size, size)

        # ── Dolu gün: kırmızı dolgu ────────────────────────────────────────
        if is_filled:
            # Radial gradient ile derinlik efekti
            gradient = QRadialGradient(circle_rect.center(), size / 2)
            gradient.setColorAt(0.0, QColor("#F05555"))
            gradient.setColorAt(1.0, QColor("#B02828"))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle_rect)

            # Seçili dolu gün: parlak kenarlık ve sol bar
            if is_selected:
                pen = QPen(QColor("#FFFFFF"), 2.0)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle_rect.adjusted(-1, -1, 1, 1))
                
                # Seçim çubuğunu dairenin soluna yasla
                bar_rect = QRectF(circle_rect.left() - 4, circle_rect.top() + 6, 3, size - 12)
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bar_rect, 1.5, 1.5)

            text_color = QColor("#FFFFFF")

        # ── Seçili boş gün ────────────────────────────────────────────────
        elif is_selected:
            painter.setBrush(QBrush(QColor(ACCENT_RED + "22")))
            pen = QPen(QColor(ACCENT_RED), 1.8)
            painter.setPen(pen)
            painter.drawEllipse(circle_rect)
            
            # Seçim çubuğunu dairenin soluna yasla
            bar_rect = QRectF(circle_rect.left() - 4, circle_rect.top() + 6, 3, size - 12)
            painter.setBrush(QBrush(QColor(ACCENT_RED)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 1.5, 1.5)
            
            text_color = QColor(ACCENT_RED)

        # ── Bugün (boş ve seçili değil) ────────────────────────────────────
        elif is_today:
            painter.setBrush(QBrush(QColor("rgba(232, 69, 69, 0.08)")))
            pen = QPen(QColor(ACCENT_RED), 1.2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawEllipse(circle_rect)
            text_color = QColor(ACCENT_RED)

        # ── Normal boş gün ────────────────────────────────────────────────
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            alpha = 30 if is_other_month else 70
            pen = QPen(QColor(255, 255, 255, alpha), 1.0)
            painter.setPen(pen)
            painter.drawEllipse(circle_rect)

            if is_other_month:
                text_color = QColor(255, 255, 255, 40)
            elif is_weekend:
                text_color = QColor("#C08080")
            else:
                text_color = QColor(TEXT_PRIMARY)

        # ── Gün numarasını dairenin tam ortasına yaz ─────────────────
        font = QFont("Segoe UI", 9)  # Küçük font — sayılar daireye değmez
        font.setBold(is_today or is_selected or is_filled)
        painter.setFont(font)
        painter.setPen(text_color)
        # İç dikdörtgeni biraz küçült — sayıların kenarı daire sınırına değmemesi için
        inner_rect = circle_rect.adjusted(4, 4, -4, -4).toRect()
        painter.drawText(
            inner_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            str(date.day())
        )

        # ── Bugün: küçük nokta göstergesi ─────────────────────────────────
        if is_today and not is_filled:
            dot_radius = 2.5
            dot_x = cx
            dot_y = cy + size / 2 + 4
            painter.setBrush(QBrush(QColor(ACCENT_RED)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                QRectF(dot_x - dot_radius, dot_y - dot_radius,
                       dot_radius * 2, dot_radius * 2)
            )

        painter.restore()

    # ── Isı Haritası ────────────────────────────────────────────────────────

    def refresh_heatmap(self, filled_dates: list[str]) -> None:
        """
        Takvim ısı haritasını günceller.
        filled_dates: Dolu günlerin YYYY-MM-DD formatındaki listesi.
        """
        self._filled_dates = set(filled_dates)
        self.updateCells()  # Tüm hücreleri yeniden çiz

    def get_selected_date_str(self) -> str:
        """Seçili tarihi YYYY-MM-DD formatında döner."""
        return self.selectedDate().toString("yyyy-MM-dd")

    def is_date_filled(self, date_str: str) -> bool:
        """Verilen tarihte kayıt olup olmadığını döner."""
        return date_str in self._filled_dates
