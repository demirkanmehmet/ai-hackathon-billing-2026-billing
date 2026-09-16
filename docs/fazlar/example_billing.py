"""Basit bir fatura (billing) hesaplama ornegi.

Amaç: proje iskeletinin calistigini ve harici bir kutuphanenin (rich)
kurulup kullanilabildigini gostermek.

Calistirmak icin:
    pip install -r requirements.txt
    python src/example_billing.py
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from rich.console import Console
from rich.table import Table

KDV_ORANI = Decimal("0.20")


@dataclass(frozen=True)
class Kalem:
    """Faturadaki tek bir satir."""

    aciklama: str
    adet: int
    birim_fiyat: Decimal

    @property
    def tutar(self) -> Decimal:
        return para(self.birim_fiyat * self.adet)


def para(deger: Decimal) -> Decimal:
    """Parasal degeri 2 haneye yuvarlar."""
    return deger.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fatura_topla(kalemler: list[Kalem]) -> tuple[Decimal, Decimal, Decimal]:
    """Ara toplam, KDV ve genel toplami dondurur."""
    ara_toplam = para(sum((k.tutar for k in kalemler), Decimal("0")))
    kdv = para(ara_toplam * KDV_ORANI)
    return ara_toplam, kdv, para(ara_toplam + kdv)


def main() -> None:
    kalemler = [
        Kalem("Mobil paket - 20 GB", 1, Decimal("349.90")),
        Kalem("Ek data paketi - 5 GB", 2, Decimal("79.50")),
        Kalem("Yurt disi arama (dk)", 14, Decimal("3.25")),
    ]

    ara_toplam, kdv, genel_toplam = fatura_topla(kalemler)

    tablo = Table(title="Ornek Fatura / Bill & Chill")
    tablo.add_column("Aciklama")
    tablo.add_column("Adet", justify="right")
    tablo.add_column("Birim Fiyat", justify="right")
    tablo.add_column("Tutar", justify="right")

    for kalem in kalemler:
        tablo.add_row(
            kalem.aciklama,
            str(kalem.adet),
            f"{kalem.birim_fiyat} TL",
            f"{kalem.tutar} TL",
        )

    console = Console()
    console.print(tablo)
    console.print(f"Ara toplam : {ara_toplam} TL")
    console.print(f"KDV (%20)  : {kdv} TL")
    console.print(f"[bold]Genel toplam: {genel_toplam} TL[/bold]")


if __name__ == "__main__":
    main()
