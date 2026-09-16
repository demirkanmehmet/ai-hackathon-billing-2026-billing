"""Alarm verisini envanter ve bagimlilik grafigiyle zenginlestirir.

Girdi  : katilimci_paketi/alarms.json, host_inventory.csv, service_dependencies.csv
Cikti  : data/alarms_processed.json  (her alarma `enrichment` blogu eklenmis hali)

Kullanim:
    python src/enrich_alarms.py --ornek              # tek alarm isle ve ekrana yaz
    python src/enrich_alarms.py --ornek ALM-00042    # belirli bir alarmi isle
    python src/enrich_alarms.py                      # tumunu isle ve dosyaya yaz

Zenginlestirme iki kaynaktan gelir:

1. host_inventory.csv -> alarmin dustugu sunucunun is kritikligi ve envanterdeki
   servis kaydi. Envanter servisi ile alarmdaki servis karsilastirilir; uyusmazlik
   `servis_uyumlu` alaninda isaretlenir.

2. service_dependencies.csv -> yonlu bagimlilik grafigi. Kenar yonu:
   kaynak_servis --bagimlidir--> hedef_servis. Yani hedef bozulursa kaynak etkilenir.

   Bu grafikten alarm basina su etiketler uretilir:
     - bagimli_oldugu_servisler : dogrudan yukari komsular (bunlar bozulursa bu servis etkilenir)
     - etkiledigi_servisler     : dogrudan asagi komsular (bu servis bozulursa onlar etkilenir)
     - yayilim_alani            : gecisli asagi kapanis (bu servis bozulursa etkilenecek HER sey)
     - kok_neden_adaylari       : gecisli yukari kapanis (bu alarmin kokunde olabilecek HER servis)
     - grafik_katmani           : altyapi / ara / uc
     - kok_neden_agirligi       : 0.0-1.0, kok neden olma egilimi

`kok_neden_agirligi` neden burada hesaplaniyor: korelasyon fazinda her kume icin
kok aday siralamasi yapilacak. Bu skorun grafikten gelen bileseni alarmdan bagimsiz
(servise ozgu) oldugu icin bir kez, burada hesaplanip alarma yaziliyor.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
PAKET = KOK / "katilimci_paketi"
ALARMS = PAKET / "alarms.json"
HOSTS = PAKET / "host_inventory.csv"
DEPS = PAKET / "service_dependencies.csv"
CIKTI = KOK / "data" / "alarms_processed.json"


# --------------------------------------------------------------------------- #
# Yukleme
# --------------------------------------------------------------------------- #

def envanter_yukle(yol: Path) -> dict[str, dict[str, str]]:
    """host -> envanter satiri."""
    with yol.open(encoding="utf-8-sig", newline="") as f:
        return {satir["host"]: satir for satir in csv.DictReader(f)}


def bagimlilik_yukle(yol: Path) -> list[dict[str, str]]:
    with yol.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class BagimlilikGrafigi:
    """Servis bagimlilik grafigi.

    Kenar: kaynak --bagimlidir--> hedef.
    Ariza yonu kenarin tersidir: hedef bozulursa kaynak etkilenir.
    """

    def __init__(self, kenarlar: list[dict[str, str]]) -> None:
        self.kenarlar = kenarlar
        # servis -> bagimli oldugu hedefler (yukari)
        self.yukari: dict[str, list[dict[str, str]]] = defaultdict(list)
        # servis -> kendisine bagimli kaynaklar (asagi)
        self.asagi: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.servisler: set[str] = set()

        for k in kenarlar:
            kaynak, hedef = k["kaynak_servis"], k["hedef_servis"]
            self.servisler.update((kaynak, hedef))
            self.yukari[kaynak].append(
                {"servis": hedef, "tip": k["bagimlilik_tipi"], "kritiklik": k["kritiklik"]}
            )
            self.asagi[hedef].append(
                {"servis": kaynak, "tip": k["bagimlilik_tipi"], "kritiklik": k["kritiklik"]}
            )

    def _gecisli(self, servis: str, komsuluk: dict[str, list[dict[str, str]]]) -> list[str]:
        """Dongulere karsi korumali genislik oncelikli gecisli kapanis."""
        gorulen: set[str] = set()
        kuyruk = [k["servis"] for k in komsuluk.get(servis, [])]
        while kuyruk:
            s = kuyruk.pop()
            if s in gorulen or s == servis:
                continue
            gorulen.add(s)
            kuyruk.extend(k["servis"] for k in komsuluk.get(s, []))
        return sorted(gorulen)

    def yayilim_alani(self, servis: str) -> list[str]:
        """Bu servis bozulursa gecisli olarak etkilenecek servisler."""
        return self._gecisli(servis, self.asagi)

    def kok_neden_adaylari(self, servis: str) -> list[str]:
        """Bu servisteki bir arizanin kokunde olabilecek gecisli servisler."""
        return self._gecisli(servis, self.yukari)

    def katman(self, servis: str) -> str:
        yukari_var = bool(self.yukari.get(servis))
        asagi_var = bool(self.asagi.get(servis))
        if servis not in self.servisler:
            return "grafik_disi"
        if not yukari_var:
            return "altyapi"   # hicbir seye bagimli degil -> yaprak/altyapi katmani
        if not asagi_var:
            return "uc"        # kimse ona bagimli degil -> tuketici/uc katman
        return "ara"


# --------------------------------------------------------------------------- #
# Zenginlestirme
# --------------------------------------------------------------------------- #

KRITIKLIK_PUAN = {"kritik": 1.0, "yuksek": 0.75, "orta": 0.5, "dusuk": 0.25}


def kok_neden_agirligi(grafik: BagimlilikGrafigi, servis: str, is_kritikligi: str | None) -> float:
    """Servisin kok neden olma egilimi (0.0 - 1.0).

    Uc bilesen:
      - Katman: altyapi katmani kok olmaya en yatkin, uc katman en az.
      - Yayilim genisligi: cok servisi etkileyen bir servis kok oldugunda
        cok alarm uretir; bu da onu iyi bir kok aday yapar.
      - Envanterdeki is kritikligi.
    Agirliklar korelasyon fazinda kalibre edilecek; buradaki degerler baslangic.
    """
    katman_puan = {"altyapi": 1.0, "ara": 0.5, "uc": 0.15, "grafik_disi": 0.0}
    p_katman = katman_puan[grafik.katman(servis)]

    yayilim = len(grafik.yayilim_alani(servis))
    p_yayilim = min(yayilim / 10.0, 1.0)

    p_kritik = KRITIKLIK_PUAN.get(is_kritikligi or "", 0.5)

    return round(0.5 * p_katman + 0.3 * p_yayilim + 0.2 * p_kritik, 3)


def alarmi_zenginlestir(
    alarm: dict[str, Any],
    envanter: dict[str, dict[str, str]],
    grafik: BagimlilikGrafigi,
) -> dict[str, Any]:
    """Alarmin zenginlestirilmis kopyasini dondurur. Girdi degistirilmez."""
    servis = alarm["service"]
    host = alarm["host"]
    env = envanter.get(host)

    yukari = grafik.yukari.get(servis, [])
    asagi = grafik.asagi.get(servis, [])
    yayilim = grafik.yayilim_alani(servis)
    kok_adaylari = grafik.kok_neden_adaylari(servis)
    is_krit = env["is_kritikligi"] if env else None

    zengin = dict(alarm)
    zengin["enrichment"] = {
        "host_bilgisi": {
            "eslesti": env is not None,
            "envanter_servisi": env["servis"] if env else None,
            "servis_uyumlu": (env["servis"] == servis) if env else None,
            "is_kritikligi": is_krit,
            "veri_merkezi": env["veri_merkezi"] if env else None,
            "kabin": env["kabin"] if env else None,
        },
        "bagimlilik": {
            "grafikte_var": servis in grafik.servisler,
            "grafik_katmani": grafik.katman(servis),
            # Bunlar bozulursa bu alarmin servisi etkilenir -> kok neden adayi
            "bagimli_oldugu_servisler": yukari,
            "bagimli_oldugu_sayisi": len(yukari),
            # Bu servis bozulursa bunlar etkilenir -> turev alarm beklenen yerler
            "etkiledigi_servisler": asagi,
            "etkiledigi_sayisi": len(asagi),
            "yayilim_alani": yayilim,
            "yayilim_alani_sayisi": len(yayilim),
            "kok_neden_adaylari": kok_adaylari,
            "kok_neden_adaylari_sayisi": len(kok_adaylari),
            "en_yuksek_bagimlilik_kritikligi": (
                max((k["kritiklik"] for k in yukari), key=lambda x: KRITIKLIK_PUAN.get(x, 0))
                if yukari else None
            ),
            "senkron_bagimlilik_sayisi": sum(1 for k in yukari if k["tip"] == "senkron"),
            "kok_neden_agirligi": kok_neden_agirligi(grafik, servis, is_krit),
        },
    }
    return zengin


# --------------------------------------------------------------------------- #
# Calistirma
# --------------------------------------------------------------------------- #

def kaynaklari_yukle() -> tuple[list[dict], dict[str, dict], BagimlilikGrafigi]:
    alarmlar = json.loads(ALARMS.read_text(encoding="utf-8"))
    envanter = envanter_yukle(HOSTS)
    grafik = BagimlilikGrafigi(bagimlilik_yukle(DEPS))
    return alarmlar, envanter, grafik


def ornek_sec(alarmlar: list[dict], grafik: BagimlilikGrafigi, alarm_id: str | None) -> dict:
    """Gosterim icin alarm sec.

    Belirtilmemisse hem yukari hem asagi bagimliligi olan bir servisten ornek
    secilir; boylece zenginlestirmenin her alani dolu gorunur.
    """
    if alarm_id:
        for a in alarmlar:
            if a["alarm_id"] == alarm_id:
                return a
        sys.exit(f"HATA: {alarm_id} bulunamadi.")
    for a in alarmlar:
        s = a["service"]
        if grafik.yukari.get(s) and grafik.asagi.get(s):
            return a
    return alarmlar[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Alarm verisini zenginlestir.")
    ap.add_argument(
        "--ornek", nargs="?", const="__ILK__", default=None, metavar="ALARM_ID",
        help="Tek alarm isle ve ekrana yaz; dosyaya yazma.",
    )
    args = ap.parse_args()

    alarmlar, envanter, grafik = kaynaklari_yukle()
    print(
        f"Yuklendi: {len(alarmlar)} alarm · {len(envanter)} host · "
        f"{len(grafik.kenarlar)} bagimlilik · {len(grafik.servisler)} servis grafikte",
        file=sys.stderr,
    )

    if args.ornek:
        alarm_id = None if args.ornek == "__ILK__" else args.ornek
        secilen = ornek_sec(alarmlar, grafik, alarm_id)
        print("\n--- ONCE (ham alarm) ---")
        print(json.dumps(secilen, ensure_ascii=False, indent=2))
        print("\n--- SONRA (zenginlestirilmis) ---")
        print(json.dumps(alarmi_zenginlestir(secilen, envanter, grafik),
                         ensure_ascii=False, indent=2))
        print("\nOrnek moddasiniz; dosyaya yazilmadi.", file=sys.stderr)
        return

    zenginler = [alarmi_zenginlestir(a, envanter, grafik) for a in alarmlar]

    eslesmeyen = [z["alarm_id"] for z in zenginler if not z["enrichment"]["host_bilgisi"]["eslesti"]]
    uyumsuz = [z["alarm_id"] for z in zenginler
               if z["enrichment"]["host_bilgisi"]["servis_uyumlu"] is False]
    grafik_disi = sorted({z["service"] for z in zenginler
                          if not z["enrichment"]["bagimlilik"]["grafikte_var"]})

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(zenginler, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nYazildi: {CIKTI.relative_to(KOK)}  ({len(zenginler)} kayit)")
    print(f"  envanterde eslesmeyen host : {len(eslesmeyen)}")
    print(f"  servis uyusmazligi         : {len(uyumsuz)}")
    print(f"  bagimlilik grafiginde olmayan servis: {len(grafik_disi)} {grafik_disi}")


if __name__ == "__main__":
    main()
