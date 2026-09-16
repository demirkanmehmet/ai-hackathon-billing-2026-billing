#!/usr/bin/env python3
"""S-A1 Alarm Firtinasi — tek giris noktasi.

Windows, macOS ve Linux'ta ayni sekilde calisir. Harici bagimlilik yoktur;
Python 3.9+ disinda hicbir sey kurulmasi gerekmez.

    python run.py              # arayuzu ac (varsayilan)
    python run.py gui          # arayuzu ac
    python run.py cli          # boru hattini terminalde kosur
    python run.py cli --detay  # kanit dokumu ile
    python run.py test         # kendi kendini dogrula
    python run.py --yardim

`cli` ve `gui` sonrasindaki tum argumanlar ilgili module oldugu gibi aktarilir:
    python run.py cli --girdi baska/alarms.json --paylasilan-kaynak
    python run.py gui --port 9000 --acma
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
SRC = KOK / "src"
ASGARI_PYTHON = (3, 9)

KULLANIM = """S-A1 Alarm Firtinasi

  python run.py [gui|cli|test] [ek argumanlar...]

  gui    Yerel web arayuzu (varsayilan). Tarayicida acilir.
         ornek: python run.py gui --port 9000 --acma
  cli    Boru hattini terminalde kosar, data/pipeline/*.json uretir.
         ornek: python run.py cli --detay --girdi yol/alarms.json
  test   Kurulum ve boru hatti dogrulamasi.

Bagimlilik yok; yalnizca Python {0}.{1}+ gerekir.""".format(*ASGARI_PYTHON)


def surum_kontrol() -> None:
    if sys.version_info < ASGARI_PYTHON:
        sys.exit(f"HATA: Python {ASGARI_PYTHON[0]}.{ASGARI_PYTHON[1]}+ gerekli, "
                 f"bulunan {sys.version.split()[0]}")


def modul_kosur(ad: str, argv: list[str]) -> int:
    """Alt sureç olarak kosar: modulun kendi argparse'i bozulmadan calisir."""
    yol = SRC / f"{ad}.py"
    if not yol.exists():
        sys.exit(f"HATA: {yol} bulunamadi.")
    return subprocess.call([sys.executable, str(yol), *argv], cwd=str(KOK))


def kendini_dogrula() -> int:
    print("S-A1 kurulum dogrulamasi\n" + "-" * 46)
    tamam = True

    print(f"  Python {sys.version.split()[0]}"
          + (" [OK]" if sys.version_info >= ASGARI_PYTHON else " [HATA]"))
    tamam &= sys.version_info >= ASGARI_PYTHON

    for p in (SRC / "pipeline.py", SRC / "gui.py",
              KOK / "katilimci_paketi" / "alarms.json",
              KOK / "katilimci_paketi" / "host_inventory.csv",
              KOK / "katilimci_paketi" / "service_dependencies.csv"):
        v = p.exists()
        tamam &= v
        print(f"  {p.relative_to(KOK)}{'':<{max(0, 40 - len(str(p.relative_to(KOK))))}}"
              f"{'[OK]' if v else '[EKSIK]'}")

    if not tamam:
        print("\nEksik dosya var; boru hatti kosulmadi.")
        return 1

    print("\n  Boru hatti kosuluyor...")
    sys.path.insert(0, str(SRC))
    import pipeline  # noqa: E402
    s = pipeline.calistir(KOK / "katilimci_paketi" / "alarms.json")
    o = s["ozet"]
    print(f"    {o['alarm_sayisi']} alarm -> {o['tekrar_zinciri']} zincir "
          f"-> {o['kart_sayisi']} kart  (indirgeme %{o['indirgeme_orani'] * 100:.2f})")

    kimlikler = [i for k in s["asama6_kartlar"] for i in k["uye_alarm_idleri"]]
    kontroller = [
        ("kart uretildi", len(s["asama6_kartlar"]) > 0),
        ("kart sayisi <= 15 (brifing siniri)", len(s["asama6_kartlar"]) <= 15),
        ("cift atama yok", len(kimlikler) == len(set(kimlikler))),
        ("tum alarmlar islendi", o["alarm_sayisi"] == o["ham_alarm"]),
        ("atanan + elenen = toplam",
         o["atanan_alarm"] + o["elenen_alarm"] == o["alarm_sayisi"]),
        ("her kartta kok neden gerekcesi var",
         all(k.get("gerekce") for k in s["asama6_kartlar"])),
        ("her kartta sahipli aksiyon var",
         all(k["aksiyon"].get("sahip") and k["aksiyon"].get("durum")
             for k in s["asama6_kartlar"])),
        ("her elenen alarmda gerekce kodu var",
         all(a.get("gerekce_kodu") for a in s["asama5_korele"]["elenen_alarmlar"])),
        ("LLM kullanilmadi", o["llm_kullanildi"] is False),
    ]
    print()
    for ad, ok in kontroller:
        print(f"  {'[OK]  ' if ok else '[HATA]'} {ad}")
        tamam &= ok

    # Determinizm: ayni girdi iki kez kosuldugunda ayni kartlar cikmali.
    s2 = pipeline.calistir(KOK / "katilimci_paketi" / "alarms.json")
    ayni = ([k["id"] for k in s["asama6_kartlar"]] == [k["id"] for k in s2["asama6_kartlar"]]
            and [k["uye_alarm_idleri"] for k in s["asama6_kartlar"]]
            == [k["uye_alarm_idleri"] for k in s2["asama6_kartlar"]])
    print(f"  {'[OK]  ' if ayni else '[HATA]'} determinizm (iki kosu ayni sonuc)")
    tamam &= ayni

    print("\n" + ("TUM KONTROLLER GECTI" if tamam else "BAZI KONTROLLER BASARISIZ"))
    return 0 if tamam else 1


def main() -> int:
    surum_kontrol()
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "--yardim", "yardim"):
        print(KULLANIM)
        return 0

    komut = argv[0] if argv and argv[0] in ("gui", "cli", "test") else "gui"
    kalan = argv[1:] if argv and argv[0] in ("gui", "cli", "test") else argv

    if komut == "test":
        return kendini_dogrula()
    if komut == "cli":
        return modul_kosur("pipeline", kalan)
    return modul_kosur("gui", kalan)


if __name__ == "__main__":
    sys.exit(main())
