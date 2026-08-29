"""
ui/editor_panel.py
------------------
Sağ taraftaki editör paneli.
Üstten alta: RatingWidget → Öneri toggle → DiaryTextEdit → Alt çubuk.

DiaryTextEdit: QTextEdit alt sınıfı — Ctrl+Arrow kelime navigasyonunu
ve Ctrl+Shift+Arrow çoklu seçimi açıkça destekler.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QTextCursor

from core.date_utils import format_long, format_short, upper_tr
from ui.rating_widget import RatingWidget
from ui.suggestion_widget import SuggestionWidget
from ui.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BG_WIDGET, BG_WIDGET_ALT, BORDER_COLOR, GLASS_BG
)


class DiaryTextEdit(QTextEdit):
    """
    QTextEdit alt sınıfı.
    Ctrl+Arrow ve Ctrl+Shift+Arrow tuş kombinasyonlarının
    üst penceredeki QShortcut'lar tarafından yutulmaması için
    keyPressEvent override edilir.
    """

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        ctrl  = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier
        arrow_keys = (
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Up,   Qt.Key.Key_Down,
            Qt.Key.Key_Home, Qt.Key.Key_End,
        )

        # Ctrl+Arrow veya Ctrl+Shift+Arrow → standart metin navigasyonu
        if key in arrow_keys and (mods & ctrl):
            # QShortcut'ların bu kombinasyona karışmasını önle
            event.accept()
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)


class EditorPanel(QWidget):
    """
    Günlük yazma/görüntüleme paneli.
    entry_saved(date, content) sinyali: Kayıt sonrası takvimi günceller.
    entry_deleted(date) sinyali: Silme sonrası takvimi günceller.
    """

    entry_saved   = pyqtSignal(str, str)
    entry_deleted = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_date: str = QDate.currentDate().toString("yyyy-MM-dd")
        self._is_loading: bool = False
        # Kaydedilmemiş değişiklik tespiti için son kaydedilen/yüklenen durum
        self._baseline_content: str = ""
        self._baseline_rating: int = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Üst başlık ────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 0, 4, 0)

        section = QLabel("Günlük Yazısı")
        section.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600; "
            f"letter-spacing: 0.3px; background: transparent;"
        )
        header_layout.addWidget(section)
        header_layout.addStretch()

        self.date_label = QLabel()
        self.date_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 500; "
            f"letter-spacing: 0.8px; background: transparent;"
        )
        header_layout.addWidget(self.date_label)
        layout.addLayout(header_layout)

        # ── İnce ayırıcı ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR}; border: none;")
        layout.addWidget(sep)

        # ── Mutluluk puanlama ─────────────────────────────────────────────
        self.rating_widget = RatingWidget()
        layout.addWidget(self.rating_widget)

        # ── Öneri toggle butonu + açıklama metni (rating'in hemen altında) ─
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(4, 0, 4, 0)
        toggle_row.setSpacing(8)

        self.suggestion_widget = SuggestionWidget()
        self.suggestion_widget.prompt_selected.connect(self._append_prompt)

        suggestion_toggle_btn = self.suggestion_widget.create_toggle_button()
        toggle_row.addWidget(suggestion_toggle_btn)

        self._suggestion_hint = QLabel("Nasıl başlayacağını bilmiyorsan önerilere bakabilirsin")
        self._suggestion_hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic; background: transparent;"
        )
        toggle_row.addWidget(self._suggestion_hint)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {BORDER_COLOR}; border: none;")
        layout.addWidget(sep2)

        # Öneri kartları paneli
        layout.addWidget(self.suggestion_widget)

        # ── Metin editörü (özel alt sınıf) ───────────────────────────────
        self.editor = DiaryTextEdit()
        self.editor.setObjectName("diaryEditor")
        self.editor.setPlaceholderText(
            "Bugününü buraya yaz..."
        )
        self.editor.setFont(QFont("Segoe UI", 13))
        self.editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.editor.textChanged.connect(self._update_word_count)
        layout.addWidget(self.editor, stretch=1)

        # ── Alt çubuk ─────────────────────────────────────────────────────
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(4, 0, 4, 0)
        bottom_layout.setSpacing(8)

        self.word_count_label = QLabel("0 kelime · 0 karakter")
        self.word_count_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        bottom_layout.addWidget(self.word_count_label)
        bottom_layout.addStretch()

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setObjectName("saveButton")
        self.save_btn.setFixedHeight(38)
        self.save_btn.setToolTip("Ctrl+S ile de kaydedebilirsiniz")
        self._apply_save_btn_style()
        self.save_btn.clicked.connect(self.save_entry)
        bottom_layout.addWidget(self.save_btn)

        # Kaydı Sil butonu
        self.delete_btn = QPushButton("Kaydı Sil")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedHeight(38)
        self.delete_btn.setToolTip("Bu güne ait kaydı kalıcı olarak sil")
        self.delete_btn.setVisible(False)  # Kayıt varsa görünür
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(232, 69, 69, 0.1);
                color: {ACCENT_RED};
                border-color: {ACCENT_RED};
            }}
            QPushButton:pressed {{
                background: rgba(232, 69, 69, 0.2);
            }}
        """)
        self.delete_btn.clicked.connect(self.confirm_delete_entry)
        bottom_layout.addWidget(self.delete_btn)

        layout.addLayout(bottom_layout)

    # ── Genel Metotlar ───────────────────────────────────────────────────────

    def load_entry(self, date_str: str) -> None:
        """Tarihe ait kaydı yükler; yoksa öneri widget'ını gösterir."""
        self._is_loading = True
        self._current_date = date_str

        # Türkçe tarih başlığı (ay/gün adları core.date_utils'te tek kaynakta)
        self.date_label.setText(upper_tr(format_long(date_str)))

        entry = self.db.get_entry(date_str)

        if entry and entry["content"]:
            self.editor.setPlainText(entry["content"])
            self.suggestion_widget.hide_with_animation()
            score = entry["happiness_score"] if entry["happiness_score"] else 0
            self.rating_widget.set_rating(score)
            self.delete_btn.setVisible(True)
        else:
            self.editor.clear()
            self.suggestion_widget.show_with_animation()
            self.rating_widget.set_rating(0)
            self.delete_btn.setVisible(False)

        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        self.editor.setTextCursor(cursor)

        self._is_loading = False
        self._update_word_count()
        self._reset_baseline()

    def save_entry(self) -> bool:
        """
        Editörü ve rating'i veritabanına kaydeder.
        Kayıt gerçekleştiyse True, engellendiyse (boş metin veya puansız) False döner.
        Dönüş değeri, gün değiştirirken veriyi kaybetmemek için kullanılır.
        """
        content = self.editor.toPlainText().strip()
        if not content:
            return False

        happiness = self.rating_widget.get_rating()
        if happiness == 0:
            # Puan verilmeden kaydedilemesin
            self.rating_widget.flash_warning()
            return False

        # mood_score gönderilmez: yapay zekânın hesapladığı duygu puanı korunur
        self.db.save_entry(
            date=self._current_date,
            content=content,
            happiness_score=happiness
        )

        self._reset_baseline()
        self.entry_saved.emit(self._current_date, content)
        self.suggestion_widget.hide_with_animation()
        self.delete_btn.setVisible(True)

        # Görsel geri bildirim
        self.save_btn.setText("Kaydedildi ✓")
        self.save_btn.setStyleSheet(
            f"background: #2E7D3A; color: #FFFFFF; border: none; "
            f"border-radius: 12px; padding: 10px 28px; "
            f"font-size: 13px; font-weight: 600;"
        )
        QTimer.singleShot(1500, self._reset_save_button)
        return True

    def confirm_delete_entry(self) -> None:
        """Silme onayı ister ve onaylanırsa kaydı siler."""
        date_display = format_short(self._current_date)

        msg = QMessageBox(self)
        msg.setWindowTitle("Kaydı Sil")
        msg.setText(f"<b>{date_display}</b> tarihli günlük kaydı silinecek.")
        msg.setInformativeText("Bu işlem geri alınamaz. Devam etmek istiyor musunuz?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Evet, Sil")
        msg.button(QMessageBox.StandardButton.No).setText("İptal")

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._delete_entry()

    def _delete_entry(self) -> None:
        """Kaydı veritabanından siler ve UI'yi sıfırlar."""
        self.db.delete_entry(self._current_date)
        self.editor.clear()
        self.rating_widget.set_rating(0)
        self.suggestion_widget.show_with_animation()
        self.delete_btn.setVisible(False)
        self._reset_baseline()
        self.entry_deleted.emit(self._current_date)

    def _reset_save_button(self) -> None:
        self.save_btn.setText("Kaydet")
        self._apply_save_btn_style()

    def _apply_save_btn_style(self) -> None:
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_RED};
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: #FF5555;
            }}
            QPushButton:pressed {{
                background: #D03030;
            }}
        """)

    def _append_prompt(self, prompt: str) -> None:
        """Öneri kartından gelen metni editöre ekler."""
        current = self.editor.toPlainText()
        if current:
            self.editor.setPlainText(current + "\n\n" + prompt)
        else:
            self.editor.setPlainText(prompt)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _update_word_count(self) -> None:
        if self._is_loading:
            return
        text  = self.editor.toPlainText()
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        self.word_count_label.setText(f"{words} kelime · {chars} karakter")

    def _reset_baseline(self) -> None:
        """Mevcut içeriği "kaydedilmiş" kabul eder (kirli durum sıfırlanır)."""
        self._baseline_content = self.editor.toPlainText().strip()
        self._baseline_rating = self.rating_widget.get_rating()

    def is_dirty(self) -> bool:
        """
        Editörde kaydedilmemiş bir değişiklik var mı?

        Gün değiştirilirken yazılan metnin sessizce kaybolmasını önlemek için
        MainWindow tarafından kullanılır.
        """
        if self._is_loading:
            return False
        content_changed = self.editor.toPlainText().strip() != self._baseline_content
        rating_changed = self.rating_widget.get_rating() != self._baseline_rating
        # Boş bir günde sadece puan verilmişse kaybolacak bir metin yoktur
        if not self.editor.toPlainText().strip():
            return False
        return content_changed or rating_changed

    def get_current_date(self) -> str:
        return self._current_date

    def set_focus_to_editor(self) -> None:
        self.editor.setFocus()
