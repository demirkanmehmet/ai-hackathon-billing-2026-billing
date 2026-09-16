"""alarms_clean.json dosyasina `kaynak_servis` alani ekler.

Amac: alarmi service_dependencies.csv ile eslestirilebilir hale getirmek.

Bagimlilik CSV'sinin semasi (kaynak_servis, hedef_servis) ciftidir ve okuma yonu
"kaynak_servis, hedef_servis'e bagimlidir"dir. Alarm kaydinda hedef taraf zaten
`tekrar.hedef_servis` alaninda duruyor (iliskisel alarmlarin mesajindan
cikarilmisti). Eksik olan kaynak taraf: alarmin dustugu servisin kendisi.

    kaynak_servis = alarm["service"]

Bu alan eklendiginde (kaynak_servis, tekrar.hedef_servis) cifti dogrudan
service_dependencies.csv satirina join edilebilir hale gelir.

Alani `service`den ayri bir isimle yazmanin sebebi anlamsal: `service` alarmin
sahibi, `kaynak_servis` bagimlilik kenarinin kaynak ucu. Ayni degeri tasirlar
ama farkli seyi ifade ederler ve join kodu hangi rolde kullanildigini belli eder.

Dosya YERINDE guncellenir. Script idempotenttir; tekrar calistirmak zarar vermez.

Kullanim:
    python src/add_kaynak_servis.py --rapor   # sadece eslestirme analizini yaz
    python src/add_kaynak_servis.py           # alani ekle ve dosyayi guncelle
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HEDEF_DOSYA = KOK / "data" / "alarms_clean.json"
DEPS = KOK / "katilimci_paketi" / "service_dependencies.csv"


def kenarlari_yukle(yol: Path) -> tuple[set[tuple[str, str]], dict, dict[str, list[str]]]:
    """Dogrudan kenar kumesi, kenar meta bilgisi ve komsuluk listesi dondurur."""
    kenarlar: set[tuple[str, str]] = set()
    meta: dict[tuple[str, str], dict[str, str]] = {}
    komsu: dict[str, list[str]] = defaultdict(list)
    with yol.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cift = (r["kaynak_servis"], r["hedef_servis"])
            kenarlar.add(cift)
            meta[cift] = r
            komsu[r["kaynak_servis"]].append(r["hedef_servis"])
    return kenarlar, meta, komsu


def ulasilabilir(komsu: dict[str, list[str]], bas: str) -> set[str]:
    """bas servisinden bagimlilik yonunde ulasilabilen tum servisler."""
    gorulen: set[str] = set()
    kuyruk = deque(komsu.get(bas, []))
    while kuyruk:
        s = kuyruk.popleft()
        if s in gorulen:
            continue
        gorulen.add(s)
        kuyruk.extend(komsu.get(s, []))
    return gorulen


def eslestirme_sinifi(
    kaynak: str, hedef: str | None,
    kenarlar: set[tuple[str, str]], komsu: dict[str, list[str]],
) -> str:
    """Alarmin bagimlilik grafigiyle nasil eslestigini siniflandirir.

    iliskisel_degil : alarmda hedef servis yok (disk_full, mem_high gibi)
    kendine         : kaynak == hedef; dis servis kendi durumunu bildiriyor
    dogrudan        : CSV'de birebir kenar var
    gecisli         : dogrudan kenar yok ama bagimlilik yonunde yol var
    yol_yok         : grafikte hicbir yol yok
    """
    if hedef is None:
        return "iliskisel_degil"
    if kaynak == hedef:
        return "kendine"
    if (kaynak, hedef) in kenarlar:
        return "dogrudan"
    if hedef in ulasilabilir(komsu, kaynak):
        return "gecisli"
    return "yol_yok"


def main() -> None:
    ap = argparse.ArgumentParser(description="alarms_clean.json'a kaynak_servis ekler.")
    ap.add_argument("--rapor", action="store_true", help="Sadece analiz yaz; dosyayi degistirme.")
    args = ap.parse_args()

    if not HEDEF_DOSYA.exists():
        sys.exit(f"HATA: {HEDEF_DOSYA} yok. Once: python src/clean_alarms.py")

    alarmlar = json.loads(HEDEF_DOSYA.read_text(encoding="utf-8"))
    kenarlar, meta, komsu = kenarlari_yukle(DEPS)
    print(f"Yuklendi: {len(alarmlar)} alarm · {len(kenarlar)} bagimlilik kenari\n")

    zaten_var = sum(1 for a in alarmlar if "kaynak_servis" in a)
    if zaten_var:
        print(f"Not: {zaten_var} kayitta `kaynak_servis` zaten var, uzerine yazilacak.\n")

    siniflar: Counter = Counter()
    cift_sayim: Counter = Counter()
    for a in alarmlar:
        kaynak = a["service"]
        hedef = a["tekrar"]["hedef_servis"]
        sinif = eslestirme_sinifi(kaynak, hedef, kenarlar, komsu)
        siniflar[sinif] += 1
        if hedef:
            cift_sayim[(kaynak, hedef, sinif)] += 1

    toplam = len(alarmlar)
    iliskisel = toplam - siniflar["iliskisel_degil"]

    print("=" * 72)
    print("BAGIMLILIK ESLESTIRME ANALIZI")
    print("=" * 72)
    print(f"  Toplam alarm                    : {toplam}")
    print(f"  Iliskisel (hedef_servis dolu)   : {iliskisel}")
    for sinif in ("dogrudan", "gecisli", "kendine", "yol_yok"):
        n = siniflar[sinif]
        oran = f"%{n / iliskisel * 100:.1f}" if iliskisel else "-"
        print(f"    {sinif:18s} {n:5d}  {oran}")
    print(f"  Iliskisel degil                 : {siniflar['iliskisel_degil']}")

    for baslik, sinif in (("GECISLI ESLESEN CIFTLER", "gecisli"),
                          ("YOL BULUNAMAYAN CIFTLER", "yol_yok")):
        satirlar = [(k, v) for k, v in cift_sayim.items() if k[2] == sinif]
        if not satirlar:
            continue
        print(f"\n  {baslik} ({len(satirlar)} farkli cift)")
        for (kay, hed, _), v in sorted(satirlar, key=lambda x: -x[1])[:10]:
            print(f"    {v:4d}x  {kay:22s} -> {hed}")

    if args.rapor:
        print("\nRapor modu; dosya degistirilmedi.", file=sys.stderr)
        return

    # Tek degisiklik: kaynak_servis alanini ekle. Baska hicbir alana dokunulmaz.
    for a in alarmlar:
        a["kaynak_servis"] = a["service"]

    HEDEF_DOSYA.write_text(json.dumps(alarmlar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuncellendi: {HEDEF_DOSYA.relative_to(KOK)}")
    print(f"  `kaynak_servis` eklenen kayit : {len(alarmlar)}")
    print(f"  Join anahtari                 : (kaynak_servis, tekrar.hedef_servis)")


if __name__ == "__main__":
    main()
