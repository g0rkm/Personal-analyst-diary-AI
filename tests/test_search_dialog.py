"""
tests/test_search_dialog.py
---------------------------
Arama sonuçları diyaloğu.

Tarih biçimi artık Qt'nin sistem yereline değil core.date_utils'e bağlıdır;
böylece konteynerde (yerel ayar "C") de Türkçe görünür.
"""

import pytest

pytest.importorskip("pytestqt", reason="pytest-qt kurulu değil")

pytestmark = pytest.mark.qt


def sonuc(tarih, icerik):
    return {"date": tarih, "content": icerik, "mood_score": 0, "happiness_score": 5}


class TestSonucListesi:
    def test_sonuclar_listelenir(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("spor", [sonuc("2026-08-29", "bugün spor yaptım")])
        qtbot.addWidget(d)

        assert d.list_widget.count() == 1

    def test_tarih_turkce_gosterilir(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("spor", [sonuc("2026-08-29", "spor")])
        qtbot.addWidget(d)

        assert "29 Ağustos 2026" in d.list_widget.item(0).text()

    def test_tarih_item_verisinde_saklanir(self, qtbot):
        from PyQt6.QtCore import Qt
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("spor", [sonuc("2026-08-29", "spor")])
        qtbot.addWidget(d)

        assert d.list_widget.item(0).data(Qt.ItemDataRole.UserRole) == "2026-08-29"

    def test_uzun_icerik_kisaltilir(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("x", [sonuc("2026-08-29", "x" * 200)])
        qtbot.addWidget(d)

        assert "..." in d.list_widget.item(0).text()

    def test_satir_sonlari_tek_satira_indirilir(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("x", [sonuc("2026-08-29", "birinci\nikinci")])
        qtbot.addWidget(d)

        # Yalnızca tarih ile önizleme arasındaki satır sonu kalmalı
        assert d.list_widget.item(0).text().count("\n") == 1

    def test_cift_tiklama_tarih_sinyali_yayar(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("spor", [sonuc("2026-08-29", "spor")])
        qtbot.addWidget(d)

        with qtbot.waitSignal(d.date_selected, timeout=1000) as blocker:
            d._on_item_double_clicked(d.list_widget.item(0))

        assert blocker.args == ["2026-08-29"]


class TestSonucYok:
    def test_bos_sonucta_turkce_mesaj(self, qtbot):
        from PyQt6.QtWidgets import QLabel
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("bulunmayan", [])
        qtbot.addWidget(d)

        metinler = [w.text() for w in d.findChildren(QLabel)]
        assert any("eşleşen kayıt bulunamadı" in m for m in metinler)

    def test_bos_sonucta_liste_olusturulmaz(self, qtbot):
        from ui.search_dialog import SearchResultDialog

        d = SearchResultDialog("bulunmayan", [])
        qtbot.addWidget(d)

        assert not hasattr(d, "list_widget")
