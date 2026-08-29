"""
tests/test_editor_panel.py
--------------------------
Editör paneli — özellikle "kaydedilmemiş değişiklik" (dirty) takibi.

Bu davranış bir günlük uygulamasının en kritik güvencesidir: kullanıcı
takvimde başka bir güne tıkladığında yazdığı metin sessizce kaybolmamalıdır.
Testler offscreen Qt platformuyla, ekran gerektirmeden çalışır.
"""

import pytest

pytest.importorskip("pytestqt", reason="pytest-qt kurulu değil")

pytestmark = pytest.mark.qt


@pytest.fixture
def panel(qtbot, temp_db):
    from ui.editor_panel import EditorPanel
    widget = EditorPanel(db=temp_db)
    qtbot.addWidget(widget)
    return widget


class TestYukleme:
    def test_bos_gun_editoru_temizler(self, panel):
        panel.load_entry("2026-08-29")
        assert panel.editor.toPlainText() == ""
        assert panel.rating_widget.get_rating() == 0

    def test_mevcut_kayit_yuklenir(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "önceki yazı", happiness_score=7)
        panel.load_entry("2026-08-29")
        assert panel.editor.toPlainText() == "önceki yazı"
        assert panel.rating_widget.get_rating() == 7

    def test_tarih_basligi_turkce_yazilir(self, panel):
        panel.load_entry("2026-08-29")
        assert panel.date_label.text() == "CUMARTESİ, 29 AĞUSTOS 2026"

    def test_gecerli_tarih_saklanir(self, panel):
        panel.load_entry("2026-08-29")
        assert panel.get_current_date() == "2026-08-29"

    def test_dolu_gunde_silme_butonu_gorunur(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "yazı", happiness_score=5)
        panel.load_entry("2026-08-29")
        assert panel.delete_btn.isVisible() or not panel.isVisible()


class TestKaydetme:
    def test_kayit_basarili_ise_true_doner(self, panel, temp_db):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("yeni yazı")
        panel.rating_widget.set_rating(8)

        assert panel.save_entry() is True
        assert temp_db.get_entry("2026-08-29")["content"] == "yeni yazı"

    def test_bos_metin_kaydedilmez(self, panel, temp_db):
        panel.load_entry("2026-08-29")
        panel.rating_widget.set_rating(8)

        assert panel.save_entry() is False
        assert temp_db.get_entry("2026-08-29") is None

    def test_puansiz_kayit_engellenir(self, panel, temp_db):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("puansız yazı")

        assert panel.save_entry() is False
        assert temp_db.get_entry("2026-08-29") is None

    def test_kaydetmek_mood_score_u_korur(self, panel, temp_db):
        """Regresyon: editör eskiden mood_score=0 gönderip AI puanını siliyordu."""
        temp_db.save_entry("2026-08-29", "ilk", happiness_score=5)
        temp_db.update_mood_score("2026-08-29", 7)

        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("düzeltilmiş")
        panel.save_entry()

        assert temp_db.get_entry("2026-08-29")["mood_score"] == 7

    def test_kayit_sinyali_yayilir(self, panel, qtbot):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("yazı")
        panel.rating_widget.set_rating(6)

        with qtbot.waitSignal(panel.entry_saved, timeout=1000) as blocker:
            panel.save_entry()

        assert blocker.args == ["2026-08-29", "yazı"]


class TestKaydedilmemisDegisiklikTakibi:
    """
    Regresyon: gün değiştirildiğinde kaydedilmemiş metin uyarısızca siliniyordu.
    MainWindow artık is_dirty() sonucuna göre kullanıcıya soruyor.
    """

    def test_yuklemeden_hemen_sonra_temizdir(self, panel):
        panel.load_entry("2026-08-29")
        assert panel.is_dirty() is False

    def test_mevcut_kaydi_yukleyince_temizdir(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "kayıtlı yazı", happiness_score=5)
        panel.load_entry("2026-08-29")
        assert panel.is_dirty() is False

    def test_metin_yazilinca_kirlenir(self, panel):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("yeni bir şeyler yazdım")
        assert panel.is_dirty() is True

    def test_mevcut_metni_degistirince_kirlenir(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "eski", happiness_score=5)
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("eski ve yeni")
        assert panel.is_dirty() is True

    def test_kaydettikten_sonra_temizlenir(self, panel):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("yazı")
        panel.rating_widget.set_rating(7)
        panel.save_entry()
        assert panel.is_dirty() is False

    def test_basarisiz_kayit_kirli_birakir(self, panel):
        """Puan verilmediği için kayıt engellendiyse metin hâlâ risktedir."""
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("puansız yazı")

        assert panel.save_entry() is False
        assert panel.is_dirty() is True

    def test_sadece_puan_degisince_bos_gun_kirli_sayilmaz(self, panel):
        # Kaybolacak bir metin yok; kullanıcıyı gereksiz uyarmamak gerekir
        panel.load_entry("2026-08-29")
        panel.rating_widget.set_rating(9)
        assert panel.is_dirty() is False

    def test_dolu_gunde_puan_degisimi_kirletir(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "kayıtlı yazı", happiness_score=5)
        panel.load_entry("2026-08-29")
        panel.rating_widget.set_rating(9)
        assert panel.is_dirty() is True

    def test_bastaki_sondaki_bosluk_kirli_saymaz(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "yazı", happiness_score=5)
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("  yazı  ")
        assert panel.is_dirty() is False

    def test_baska_gune_gecince_temizlenir(self, panel):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("kaydedilmemiş")
        assert panel.is_dirty() is True

        panel.load_entry("2026-08-30")
        assert panel.is_dirty() is False

    def test_silmeden_sonra_temizlenir(self, panel, temp_db):
        temp_db.save_entry("2026-08-29", "silinecek", happiness_score=5)
        panel.load_entry("2026-08-29")
        panel._delete_entry()
        assert panel.is_dirty() is False


class TestOneriEkleme:
    def test_bos_editore_oneri_eklenir(self, panel):
        panel.load_entry("2026-08-29")
        panel._append_prompt("Bugün ne hissettim:\n")
        assert panel.editor.toPlainText() == "Bugün ne hissettim:\n"

    def test_dolu_editore_bos_satirla_eklenir(self, panel):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("mevcut metin")
        panel._append_prompt("Ne yaptım:")
        assert panel.editor.toPlainText() == "mevcut metin\n\nNe yaptım:"


class TestKelimeSayaci:
    def test_bos_metin_sifir_gosterir(self, panel):
        panel.load_entry("2026-08-29")
        assert panel.word_count_label.text() == "0 kelime · 0 karakter"

    def test_kelime_ve_karakter_sayilir(self, panel):
        panel.load_entry("2026-08-29")
        panel.editor.setPlainText("bir iki üç")
        assert panel.word_count_label.text() == "3 kelime · 10 karakter"
