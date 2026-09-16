"""Temizlenmis alarmlari verilen etiket kumesine gore gruplar.

Girdi : data/alarms_clean.json   (clean_alarms.py ciktisi, `tekrar` blogu iceren)
Cikti : data/alarms_grouped.json

Kullanim:
    python src/group_alarms.py --test            # ornek gruplar + istatistik, dosya yazma
    python src/group_alarms.py                   # tumunu grupla ve yaz
    python src/group_alarms.py --anahtar host,service,alarm_type,grup_id

Varsayilan anahtar (istenen sira):
    source_system, host, service, alarm_type, veri_merkezi, kabin, ortam,
    grup_anahtari, grup_id

--------------------------------------------------------------------------------
ANAHTAR SECIMI HAKKINDA
--------------------------------------------------------------------------------
Bu dokuz alanin bir kismi birbirini zaten belirler:

  host           -> veri_merkezi, kabin, ortam, service   (envanterden tek deger)
  grup_id        -> host, service, alarm_type, hedef_servis (zincir anahtari)
  grup_anahtari  -> grup_id'nin tasidigi bilginin metin hali

Yani kardinaliteyi fiilen belirleyen iki alan kalir: `grup_id` ve `source_system`.
`source_system` anahtara dahil edildiginde, birden fazla izleme sisteminden
beslenen tekrar zincirleri parcalanir. Ornegin ayni timeout zinciri Prometheus,
Zabbix ve OBM tarafindan raporlandiysa tek grup yerine uc grup olusur.

Bu istenen davranis olabilir (kaynak sistem bazli denetim, izleme sistemi
karsilastirmasi) ya da istenmeyen olabilir (olay kartinda tek satir gormek).
--test modu her iki kardinaliteyi de raporlar; karar kullaniciya birakilir.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
GIRDI = KOK / "data" / "alarms_clean.json"
CIKTI = KOK / "data" / "alarms_grouped.json"

# `source_system` bilincli olarak anahtarda DEGIL. Gerekcesi:
# Ayni tekrar zinciri birden fazla izleme sisteminden raporlanabiliyor
# (or. RPT-01774: AppDynamics 4 + Zabbix 4 + OBM 3 + Prometheus 2 = tek olay).
# Anahtara dahil edilseydi bu tek olgu dort satira bolunur, indirgeme
# %37.8'den %15.4'e duserdi. Bilgi kaybi yok: hangi sistemlerin rapor ettigi
# her grup kaydinda `kaynak_sistemler` alaninda listeleniyor.
# Kaynak sistem bazli denetim gerekirse:
#     python src/group_alarms.py --anahtar source_system,host,...,grup_id
VARSAYILAN_ANAHTAR = [
    "host", "service", "alarm_type",
    "veri_merkezi", "kabin", "ortam", "grup_anahtari", "grup_id",
]

# Alan adi -> alarm kaydindan degeri cikaran fonksiyon.
# tags ve tekrar bloklari duzlestirilerek anahtar olarak kullanilabilir hale gelir.
ALAN_ERISIM = {
    "alarm_id": lambda a: a["alarm_id"],
    "timestamp": lambda a: a["timestamp"],
    "source_system": lambda a: a["source_system"],
    "host": lambda a: a["host"],
    "service": lambda a: a["service"],
    "severity": lambda a: a["severity"],
    "alarm_type": lambda a: a["alarm_type"],
    "veri_merkezi": lambda a: a["tags"]["veri_merkezi"],
    "kabin": lambda a: a["tags"]["kabin"],
    "ortam": lambda a: a["tags"]["ortam"],
    "grup_anahtari": lambda a: a["tekrar"]["grup_anahtari"],
    "grup_id": lambda a: a["tekrar"]["grup_id"],
    "hedef_servis": lambda a: a["tekrar"]["hedef_servis"],
}


def anahtar_degeri(alarm: dict[str, Any], alanlar: list[str]) -> tuple:
    return tuple(ALAN_ERISIM[f](alarm) for f in alanlar)


def grupla(alarmlar: list[dict], alanlar: list[str]) -> list[dict]:
    """Alarmlari anahtara gore gruplar ve her grup icin ozet kayit uretir."""
    kovalar: dict[tuple, list[dict]] = defaultdict(list)
    for a in alarmlar:
        kovalar[anahtar_degeri(a, alanlar)].append(a)

    gruplar: list[dict] = []
    for sira, (anahtar, uyeler) in enumerate(
        sorted(kovalar.items(), key=lambda kv: kv[1][0]["timestamp"]), start=1
    ):
        uyeler.sort(key=lambda a: a["timestamp"])
        ilk = datetime.fromisoformat(uyeler[0]["timestamp"])
        son = datetime.fromisoformat(uyeler[-1]["timestamp"])
        sevler = [a["severity"] for a in uyeler]
        mesajlar = Counter(a["message"] for a in uyeler)

        gruplar.append({
            "grup_no": f"GRP-{sira:05d}",
            "anahtar": dict(zip(alanlar, anahtar)),
            "alarm_sayisi": len(uyeler),
            "ilk_zaman": uyeler[0]["timestamp"],
            "son_zaman": uyeler[-1]["timestamp"],
            "sure_sn": int((son - ilk).total_seconds()),
            "severity": {
                "min": min(sevler), "max": max(sevler),
                "ortalama": round(sum(sevler) / len(sevler), 2),
            },
            "kaynak_sistemler": sorted({a["source_system"] for a in uyeler}),
            "farkli_mesaj_sayisi": len(mesajlar),
            "ornek_mesaj": uyeler[0]["message"],
            "alarm_idler": [a["alarm_id"] for a in uyeler],
        })
    return gruplar


def kardinalite_karsilastir(alarmlar: list[dict], alanlar: list[str]) -> None:
    """Anahtardan tek tek alan cikarildiginda grup sayisinin nasil degistigini gosterir.

    Amac: hangi alanin gercekten bolme yaptigini gormek. Grup sayisini
    degistirmeyen alan, anahtarda gereksiz yer kapliyor demektir.
    """
    tam = len({anahtar_degeri(a, alanlar) for a in alarmlar})
    print(f"  Tam anahtar ({len(alanlar)} alan)          -> {tam:5d} grup")
    for cikarilan in alanlar:
        kalan = [f for f in alanlar if f != cikarilan]
        n = len({anahtar_degeri(a, kalan) for a in alarmlar})
        fark = tam - n
        not_ = "  <- BOLUCU" if fark else "  (etkisiz, digerleri belirliyor)"
        print(f"    '{cikarilan}' cikarilirsa           -> {n:5d} grup  (fark {fark:+d}){not_}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Alarmlari etiketlere gore gruplar.")
    ap.add_argument("--test", action="store_true",
                    help="Ornek gruplari ve istatistikleri yaz; dosyaya yazma.")
    ap.add_argument("--anahtar", default=",".join(VARSAYILAN_ANAHTAR),
                    help="Virgulle ayrilmis gruplama alanlari.")
    ap.add_argument("--ornek-sayisi", type=int, default=5, help="Test modunda gosterilecek grup.")
    args = ap.parse_args()

    if not GIRDI.exists():
        sys.exit(f"HATA: {GIRDI} yok. Once: python src/clean_alarms.py")

    alanlar = [f.strip() for f in args.anahtar.split(",") if f.strip()]
    bilinmeyen = [f for f in alanlar if f not in ALAN_ERISIM]
    if bilinmeyen:
        sys.exit(f"HATA: bilinmeyen alan {bilinmeyen}. Gecerli: {sorted(ALAN_ERISIM)}")

    alarmlar = json.loads(GIRDI.read_text(encoding="utf-8"))
    print(f"Yuklendi: {len(alarmlar)} alarm")
    print(f"Anahtar : {' + '.join(alanlar)}\n")

    gruplar = grupla(alarmlar, alanlar)
    boyutlar = Counter(g["alarm_sayisi"] for g in gruplar)
    kapsanan = sum(g["alarm_sayisi"] for g in gruplar)

    print("=" * 72)
    print("GRUPLAMA SONUCU")
    print("=" * 72)
    print(f"  Grup sayisi          : {len(gruplar)}")
    print(f"  Kapsanan alarm       : {kapsanan} / {len(alarmlar)}"
          f"  {'OK' if kapsanan == len(alarmlar) else 'EKSIK'}")
    print(f"  Indirgeme            : {len(alarmlar)} -> {len(gruplar)}"
          f"  (%{(1 - len(gruplar) / len(alarmlar)) * 100:.1f})")
    print(f"  Tek uyeli grup       : {boyutlar[1]} (%{boyutlar[1] / len(gruplar) * 100:.1f})")
    print(f"  En buyuk grup        : {max(g['alarm_sayisi'] for g in gruplar)} alarm")
    print(f"  Ortalama grup boyutu : {kapsanan / len(gruplar):.2f}")

    if args.test:
        print("\n" + "=" * 72)
        print("HANGI ALAN GERCEKTEN BOLUYOR")
        print("=" * 72)
        kardinalite_karsilastir(alarmlar, alanlar)

        print("\n" + "=" * 72)
        print(f"EN BUYUK {args.ornek_sayisi} GRUP")
        print("=" * 72)
        for g in sorted(gruplar, key=lambda x: -x["alarm_sayisi"])[:args.ornek_sayisi]:
            a = g["anahtar"]
            print(f"\n  {g['grup_no']}  x{g['alarm_sayisi']}  "
                  f"{g['ilk_zaman'][11:19]} - {g['son_zaman'][11:19]}  ({g['sure_sn']}sn)")
            print(f"    {a.get('service')} / {a.get('alarm_type')} @ {a.get('host')} "
                  f"[{a.get('veri_merkezi')}/{a.get('kabin')}]")
            print(f"    kaynak={a.get('source_system')}  grup_id={a.get('grup_id')}")
            print(f"    severity min/max/ort = {g['severity']['min']}/{g['severity']['max']}"
                  f"/{g['severity']['ortalama']}   farkli mesaj: {g['farkli_mesaj_sayisi']}")
            print(f"    ornek: {g['ornek_mesaj'][:64]}")

        print("\n" + "=" * 72)
        print("TAM GRUP KAYDI (JSON ornegi)")
        print("=" * 72)
        en_buyuk = max(gruplar, key=lambda x: x["alarm_sayisi"])
        gosterim = dict(en_buyuk)
        gosterim["alarm_idler"] = gosterim["alarm_idler"][:6] + ["..."]
        print(json.dumps(gosterim, ensure_ascii=False, indent=2))

        print("\nTest modu; dosya yazilmadi.", file=sys.stderr)
        return

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(
        {"anahtar_alanlari": alanlar, "girdi_alarm_sayisi": len(alarmlar),
         "grup_sayisi": len(gruplar), "gruplar": gruplar},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nYazildi: {CIKTI.relative_to(KOK)}  ({len(gruplar)} grup)")


if __name__ == "__main__":
    main()
