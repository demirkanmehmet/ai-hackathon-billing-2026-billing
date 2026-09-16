"""Alarm verisi duplike taramasi, kalite denetimi ve tekrar gruplama.

Boru hattinda ILK adimdir: alarms.json -> data/alarms_clean.json -> zenginlestirme.

Kullanim:
    python src/clean_alarms.py --rapor      # sadece tara ve raporla, dosya yazma
    python src/clean_alarms.py              # tara, temizle, data/alarms_clean.json yaz
    python src/clean_alarms.py --aralik 180 # tekrar zinciri bosluk esigini degistir

--------------------------------------------------------------------------------
TASARIM KARARI — neden tekrarlar SILINMIYOR
--------------------------------------------------------------------------------
Veride klasik anlamda duplike yok: alarm_id benzersiz, iki kayit tum alanlariyla
ayni degil. Buna karsilik ayni (host, alarm_type) cifti defalarca alarm uretiyor
(300 sn penceresinde kayitlarin ~%40'i). Bunlar duplike DEGIL, tekrar bildirimidir:

    ao-028-order / timeout, 26 kayit:
      01:45-01:53  hedef = subscriber-service   -> ag olayi
      02:14-02:21  hedef = billing-service      -> billing-db olayi
      02:42        hedef = payment-provider-gw  -> dis servis olayi

Bu kayitlari "ayni host + ayni tip" diye teke indirmek UC AYRI OLAYIN kanitini
silmek olur. Bu yuzden:

  1. Tekrar zinciri anahtarina HEDEF SERVIS de dahil edilir (mesajdan cikarilir).
  2. Zincir, iki kayit arasindaki bosluk esigi astiginda kirilir.
  3. Hicbir kayit silinmez; her kayda `tekrar` blogu yazilir ve zincirin ilk
     kaydi temsilci isaretlenir. Kart uretiminde temsilci gosterilir, sayac
     `grup_boyutu`ndan okunur. Boylece hem ekran sadelesir hem sayim korunur.

Gercek duplike (tum alanlari ayni kayit) bulunursa kaldirilir ve kaldirilanlar
raporda listelenir. Mevcut veri setinde bu sayi sifirdir.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
PAKET = KOK / "katilimci_paketi"
ALARMS = PAKET / "alarms.json"
HOSTS = PAKET / "host_inventory.csv"
CIKTI = KOK / "data" / "alarms_clean.json"
RAPOR = KOK / "data" / "temizlik_raporu.json"

ZORUNLU_ALANLAR = {
    "alarm_id", "timestamp", "source_system", "host",
    "service", "severity", "alarm_type", "message", "tags",
}
ZORUNLU_TAGS = {"veri_merkezi", "kabin", "ortam"}
GECERLI_KAYNAKLAR = {"OBM", "Prometheus", "Zabbix", "AppDynamics", "SyslogNG"}
GECERLI_TIPLER = {
    "network_down", "network_flap", "pkt_loss", "timeout", "conn_refused", "http_5xx",
    "latency_high", "disk_full", "disk_warn", "db_write_fail", "db_conn_pool", "mem_high",
    "gc_pressure", "oom_risk", "ext_unreach", "ext_slow", "txn_fail", "queue_backlog",
    "batch_overlap", "batch_slow", "cpu_high", "cert_expiry", "backup_warn", "ntp_drift",
    "log_rotate", "thread_pool",
}
PENCERE_BAS = datetime(2026, 9, 10, 1, 30)
PENCERE_SON = datetime(2026, 9, 10, 3, 31)

# Mesajdan hedef servis cikarimi. Iliskisel alarmlarda hangi servise yapilan
# cagrinin bozuldugu mesajda gecer; tekrar zincirini dogru bolmek icin sart.
HEDEF_KALIPLARI = (
    re.compile(r"^([a-z0-9-]+) servisine"),
    re.compile(r"^([a-z0-9-]+) baglantisi"),
    re.compile(r"^Dis servis ([a-z0-9-]+)"),
)
ILISKISEL_TIPLER = {"timeout", "conn_refused", "ext_unreach", "ext_slow"}

VARSAYILAN_ARALIK_SN = 300


def hedef_servis(alarm: dict[str, Any]) -> str | None:
    if alarm["alarm_type"] not in ILISKISEL_TIPLER:
        return None
    for kalip in HEDEF_KALIPLARI:
        m = kalip.match(alarm["message"])
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------- #
# 1. Duplike taramasi
# --------------------------------------------------------------------------- #

def _icerik_imzasi(a: dict[str, Any]) -> str:
    """alarm_id disindaki tum alanlarin kararli imzasi."""
    return json.dumps({k: v for k, v in a.items() if k != "alarm_id"},
                      sort_keys=True, ensure_ascii=False)


def duplike_tara(alarmlar: list[dict]) -> dict[str, Any]:
    id_sayim = Counter(a["alarm_id"] for a in alarmlar)
    tekrar_id = {k: v for k, v in id_sayim.items() if v > 1}

    imza_gruplari: dict[str, list[str]] = defaultdict(list)
    for a in alarmlar:
        imza_gruplari[_icerik_imzasi(a)].append(a["alarm_id"])
    tam_duplike = {i: ids for i, ids in imza_gruplari.items() if len(ids) > 1}

    # Ayni saniye + host + tip: duplike DEGIL, cok kaynakli gozlem olabilir.
    # Farkli source_system varsa ayri olcumdur; ayni ise supheli.
    anahtar: dict[tuple, list[dict]] = defaultdict(list)
    for a in alarmlar:
        anahtar[(a["timestamp"], a["host"], a["alarm_type"])].append(a)
    cakisan = {k: v for k, v in anahtar.items() if len(v) > 1}
    cok_kaynakli = sum(1 for v in cakisan.values()
                       if len({x["source_system"] for x in v}) == len(v))

    return {
        "tekrarlanan_alarm_id": {"sayi": len(tekrar_id), "ornekler": list(tekrar_id)[:10]},
        "tam_kayit_duplikesi": {
            "grup_sayisi": len(tam_duplike),
            "fazla_kayit": sum(len(v) - 1 for v in tam_duplike.values()),
            "kaldirilacak_idler": [i for ids in tam_duplike.values() for i in ids[1:]],
        },
        "ayni_sn_host_tip": {
            "anahtar_sayisi": len(cakisan),
            "cok_kaynakli_olan": cok_kaynakli,
            "gercek_supheli": len(cakisan) - cok_kaynakli,
            "ornekler": [
                {"zaman": k[0], "host": k[1], "tip": k[2],
                 "kaynaklar": [x["source_system"] for x in v],
                 "mesajlar": [x["message"] for x in v]}
                for k, v in list(cakisan.items())[:5]
            ],
        },
    }


# --------------------------------------------------------------------------- #
# 2. Kalite denetimi
# --------------------------------------------------------------------------- #

def envanter_yukle(yol: Path) -> dict[str, dict[str, str]]:
    with yol.open(encoding="utf-8-sig", newline="") as f:
        return {r["host"]: r for r in csv.DictReader(f)}


def kalite_tara(alarmlar: list[dict], envanter: dict[str, dict]) -> dict[str, Any]:
    bulgu: Counter = Counter()
    ornek: dict[str, list[str]] = defaultdict(list)

    def isaretle(kod: str, aid: str) -> None:
        bulgu[kod] += 1
        if len(ornek[kod]) < 5:
            ornek[kod].append(aid)

    for a in alarmlar:
        aid = a.get("alarm_id", "?")
        eksik = ZORUNLU_ALANLAR - set(a)
        if eksik:
            isaretle(f"eksik_alan:{','.join(sorted(eksik))}", aid)
        for alan in ZORUNLU_ALANLAR & set(a):
            if a[alan] is None or a[alan] == "":
                isaretle(f"bos_alan:{alan}", aid)
        if not re.fullmatch(r"ALM-\d{5}", str(a.get("alarm_id", ""))):
            isaretle("alarm_id_formati", aid)
        try:
            t = datetime.fromisoformat(a["timestamp"])
            if not PENCERE_BAS <= t <= PENCERE_SON:
                isaretle("pencere_disi_zaman", aid)
        except (KeyError, ValueError):
            isaretle("gecersiz_timestamp", aid)
        sev = a.get("severity")
        if not isinstance(sev, int) or not 1 <= sev <= 5:
            isaretle("severity_aralik_disi", aid)
        if a.get("alarm_type") not in GECERLI_TIPLER:
            isaretle("bilinmeyen_alarm_tipi", aid)
        if a.get("source_system") not in GECERLI_KAYNAKLAR:
            isaretle("bilinmeyen_kaynak_sistem", aid)
        etiket = a.get("tags") or {}
        if set(etiket) != ZORUNLU_TAGS:
            isaretle("tags_anahtar_farkli", aid)
        env = envanter.get(a.get("host", ""))
        if not env:
            isaretle("envanterde_olmayan_host", aid)
        else:
            if env["servis"] != a.get("service"):
                isaretle("servis_uyusmazligi", aid)
            if env["veri_merkezi"] != etiket.get("veri_merkezi"):
                isaretle("dc_uyusmazligi", aid)
            if env["kabin"] != etiket.get("kabin"):
                isaretle("kabin_uyusmazligi", aid)

    return {"toplam_bulgu": sum(bulgu.values()),
            "bulgular": dict(bulgu),
            "ornekler": {k: v for k, v in ornek.items()}}


# --------------------------------------------------------------------------- #
# 3. Temizlik ve tekrar gruplama
# --------------------------------------------------------------------------- #

def tam_duplikeleri_kaldir(alarmlar: list[dict]) -> tuple[list[dict], list[str]]:
    """Tum alanlari ayni olan kayitlarin ilkini tutar, digerlerini dusurur."""
    gorulen: set[str] = set()
    tutulan: list[dict] = []
    dusurulen: list[str] = []
    for a in alarmlar:
        imza = _icerik_imzasi(a)
        if imza in gorulen:
            dusurulen.append(a["alarm_id"])
        else:
            gorulen.add(imza)
            tutulan.append(a)
    return tutulan, dusurulen


def tekrar_gruplarini_isaretle(alarmlar: list[dict], aralik_sn: int) -> list[dict]:
    """Her alarma `tekrar` blogu ekler. Hicbir kayit silinmez.

    Zincir anahtari: (host, service, alarm_type, hedef_servis).
    Hedef servis mesajdan cikarilir; boylece ayni host+tip farkli hedeflere
    alarm uretiyorsa ayri zincirlere bolunur. Iki ardisik kayit arasindaki
    bosluk `aralik_sn`yi asarsa zincir kirilir.
    """
    zincirler: dict[tuple, list[dict]] = defaultdict(list)
    for a in alarmlar:
        zincirler[(a["host"], a["service"], a["alarm_type"], hedef_servis(a))].append(a)

    sonuc: dict[str, dict] = {}
    sayac = 0
    for anahtar, grup in zincirler.items():
        grup.sort(key=lambda x: x["timestamp"])
        parca: list[dict] = []
        parcalar: list[list[dict]] = []
        onceki: datetime | None = None
        for a in grup:
            t = datetime.fromisoformat(a["timestamp"])
            if onceki is not None and (t - onceki).total_seconds() > aralik_sn:
                parcalar.append(parca)
                parca = []
            parca.append(a)
            onceki = t
        parcalar.append(parca)

        for p in parcalar:
            sayac += 1
            gid = f"RPT-{sayac:05d}"
            ilk = datetime.fromisoformat(p[0]["timestamp"])
            son = datetime.fromisoformat(p[-1]["timestamp"])
            for i, a in enumerate(p):
                sonuc[a["alarm_id"]] = {
                    "grup_id": gid,
                    "grup_anahtari": "|".join(str(x) for x in anahtar),
                    "grup_boyutu": len(p),
                    "sira": i + 1,
                    "temsilci_mi": i == 0,
                    "grup_ilk_zaman": p[0]["timestamp"],
                    "grup_son_zaman": p[-1]["timestamp"],
                    "grup_suresi_sn": int((son - ilk).total_seconds()),
                    "hedef_servis": anahtar[3],
                }

    return [{**a, "tekrar": sonuc[a["alarm_id"]]} for a in alarmlar]


# --------------------------------------------------------------------------- #
# Calistirma
# --------------------------------------------------------------------------- #

def yazdir_rapor(dup: dict, kal: dict) -> None:
    print("=" * 72)
    print("1) DUPLIKE TARAMASI")
    print("=" * 72)
    t = dup["tekrarlanan_alarm_id"]
    print(f"  Tekrarlanan alarm_id      : {t['sayi']}")
    f = dup["tam_kayit_duplikesi"]
    print(f"  Tam kayit duplikesi       : {f['grup_sayisi']} grup / {f['fazla_kayit']} fazla kayit")
    c = dup["ayni_sn_host_tip"]
    print(f"  Ayni sn + host + tip      : {c['anahtar_sayisi']} anahtar")
    print(f"    cok kaynakli (duplike degil): {c['cok_kaynakli_olan']}")
    print(f"    gercekten supheli           : {c['gercek_supheli']}")
    for o in c["ornekler"]:
        print(f"      {o['zaman'][11:]} {o['host']} {o['tip']} kaynak={o['kaynaklar']}")
        for m in o["mesajlar"]:
            print(f"        - {m}")

    print("\n" + "=" * 72)
    print("2) KALITE DENETIMI")
    print("=" * 72)
    if kal["toplam_bulgu"] == 0:
        print("  Bulgu yok. Zorunlu alanlar, deger araliklari, envanter tutarliligi temiz.")
    else:
        for k, v in sorted(kal["bulgular"].items(), key=lambda x: -x[1]):
            print(f"  {k:32s} {v:5d}   ornek: {kal['ornekler'][k]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Alarm verisi duplike/kalite taramasi ve temizligi.")
    ap.add_argument("--rapor", action="store_true", help="Sadece tara ve raporla; dosya yazma.")
    ap.add_argument("--aralik", type=int, default=VARSAYILAN_ARALIK_SN,
                    help=f"Tekrar zinciri bosluk esigi (sn). Varsayilan {VARSAYILAN_ARALIK_SN}.")
    args = ap.parse_args()

    alarmlar = json.loads(ALARMS.read_text(encoding="utf-8"))
    envanter = envanter_yukle(HOSTS)
    print(f"Yuklendi: {len(alarmlar)} alarm · {len(envanter)} host\n")

    dup = duplike_tara(alarmlar)
    kal = kalite_tara(alarmlar, envanter)
    yazdir_rapor(dup, kal)

    if args.rapor:
        print("\nRapor modu; dosya yazilmadi.", file=sys.stderr)
        return

    print("\n" + "=" * 72)
    print("3) TEMIZLIK")
    print("=" * 72)

    temiz, dusurulen = tam_duplikeleri_kaldir(alarmlar)
    print(f"  Kaldirilan tam duplike    : {len(dusurulen)} {dusurulen[:10]}")

    temiz.sort(key=lambda a: (a["timestamp"], a["alarm_id"]))
    print(f"  Siralama                  : (timestamp, alarm_id) artan")

    temiz = tekrar_gruplarini_isaretle(temiz, args.aralik)

    gruplar = {a["tekrar"]["grup_id"] for a in temiz}
    temsilci = sum(1 for a in temiz if a["tekrar"]["temsilci_mi"])
    zincirli = sum(1 for a in temiz if a["tekrar"]["grup_boyutu"] > 1)
    en_uzun = max(temiz, key=lambda a: a["tekrar"]["grup_boyutu"])["tekrar"]

    print(f"  Tekrar zinciri (esik {args.aralik}sn): {len(gruplar)} grup")
    print(f"    temsilci kayit          : {temsilci}")
    print(f"    zincire dahil kayit     : {zincirli} ({zincirli/len(temiz)*100:.1f}%)")
    print(f"    en uzun zincir          : {en_uzun['grup_boyutu']}x  {en_uzun['grup_anahtari']}"
          f"  ({en_uzun['grup_ilk_zaman'][11:16]}-{en_uzun['grup_son_zaman'][11:16]})")
    print(f"  SILINEN KAYIT             : {len(alarmlar) - len(temiz)}")

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(temiz, ensure_ascii=False, indent=2), encoding="utf-8")
    RAPOR.write_text(json.dumps(
        {"girdi_kayit": len(alarmlar), "cikti_kayit": len(temiz),
         "kaldirilan_idler": dusurulen, "tekrar_esigi_sn": args.aralik,
         "tekrar_grup_sayisi": len(gruplar), "temsilci_sayisi": temsilci,
         "duplike": dup, "kalite": kal},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nYazildi: {CIKTI.relative_to(KOK)}  ({len(temiz)} kayit)")
    print(f"Yazildi: {RAPOR.relative_to(KOK)}")


if __name__ == "__main__":
    main()
