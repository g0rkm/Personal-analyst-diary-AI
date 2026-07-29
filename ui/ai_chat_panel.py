"""
ui/ai_chat_panel.py
-------------------
AI asistan chat paneli — sağ tarafta açılır-kapanır sidebar.
Model indirme, RAG sohbeti ve arayüzü yönetir.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor

from ui.styles import (
    BG_DARK, BG_WIDGET, BG_CARD, BG_SIDEBAR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_RED, ACCENT_RED_BG, BORDER_COLOR, GLASS_BG, GLASS_BORDER
)

from ai.rag_engine import RAGEngine
from ai.worker import ModelDownloadWorker, RAGChatWorker
from settings import load_settings

SAMPLE_QUESTIONS = [
    "Geçen ay en çok neyi erteledim?",
    "Stresli olduğumda bana ne iyi geliyor?",
    "Bu ay genel ruh halim nasıldı?",
    "En mutlu olduğum günlerde ortak ne var?",
]


class ChatBubble(QWidget):
    """Tek bir chat mesajı balonu."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.label = QLabel(text)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.label.setWordWrap(True)
        self.label.setFont(QFont("Segoe UI", 12))
        self.label.setMaximumWidth(220)

        if self.is_user:
            self.label.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_RED}, stop:1 #C03535);
                    color: #FFFFFF;
                    border-radius: 14px 14px 4px 14px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addStretch()
            layout.addWidget(self.label)
        else:
            self.label.setStyleSheet(f"""
                QLabel {{
                    background: {BG_CARD};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 14px 14px 14px 4px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addWidget(self.label)
            layout.addStretch()

    def append_text(self, text: str):
        """Streaming sırasında metin ekler."""
        current = self.label.text()
        self.label.setText(current + text)


class AIChatPanel(QWidget):
    COLLAPSED_WIDTH = 52
    EXPANDED_WIDTH  = 280

    # Rag engine'in dışarıdan atanması için (main_window'dan)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self.rag_engine = None
        self.chat_worker = None
        self.download_worker = None
        self._current_ai_bubble = None
        self._chat_history = []  # Sohbet geçmişi — modelin bağlamı takip etmesi için
        self._current_user_query = ""  # Yanıt tamamlandığında geçmişe eklemek için
        self._current_ai_response = ""  # Streaming sırasında toplanan tam yanıt
        self.last_date_range = None  # Kontekst hafızası (SQL yönlendirme için)
        
        self._thinking_timer = QTimer(self)
        self._thinking_timer.timeout.connect(self._update_thinking_animation)
        self._thinking_dots = 0
        self._thinking_base_text = "Düşünüyor"
        
        self._setup_ui()
        self.setFixedWidth(self.COLLAPSED_WIDTH)
        self._check_model_status()

    def set_rag_engine(self, rag_engine: RAGEngine):
        self.rag_engine = rag_engine

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

        # Toggle Butonu
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedHeight(36)
        self._toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle_btn.setToolTip("AI Asistanı Aç/Kapat")
        self._toggle_btn.clicked.connect(self.toggle)
        self._update_toggle_style(expanded=False)
        self._main_layout.addWidget(self._toggle_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        self._main_layout.addWidget(sep)

        # Geniş İçerik
        self._content_widget = QWidget()
        self._content_widget.setVisible(False)
        self._content_widget.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # Başlık ve Badge
        header_layout = QHBoxLayout()
        header_label = QLabel("AI Asistan")
        header_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 700; letter-spacing: 0.5px;")
        header_layout.addWidget(header_label)
        
        self.beta_label = QLabel("Aktif Değil")
        self.beta_label.setStyleSheet(f"""
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
        self.beta_label.setFixedHeight(22)
        header_layout.addWidget(self.beta_label)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        # İndirme Ekranı (Model Yoksa)
        self._download_widget = QWidget()
        dl_layout = QVBoxLayout(self._download_widget)
        dl_layout.setContentsMargins(0,0,0,0)
        
        dl_info = QLabel("AI Asistanı kullanabilmek için yerel modelin (~1.9 GB) indirilmesi gerekiyor. Bu işlem sadece bir kez yapılacaktır.")
        dl_info.setWordWrap(True)
        dl_info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        dl_layout.addWidget(dl_info)
        
        self.dl_btn = QPushButton("Modeli İndir")
        self.dl_btn.setStyleSheet(f"background: {ACCENT_RED}; color: white; border-radius: 4px; padding: 6px;")
        self.dl_btn.clicked.connect(self._start_download)
        dl_layout.addWidget(self.dl_btn)
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setVisible(False)
        self.dl_progress.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {BORDER_COLOR}; border-radius: 4px; text-align: center; color: white; }}
            QProgressBar::chunk {{ background-color: {ACCENT_RED}; }}
        """)
        dl_layout.addWidget(self.dl_progress)
        
        self.dl_status = QLabel("")
        self.dl_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        dl_layout.addWidget(self.dl_status)
        
        content_layout.addWidget(self._download_widget)

        # Chat Geçmişi
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()
        self._chat_scroll.setWidget(self._chat_container)
        content_layout.addWidget(self._chat_scroll)

        # Soru Önerileri (Sadece Model Varken ve Chat Boşken)
        self._suggestions_widget = QWidget()
        sugg_layout = QVBoxLayout(self._suggestions_widget)
        sugg_layout.setContentsMargins(0,0,0,0)
        sugg_label = QLabel("Örnek sorular:")
        sugg_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        sugg_layout.addWidget(sugg_label)
        for q in SAMPLE_QUESTIONS:
            btn = QPushButton(q)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {GLASS_BG}; color: {TEXT_SECONDARY};
                    border: 1px solid {GLASS_BORDER}; border-radius: 8px;
                    padding: 6px 8px; text-align: left; font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {ACCENT_RED}15; border-color: {ACCENT_RED}44; color: {TEXT_PRIMARY};
                }}
            """)
            btn.clicked.connect(lambda _, text=q: self._set_input_text(text))
            sugg_layout.addWidget(btn)
        content_layout.addWidget(self._suggestions_widget)

        # Giriş Alanı
        self.input_layout_widget = QWidget()
        input_layout = QHBoxLayout(self.input_layout_widget)
        input_layout.setContentsMargins(0,0,0,0)
        input_layout.setSpacing(6)

        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Günlüğüne sor...")
        self._chat_input.setFixedHeight(36)
        self._chat_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._chat_input, stretch=1)

        self.send_btn = QPushButton(">")
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.send_btn.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT_RED}; color: #FFFFFF; border: none; border-radius: 18px; font-size: 14px; }}
            QPushButton:hover {{ background: #F05555; }}
            QPushButton:pressed {{ background: #A02828; }}
            QPushButton:disabled {{ background: {BORDER_COLOR}; color: {TEXT_MUTED}; }}
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        content_layout.addWidget(self.input_layout_widget)

        self._main_layout.addWidget(self._content_widget, stretch=1)

    def _check_model_status(self):
        settings = load_settings()
        model_path = settings.get("model_path", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
        if os.path.exists(model_path):
            self._download_widget.setVisible(False)
            self.input_layout_widget.setVisible(True)
            self._suggestions_widget.setVisible(True)
            self.beta_label.setText("Aktif")
            self.beta_label.setStyleSheet(f"""
                QLabel {{
                    background: #28a74522; color: #28a745;
                    border: 1px solid #28a74544; border-radius: 8px;
                    padding: 2px 8px; font-size: 10px; font-weight: 600;
                }}
            """)
        else:
            self._download_widget.setVisible(True)
            self.input_layout_widget.setVisible(False)
            self._suggestions_widget.setVisible(False)
            self._chat_scroll.setVisible(False)

    def _start_download(self):
        self.dl_btn.setEnabled(False)
        self.dl_progress.setVisible(True)
        self.dl_status.setText("İndiriliyor... Lütfen bekleyin.")
        
        settings = load_settings()
        model_path = settings.get("model_path", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
        model_url = settings.get("model_url", "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf")
        
        self.download_worker = ModelDownloadWorker(model_url, model_path)
        self.download_worker.progress.connect(self.dl_progress.setValue)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_finished(self, success: bool, message: str):
        if success:
            self._check_model_status()
        else:
            self.dl_status.setText(message)
            self.dl_btn.setEnabled(True)
            self.dl_progress.setVisible(False)

    def _update_toggle_style(self, expanded: bool) -> None:
        if expanded:
            self._toggle_btn.setText("✕")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{ background: {ACCENT_RED_BG}; color: {ACCENT_RED}; border: 1px solid rgba(232,69,69,0.3); border-radius: 0; font-size: 15px; padding: 0; }}
                QPushButton:hover {{ background: rgba(232,69,69,0.2); color: #FF6666; }}
            """)
        else:
            self._toggle_btn.setText("AI")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: none; border-radius: 0; font-size: 16px; padding: 0; font-weight: bold; }}
                QPushButton:hover {{ color: {ACCENT_RED}; background: {ACCENT_RED_BG}; }}
            """)

    def toggle(self) -> None:
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self.setFixedWidth(self.EXPANDED_WIDTH)
            self._content_widget.setVisible(True)
        else:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self._content_widget.setVisible(False)
        self._update_toggle_style(self._is_expanded)

    def _set_input_text(self, text: str) -> None:
        self._chat_input.setText(text)
        self._chat_input.setFocus()

    def _send_message(self) -> None:
        text = self._chat_input.text().strip()
        if not text or not self.rag_engine:
            return

        self._suggestions_widget.setVisible(False)
        self._chat_scroll.setVisible(True)
        
        # UI Kilit
        self._chat_input.clear()
        self._chat_input.setEnabled(False)
        self.send_btn.setEnabled(False)

        # Kullanıcı mesajını ekle
        self._add_bubble(text, is_user=True)
        
        # Mevcut soruyu ve boş yanıt değişkenini kaydet
        self._current_user_query = text
        self._current_ai_response = ""

        # AI yanıtı için boş balon oluştur
        self._thinking_base_text = "Düşünüyor"
        self._current_ai_bubble = self._add_bubble(self._thinking_base_text, is_user=False)
        
        # Düşünme animasyonunu başlat
        self._thinking_dots = 0
        self._thinking_timer.start(400)

        # Arka planda çalıştır — sohbet geçmişini ve aktif zaman aralığını da gönder
        self.chat_worker = RAGChatWorker(self.rag_engine, text, self._chat_history.copy(), self.last_date_range)
        self.chat_worker.token_received.connect(self._on_token_received)
        self.chat_worker.mode_detected.connect(self._on_mode_detected)
        self.chat_worker.finished.connect(self._on_chat_finished)
        self.chat_worker.error.connect(self._on_chat_error)
        self.chat_worker.start()

    def _on_mode_detected(self, mode: str, loading_message: str):
        self._thinking_base_text = loading_message
        if self._current_ai_bubble and self._current_ai_response == "":
            self._current_ai_bubble.label.setText(self._thinking_base_text)

    def _update_thinking_animation(self):
        if self._current_ai_bubble and self._current_ai_response == "":
            self._thinking_dots = (self._thinking_dots + 1) % 4
            self._current_ai_bubble.label.setText(self._thinking_base_text + "." * self._thinking_dots)

    def _on_token_received(self, token: str):
        if self._current_ai_bubble:
            # İlk token geldiğinde timer'ı durdur ve metni temizle
            if self._current_ai_response == "":
                self._thinking_timer.stop()
                self._current_ai_bubble.label.setText("")
                
            self._current_ai_bubble.append_text(token)
            self._current_ai_response += token  # Tam yanıtı biriktir
            self._scroll_to_bottom()

    def _on_chat_finished(self, new_date_range=None):
        self._thinking_timer.stop()
        self.last_date_range = new_date_range
        # Tamamlanan soru-cevap çiftini geçmişe ekle
        if self._current_user_query and self._current_ai_response:
            self._chat_history.append({"role": "user", "content": self._current_user_query})
            self._chat_history.append({"role": "assistant", "content": self._current_ai_response})
        
        self._chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self._chat_input.setFocus()
        self._current_ai_bubble = None
        self._current_user_query = ""
        self._current_ai_response = ""

    def _on_chat_error(self, error_msg: str):
        self._thinking_timer.stop()
        if self._current_ai_bubble:
            self._current_ai_bubble.label.setText(f"Hata oluştu: {error_msg}")
        self._on_chat_finished()

    def _add_bubble(self, text: str, is_user: bool) -> ChatBubble:
        count = self._chat_layout.count()
        if count > 0:
            stretch_item = self._chat_layout.takeAt(count - 1)

        bubble = ChatBubble(text, is_user)
        self._chat_layout.addWidget(bubble)
        self._chat_layout.addStretch()
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))
