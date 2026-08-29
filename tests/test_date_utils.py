"""
tests/test_date_utils.py
------------------------
Türkçe tarih biçimlendirme yardımcıları.
"""

from datetime import date

import pytest

from core.date_utils import (
    TURKISH_DAYS,
    TURKISH_MONTHS,
    day_name,
    format_day_and_date,
    format_long,
    format_short,
    month_name,
    parse_iso,
    to_iso,
)


class TestAyVeGunAdlari:
    def test_on_iki_ay_ve_yedi_gun_tanimli(self):
        assert len(TURKISH_MONTHS) == 12
        assert len(TURKISH_DAYS) == 7

    @pytest.mark.parametrize("numara,beklenen", [
        (1, "Ocak"), (3, "Mart"), (8, "Ağustos"), (12, "Aralık"),
    ])
    def test_ay_adi(self, numara, beklenen):
        assert month_name(numara) == beklenen

    @pytest.mark.parametrize("numara,beklenen", [
        (1, "Pazartesi"), (6, "Cumartesi"), (7, "Pazar"),
    ])
    def test_gun_adi(self, numara, beklenen):
        assert day_name(numara) == beklenen

    @pytest.mark.parametrize("gecersiz", [0, 13, -1])
    def test_gecersiz_ay_hata_verir(self, gecersiz):
        with pytest.raises(ValueError):
            month_name(gecersiz)

    @pytest.mark.parametrize("gecersiz", [0, 8, -1])
    def test_gecersiz_gun_hata_verir(self, gecersiz):
        with pytest.raises(ValueError):
            day_name(gecersiz)


class TestIsoDonusumleri:
    def test_gecerli_tarih_cozumlenir(self):
        assert parse_iso("2026-08-29") == date(2026, 8, 29)

    @pytest.mark.parametrize("gecersiz", ["", "29-08-2026", "2026-13-01", "abc", None])
    def test_gecersiz_tarih_none_doner(self, gecersiz):
        assert parse_iso(gecersiz) is None

    def test_to_iso_geri_donusturur(self):
        assert to_iso(date(2026, 1, 5)) == "2026-01-05"

    def test_gidis_donus_tutarli(self):
        assert to_iso(parse_iso("2026-02-28")) == "2026-02-28"


class TestBicimlendirme:
    def test_uzun_bicim(self):
        # 29 Ağustos 2026 bir Cumartesi
        assert format_long("2026-08-29") == "Cumartesi, 29 Ağustos 2026"

    def test_kisa_bicim(self):
        assert format_short("2026-08-29") == "29 Ağustos 2026"

    def test_gun_ve_tarih_iki_satir(self):
        assert format_day_and_date("2026-08-29") == "Cumartesi\n29 Ağustos 2026"

    def test_basindaki_sifir_gosterilmez(self):
        assert format_short("2026-01-05") == "5 Ocak 2026"

    @pytest.mark.parametrize("bicimlendirici", [format_long, format_short, format_day_and_date])
    def test_gecersiz_girdi_oldugu_gibi_doner(self, bicimlendirici):
        # Arayüz çökmesin diye biçimlendiriciler hata fırlatmaz
        assert bicimlendirici("gecersiz-tarih") == "gecersiz-tarih"

    def test_artik_yil_29_subat(self):
        assert format_short("2024-02-29") == "29 Şubat 2024"


class TestTurkceBuyukHarf:
    """
    Regresyon: Python'un str.upper() metodu 'i' -> 'I' yapar, Türkçede
    doğrusu 'İ'dir. Editördeki tarih başlığı "CUMARTESI" yazıyordu.
    """

    @pytest.mark.parametrize("girdi,beklenen", [
        ("Cumartesi", "CUMARTESİ"),
        ("Pazartesi", "PAZARTESİ"),
        ("Nisan", "NİSAN"),
        ("Haziran", "HAZİRAN"),
        ("Ekim", "EKİM"),
    ])
    def test_noktali_i_korunur(self, girdi, beklenen):
        from core.date_utils import upper_tr
        assert upper_tr(girdi) == beklenen

    @pytest.mark.parametrize("girdi,beklenen", [
        ("Salı", "SALI"),
        ("Aralık", "ARALIK"),
        ("Kasım", "KASIM"),
        ("Mayıs", "MAYIS"),
    ])
    def test_noktasiz_i_noktasiz_kalir(self, girdi, beklenen):
        from core.date_utils import upper_tr
        assert upper_tr(girdi) == beklenen

    def test_diger_turkce_harfler_bozulmaz(self):
        from core.date_utils import upper_tr
        assert upper_tr("Çarşamba Perşembe Ağustos Şubat Eylül") == \
               "ÇARŞAMBA PERŞEMBE AĞUSTOS ŞUBAT EYLÜL"

    def test_tam_tarih_basligi(self):
        from core.date_utils import format_long, upper_tr
        assert upper_tr(format_long("2026-08-29")) == "CUMARTESİ, 29 AĞUSTOS 2026"
