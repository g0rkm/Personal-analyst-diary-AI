"""
tests/test_main_window.py
-------------------------
Ana pencere entegrasyonu — özellikle gün değiştirirken kaydedilmemiş
yazının korunması.

QMessageBox testte açılamaz; exec() metodu sahte bir yanıtla değiştirilir.
"""

import pytest

pytest.importorskip("pytestqt", reason="pytest-qt kurulu değil")

pytestmark = pytest.mark.qt


@pytest.fixture
def pencere(qtbot, tmp_path, monkeypatch):
    """Geçici veritabanıyla açılmış bir MainWindow."""
    monkeypatch.setenv("DIARY_DB_PATH", str(tmp_path / "diary.db"))
    monkeypatch.setenv("DIARY_VECTOR_DB_PATH", str(tmp_path / "lance_db"))
    # Model dosyası bulunmasın: AI worker'ları testte başlamasın
    monkeypatch.setenv("DIARY_MODEL_PATH", str(tmp_path / "olmayan-model.gguf"))

    from ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def cevapla(monkeypatch):
    """QMessageBox.exec() yerine sabit bir düğme yanıtı koyar."""
    from PyQt6.QtWidgets import QMessageBox

    def ayarla(dugme):
        monkeypatch.setattr(QMessageBox, "exec", lambda self: dugme)

    return ayarla


def gune_git(pencere, tarih):
    """Takvimde bir güne tıklanmasını taklit eder (selectionChanged tetiklenir)."""
    from PyQt6.QtCore import QDate
    pencere.calendar.setSelectedDate(QDate.fromString(tarih, "yyyy-MM-dd"))


class TestAcilis:
    def test_bugun_yuklenir(self, pencere):
        from PyQt6.QtCore import QDate
        bugun = QDate.currentDate().toString("yyyy-MM-dd")
        assert pencere.editor_panel.get_current_date() == bugun

    def test_baslangicta_temiz(self, pencere):
        assert pencere.editor_panel.is_dirty() is False

    def test_calisan_worker_yok(self, pencere):
        assert pencere._active_workers == set()


class TestGunDegistirme:
    def test_temizken_uyari_cikmadan_gecer(self, pencere, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        cagrildi = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: cagrildi.append(1))

        gune_git(pencere, "2026-08-10")

        assert cagrildi == []
        assert pencere.editor_panel.get_current_date() == "2026-08-10"

    def test_ayni_gune_tiklamak_uyari_cikarmaz(self, pencere, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        cagrildi = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: cagrildi.append(1))

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("yazı")
        gune_git(pencere, "2026-08-10")

        assert cagrildi == []


class TestKaydedilmemisYaziKorumasi:
    """
    Regresyon: takvimde başka bir güne tıklandığında editördeki
    kaydedilmemiş metin uyarısızca siliniyordu.
    """

    def test_kaydet_secilirse_yazi_veritabanina_gider(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("kaybolmaması gereken yazı")
        pencere.editor_panel.rating_widget.set_rating(7)
        cevapla(QMessageBox.StandardButton.Save)

        gune_git(pencere, "2026-08-11")

        kayit = pencere.db.get_entry("2026-08-10")
        assert kayit["content"] == "kaybolmaması gereken yazı"
        assert pencere.editor_panel.get_current_date() == "2026-08-11"

    def test_kaydetme_secilirse_yazi_atilir_ve_gecilir(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("atılacak yazı")
        cevapla(QMessageBox.StandardButton.Discard)

        gune_git(pencere, "2026-08-11")

        assert pencere.db.get_entry("2026-08-10") is None
        assert pencere.editor_panel.get_current_date() == "2026-08-11"

    def test_vazgec_secilirse_ayni_gunde_kalinir(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("korunacak yazı")
        cevapla(QMessageBox.StandardButton.Cancel)

        gune_git(pencere, "2026-08-11")

        assert pencere.editor_panel.get_current_date() == "2026-08-10"
        assert pencere.editor_panel.editor.toPlainText() == "korunacak yazı"

    def test_vazgecince_takvim_secimi_de_geri_alinir(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("korunacak yazı")
        cevapla(QMessageBox.StandardButton.Cancel)

        gune_git(pencere, "2026-08-11")

        assert pencere.calendar.get_selected_date_str() == "2026-08-10"

    def test_puansiz_kayit_engellenirse_gun_degismez(self, pencere, cevapla):
        """Kaydet seçildi ama puan verilmediği için kayıt olmadı: metin durmalı."""
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("puansız yazı")
        cevapla(QMessageBox.StandardButton.Save)

        gune_git(pencere, "2026-08-11")

        assert pencere.editor_panel.get_current_date() == "2026-08-10"
        assert pencere.editor_panel.editor.toPlainText() == "puansız yazı"
        assert pencere.db.get_entry("2026-08-10") is None

    def test_geri_alma_sonsuz_donguye_girmez(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        sayac = {"n": 0}

        def sayan_exec(self):
            sayac["n"] += 1
            return QMessageBox.StandardButton.Cancel

        monkeypatched = QMessageBox.exec
        QMessageBox.exec = sayan_exec
        try:
            gune_git(pencere, "2026-08-10")
            pencere.editor_panel.editor.setPlainText("yazı")
            gune_git(pencere, "2026-08-11")
        finally:
            QMessageBox.exec = monkeypatched

        assert sayac["n"] == 1


class TestArama:
    def test_bos_arama_kullaniciyi_uyarir(self, pencere):
        pencere.search_bar.setText("   ")
        pencere._do_search()
        assert "Aranacak kelimeyi girin" in pencere.search_bar.placeholderText()


class TestIsiHaritasi:
    def test_kayit_sonrasi_takvim_yenilenir(self, pencere, cevapla):
        from PyQt6.QtWidgets import QMessageBox

        gune_git(pencere, "2026-08-10")
        pencere.editor_panel.editor.setPlainText("ısı haritası kaydı")
        pencere.editor_panel.rating_widget.set_rating(6)
        pencere.editor_panel.save_entry()

        assert "2026-08-10" in pencere.db.get_all_entry_dates()
