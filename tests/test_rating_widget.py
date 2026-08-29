"""
tests/test_rating_widget.py
---------------------------
1-10 arası mutluluk puanlama widget'ı.
"""

import pytest

pytest.importorskip("pytestqt", reason="pytest-qt kurulu değil")

pytestmark = pytest.mark.qt


@pytest.fixture
def widget(qtbot):
    from ui.rating_widget import RatingWidget
    w = RatingWidget()
    qtbot.addWidget(w)
    return w


class TestBaslangic:
    def test_puansiz_baslar(self, widget):
        assert widget.get_rating() == 0

    def test_on_buton_vardir(self, widget):
        assert len(widget._buttons) == 10

    def test_gosterge_puanlanmadi_yazar(self, widget):
        assert widget.mood_indicator.text() == "Puanlanmadı"


class TestPuanSecimi:
    @pytest.mark.parametrize("puan", [1, 5, 10])
    def test_tiklama_puani_ayarlar(self, widget, puan):
        widget._on_button_clicked(puan)
        assert widget.get_rating() == puan

    def test_tiklama_sinyal_yayar(self, widget, qtbot):
        with qtbot.waitSignal(widget.rating_changed, timeout=1000) as blocker:
            widget._on_button_clicked(7)
        assert blocker.args == [7]

    def test_gosterge_etiketi_guncellenir(self, widget):
        from ui.rating_widget import MOOD_LABELS
        widget._on_button_clicked(8)
        assert MOOD_LABELS[8] in widget.mood_indicator.text()
        assert "8/10" in widget.mood_indicator.text()


class TestDisaridanAyarlama:
    def test_set_rating_puani_ayarlar(self, widget):
        widget.set_rating(6)
        assert widget.get_rating() == 6

    def test_set_rating_butonu_da_isaretler(self, widget):
        """Görsel stil ile QButtonGroup durumu tutarlı olmalı."""
        widget.set_rating(6)
        assert widget._buttons[5].isChecked() is True

    def test_yeni_puan_oncekini_iptal_eder(self, widget):
        widget.set_rating(3)
        widget.set_rating(9)
        assert widget._buttons[2].isChecked() is False
        assert widget._buttons[8].isChecked() is True

    def test_sifir_puani_sifirlar(self, widget):
        widget.set_rating(7)
        widget.set_rating(0)
        assert widget.get_rating() == 0
        assert all(not b.isChecked() for b in widget._buttons)

    @pytest.mark.parametrize("girdi,beklenen", [(15, 10), (99, 10), (-5, 0)])
    def test_aralik_disi_degerler_kirpilir(self, widget, girdi, beklenen):
        widget.set_rating(girdi)
        assert widget.get_rating() == beklenen


class TestSifirlama:
    def test_sifirlama_gostergeyi_temizler(self, widget):
        widget.set_rating(8)
        widget._reset_rating()
        assert widget.mood_indicator.text() == "Puanlanmadı"

    def test_sifirlama_sinyal_yayar(self, widget, qtbot):
        widget.set_rating(8)
        with qtbot.waitSignal(widget.rating_changed, timeout=1000) as blocker:
            widget._reset_rating()
        assert blocker.args == [0]


class TestUyari:
    def test_flash_warning_mesaj_gosterir(self, widget):
        widget.flash_warning()
        assert "Önce puanlama yapın" in widget.mood_indicator.text()


class TestEtiketler:
    def test_tum_puanlarin_etiketi_var(self):
        from ui.rating_widget import MOOD_LABELS
        assert set(MOOD_LABELS) == set(range(11))

    def test_etiketler_bos_degil(self):
        from ui.rating_widget import MOOD_LABELS
        assert all(etiket.strip() for etiket in MOOD_LABELS.values())
