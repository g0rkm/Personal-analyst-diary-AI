"""
tests/test_time_range.py
------------------------
Akıllı Yönlendirici'nin zaman çözümleyicisi.

Buradaki en kritik testler "yanlış eşleşme" testleridir: eskiden ay adları
düz substring aramasıyla bulunuyor, "çekimser" -> Ekim, "smart" -> Mart,
"kasımpatı" -> Kasım olarak algılanıyor ve sıradan sorular yanlışlıkla
aylık rapor moduna düşüyordu.
"""

from datetime import date

import pytest

from core.time_range import parse_time_range

# 29 Ağustos 2026, Cumartesi — tüm testlerin referans günü
BUGUN = date(2026, 8, 29)


def aralik(sorgu, bugun=BUGUN):
    """Yardımcı: sadece tarih aralığını döner."""
    return parse_time_range(sorgu, bugun)[0]


class TestZamanIfadesiYok:
    @pytest.mark.parametrize("sorgu", [
        "spora ne zaman başlamıştım",
        "kendimi neden kötü hissediyorum",
        "en mutlu olduğum günlerde ortak ne var",
        "",
    ])
    def test_zaman_ifadesi_olmayan_sorgular(self, sorgu):
        assert parse_time_range(sorgu, BUGUN) == (None, None)

    def test_none_sorgu(self):
        assert parse_time_range(None, BUGUN) == (None, None)


class TestYanlisEslesmeler:
    """Ay adı BAŞKA bir kelimenin içinde geçiyorsa eşleşmemeli."""

    @pytest.mark.parametrize("sorgu,yakalanan_ay", [
        ("çekimser kaldığım günler", "Ekim"),
        ("çekimserlik neden", "Ekim"),
        ("smart saat aldım", "Mart"),
        ("kasımpatı çiçeği aldım", "Kasım"),
    ])
    def test_kelime_icindeki_ay_adi_yakalanmaz(self, sorgu, yakalanan_ay):
        assert aralik(sorgu) is None, f"{sorgu!r} yanlışlıkla {yakalanan_ay} olarak algılandı"


class TestAyAdlari:
    @pytest.mark.parametrize("sorgu", [
        "ocak ayında ne oldu",
        "ocakta ne yaptım",
        "Ocak'ta ne yaptım",
        "ocaktan beri",
        "OCAK ayı nasıldı",
    ])
    def test_ocak_cesitli_eklerle(self, sorgu):
        assert aralik(sorgu) == ("2026-01-01", "2026-01-31")

    def test_icinde_bulunulan_ay_bugune_kadar(self):
        # Ağustos'tayken "Ağustos" sorulursa gelecek günler dahil edilmez
        assert aralik("ağustosta ne yaptım") == ("2026-08-01", "2026-08-29")

    def test_gelecek_ay_onceki_yildan_alinir(self):
        # Ağustos 2026'dayken "Aralık" denince kastedilen Aralık 2025'tir
        assert aralik("aralıkta ne oldu") == ("2025-12-01", "2025-12-31")

    def test_subat_gun_sayisi_dogru(self):
        assert aralik("şubatta ne yaptım") == ("2026-02-01", "2026-02-28")

    def test_artik_yilda_subat_29_cektir(self):
        assert aralik("şubatta ne yaptım", date(2024, 6, 1)) == ("2024-02-01", "2024-02-29")


class TestGoreliIfadeler:
    def test_gecen_ay(self):
        assert aralik("geçen ay ruh halim nasıldı") == ("2026-07-01", "2026-07-31")

    def test_bu_ay_bugune_kadar(self):
        assert aralik("bu ay genel ruh halim") == ("2026-08-01", "2026-08-29")

    def test_bu_hafta_pazartesiden_bugune(self):
        # 29 Ağustos 2026 Cumartesi; o haftanın Pazartesi'si 24 Ağustos
        assert aralik("bu hafta en çok neyi erteledim") == ("2026-08-24", "2026-08-29")

    def test_gecen_hafta_pazartesi_pazar(self):
        assert aralik("geçen hafta nasıldım") == ("2026-08-17", "2026-08-23")

    def test_bu_yil(self):
        assert aralik("bu yıl nasıl geçti") == ("2026-01-01", "2026-08-29")

    def test_gecen_yil(self):
        assert aralik("geçen yıl neler yaptım") == ("2025-01-01", "2025-12-31")

    def test_dun(self):
        assert aralik("dün ne yaptım") == ("2026-08-28", "2026-08-28")

    def test_bugun(self):
        assert aralik("bugün nasıl geçti") == ("2026-08-29", "2026-08-29")

    def test_gecen_ay_yil_sinirini_asar(self):
        # Ocak'tayken "geçen ay" bir önceki yılın Aralık'ıdır
        assert aralik("geçen ay", date(2026, 1, 15)) == ("2025-12-01", "2025-12-31")

    def test_bu_hafta_pazartesi_gunu(self):
        # Pazartesi'yken "bu hafta" tek günlük bir aralıktır
        pazartesi = date(2026, 8, 24)
        assert aralik("bu hafta", pazartesi) == ("2026-08-24", "2026-08-24")


class TestOncelikSirasi:
    def test_gecen_ay_bu_aydan_once_denenir(self):
        # "geçen ay" ifadesi "bu ay" içermez ama sıralama yine de doğrulanmalı
        assert aralik("geçen ay") == ("2026-07-01", "2026-07-31")

    def test_yil_aydan_once_gelir(self):
        assert aralik("geçen yıl bu ay") == ("2025-01-01", "2025-12-31")


class TestMesajlar:
    @pytest.mark.parametrize("sorgu,parca", [
        ("geçen ay", "Geçen ay"),
        ("bu hafta", "Bu haftaki"),
        ("ocakta", "Ocak ayı"),
        ("dün", "Dünkü"),
    ])
    def test_yukleniyor_mesaji_bilgilendirici(self, sorgu, parca):
        _, mesaj = parse_time_range(sorgu, BUGUN)
        assert mesaj is not None and parca in mesaj
