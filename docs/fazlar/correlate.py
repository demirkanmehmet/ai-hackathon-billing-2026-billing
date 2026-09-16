"""Alarm korelasyonu ve kok neden karti uretimi.

Girdi : data/alarms_clean.json  (clean_alarms.py + add_kaynak_servis.py ciktisi)
Cikti : data/olay_kartlari.json

Kullanim:
    python src/correlate.py            # kartlari uret ve yaz
    python src/correlate.py --detay    # her kart icin kanit dokumunu da yaz

--------------------------------------------------------------------------------
ALGORITMA
--------------------------------------------------------------------------------
1. SINIFLANDIRMA
   Alarm tipleri iki eksende siniflanir:
     - zamansal dagilim (CV) + servis yayilimi + ortalama severity -> gurultu egilimi
     - nedensellik: NEDEN tipi mi (altyapi arizasi) yoksa SEMPTOM tipi mi (sonuc)
   Bu ayrim veri sozlugundeki tip anlamlarindan turetilir, veriye bakilarak
   dogrulanir. Tek basina alarm tipine bakmak yaniltici oldugu icin (brifing
   bunu acikca soyluyor) tip sinifi yalnizca ON BILGI olarak kullanilir; nihai
   atama zaman + topoloji + bagimlilik ile yapilir.

2. CEKIRDEK TESPITI (iki gecis)
   A) Patlama : NEDEN tipi alarmlar zaman ve servis yakinligina gore birlestirilir.
   B) Suregelen: servis bazinda taban orani sifira yakin olan NEDEN tipleri,
      patlama esigini hic asmasa bile cekirdek olusturur.
   Iki gecis sart: session-service bellek sizintisi 40 dakikaya yayildigi ve
   dakikada 1-2 alarm urettigi icin (A) onu goremez.

3. KOK SECIMI
   Her cekirdek icin kok servis, agirlikli skorla secilir:
     nedensel tip (0.40) + grafik katmani (0.25) + zamansal oncelik (0.20)
     + severity (0.15)
   Ag olaylarinda kok servis degil, TOPOLOJI (dc/kabin) kok ilan edilir; cunku
   birden fazla bagimsiz servis ayni anda ve ayni kabinde baglanti kaybediyorsa
   ortak neden servis degil altyapidir.

4. SEMPTOM ATAMASI
   Her semptom alarmi her olaya karsi skorlanir:
     zaman ortusmesi + kok servisin yayilim alaninda olmak + iliskisel alarmin
     hedefinin olay zincirinde olmasi + ag olaylarinda ayni kabinde olmak
   En yuksek skorlu olaya atanir; hicbir olay esigi gecemezse "iliskisiz" kalir.

5. KARSI OLASILIK
   Kok skorunda ikinci siradaki aday, neden daha zayif oldugu gerekcesiyle
   birlikte karta yazilir. Brifing "karsi olasiliklari belirtmek" istiyor.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
GIRDI = KOK / "data" / "alarms_clean.json"
HOSTS = KOK / "katilimci_paketi" / "host_inventory.csv"
DEPS = KOK / "katilimci_paketi" / "service_dependencies.csv"
CIKTI = KOK / "data" / "olay_kartlari.json"

# --------------------------------------------------------------------------- #
# Tip siniflandirmasi
# --------------------------------------------------------------------------- #

# Altyapi/kaynak arizasi bildiren tipler. Bunlar kok neden adayidir.
NEDEN_TIPLERI = {
    "network_down", "pkt_loss", "disk_full", "ext_unreach", "ext_slow",
    "batch_overlap", "oom_risk", "gc_pressure",
}

# Baska bir seyin sonucu olan tipler. Tek baslarina kok olamazlar.
SEMPTOM_TIPLERI = {
    "timeout", "conn_refused", "http_5xx", "latency_high", "txn_fail",
    "thread_pool", "db_conn_pool", "db_write_fail", "batch_slow", "queue_backlog",
}

# Bakim/bilgi sinifi: surekli arka planda akar, aksiyona yol acmaz.
BAKIM_TIPLERI = {
    "cert_expiry", "backup_warn", "log_rotate", "ntp_drift",
    "disk_warn", "mem_high", "cpu_high",
}

# Ag katmani arizasi: kok servis degil, topoloji olabilir.
AG_TIPLERI = {"network_down", "pkt_loss", "network_flap"}

# NEDEN tiplerinin ariza ailesi. Ayni ailedeki tipler AYNI fiziksel olgunun
# farkli asamalaridir; ayri cekirdek olusturmamalidirlar.
#   bellek     : gc_pressure once gelir, tedavi edilmezse oom_risk'e doner
#   dis_servis : ext_slow ve ext_unreach ayni saglayici kesintisinin iki yuzu
# Bu esleme olmadan tek olay iki karta bolunur (yanlis bolme = dusuk indirgeme).
TIP_AILESI = {
    "network_down": "ag", "pkt_loss": "ag", "network_flap": "ag",
    "gc_pressure": "bellek", "oom_risk": "bellek",
    "ext_unreach": "dis_servis", "ext_slow": "dis_servis",
    "disk_full": "disk",
    "batch_overlap": "batch",
}

CEKIRDEK_BOSLUK_SN = 600      # cekirdek icindeki iki neden alarmi arasi azami bosluk
ATAMA_ESIGI = 0.45            # bu skorun altinda kalan semptom olaya atanmaz

# Semptom penceresi ASIMETRIKTIR. Nedensellik tek yonlu isler: etki nedenden
# SONRA gelir. Ag arizasi 01:42-01:45 arasinda olusur ama turev thread_pool ve
# http_5xx alarmlari 01:54'e kadar surer. Simetrik bir marj bu kuyrugu keser.
# Geriye dogru kucuk bir pay birakilir (alarm uretim gecikmesi, saat sapmasi).
MARJ_GERI_SN = 180
MARJ_ILERI_SN = 900


# --------------------------------------------------------------------------- #
# Veri
# --------------------------------------------------------------------------- #

def envanter_yukle() -> dict[str, dict[str, str]]:
    with HOSTS.open(encoding="utf-8-sig", newline="") as f:
        return {r["host"]: r for r in csv.DictReader(f)}


class Grafik:
    def __init__(self) -> None:
        self.yukari: dict[str, list[dict]] = defaultdict(list)
        self.asagi: dict[str, list[dict]] = defaultdict(list)
        self.servisler: set[str] = set()
        with DEPS.open(encoding="utf-8-sig", newline="") as f:
            for r in f and csv.DictReader(f):
                k, h = r["kaynak_servis"], r["hedef_servis"]
                self.servisler.update((k, h))
                self.yukari[k].append({"servis": h, "kritiklik": r["kritiklik"]})
                self.asagi[h].append({"servis": k, "kritiklik": r["kritiklik"]})
        self._yayilim: dict[str, set[str]] = {}

    def yayilim_alani(self, servis: str) -> set[str]:
        """servis bozulursa gecisli olarak etkilenecek servisler."""
        if servis in self._yayilim:
            return self._yayilim[servis]
        gorulen: set[str] = set()
        kuyruk = deque(k["servis"] for k in self.asagi.get(servis, []))
        while kuyruk:
            s = kuyruk.popleft()
            if s in gorulen or s == servis:
                continue
            gorulen.add(s)
            kuyruk.extend(k["servis"] for k in self.asagi.get(s, []))
        self._yayilim[servis] = gorulen
        return gorulen

    def katman(self, servis: str) -> str:
        if servis not in self.servisler:
            return "grafik_disi"
        if not self.yukari.get(servis):
            return "altyapi"
        if not self.asagi.get(servis):
            return "uc"
        return "ara"


def zaman(a: dict) -> datetime:
    return datetime.fromisoformat(a["timestamp"])


# --------------------------------------------------------------------------- #
# 1. Gurultu on siniflandirmasi (veriden turetilir)
# --------------------------------------------------------------------------- #

def tip_profilleri(alarmlar: list[dict]) -> dict[str, dict]:
    """Her alarm tipi icin zamansal dagilim ve yayilim profili."""
    t0 = min(zaman(a) for a in alarmlar)
    gruplar: dict[str, list[dict]] = defaultdict(list)
    for a in alarmlar:
        gruplar[a["alarm_type"]].append(a)

    profil = {}
    for tip, grup in gruplar.items():
        kova = [0] * 120
        for a in grup:
            kova[min(119, int((zaman(a) - t0).total_seconds() // 60))] += 1
        mu = len(grup) / 120
        cv = math.sqrt(sum((x - mu) ** 2 for x in kova) / 120) / mu if mu else 0
        profil[tip] = {
            "sayi": len(grup),
            "cv": round(cv, 2),
            "servis_yayilimi": len({a["service"] for a in grup}),
            "ort_severity": round(sum(a["severity"] for a in grup) / len(grup), 2),
            "nedensellik": ("neden" if tip in NEDEN_TIPLERI else
                            "semptom" if tip in SEMPTOM_TIPLERI else "bakim"),
        }
        # Gurultu egilimi: zamana duzgun yayilmis + her servise dokunmus + dusuk siddet
        profil[tip]["gurultu_egilimi"] = (
            cv < 1.30 and profil[tip]["servis_yayilimi"] >= 20
            and profil[tip]["ort_severity"] < 2.6
        )
    return profil


# --------------------------------------------------------------------------- #
# 2. Cekirdek tespiti
# --------------------------------------------------------------------------- #

def cekirdekleri_bul(alarmlar: list[dict], profil: dict) -> list[dict]:
    """NEDEN tipi alarmlari zaman + servis yakinligina gore cekirdeklere ayirir.

    Gecis A ve B ayni mekanizmayi kullanir; farki bosluk esigidir. Patlama
    tipi cekirdekler dar boslukla, suregelen olanlar genis boslukla birlesir.
    Bu sayede 40 dakikaya yayilan gc_pressure zinciri tek cekirdek olur.
    """
    nedenler = sorted((a for a in alarmlar if a["alarm_type"] in NEDEN_TIPLERI),
                      key=zaman)
    if not nedenler:
        return []

    # Once (tip ailesi, servis) bazinda zincirler kur, sonra zincirleri birlestir.
    zincirler: dict[tuple, list[dict]] = defaultdict(list)
    for a in nedenler:
        aile = TIP_AILESI.get(a["alarm_type"], a["alarm_type"])
        zincirler[(aile, a["service"])].append(a)

    parcalar: list[dict] = []
    for (aile, servis), grup in zincirler.items():
        grup.sort(key=zaman)
        aktif = [grup[0]]
        for a in grup[1:]:
            if (zaman(a) - zaman(aktif[-1])).total_seconds() > CEKIRDEK_BOSLUK_SN:
                parcalar.append({"aile": aile, "servis": servis, "alarmlar": aktif})
                aktif = []
            aktif.append(a)
        parcalar.append({"aile": aile, "servis": servis, "alarmlar": aktif})

    # Ayni aileden, zamanda ortusen parcalari birlestir. Ag arizasi birden cok
    # servisi ayni anda vurur; bunlar tek olaydir.
    parcalar.sort(key=lambda p: zaman(p["alarmlar"][0]))
    cekirdekler: list[dict] = []
    for p in parcalar:
        bas, son = zaman(p["alarmlar"][0]), zaman(p["alarmlar"][-1])
        birlestirildi = False
        for c in cekirdekler:
            if c["aile"] != p["aile"]:
                continue
            if bas <= c["son"] + timedelta(seconds=CEKIRDEK_BOSLUK_SN):
                c["alarmlar"].extend(p["alarmlar"])
                c["servisler"].add(p["servis"])
                c["bas"] = min(c["bas"], bas)
                c["son"] = max(c["son"], son)
                birlestirildi = True
                break
        if not birlestirildi:
            cekirdekler.append({
                "aile": p["aile"], "servisler": {p["servis"]},
                "alarmlar": list(p["alarmlar"]), "bas": bas, "son": son,
            })

    for c in cekirdekler:
        c["alarmlar"].sort(key=zaman)
    return [c for c in cekirdekler if len(c["alarmlar"]) >= 3]


# --------------------------------------------------------------------------- #
# 3. Kok secimi
# --------------------------------------------------------------------------- #

def kok_sec(cekirdek: dict, grafik: Grafik, envanter: dict) -> tuple[dict, list[dict]]:
    """Cekirdek icin kok aday siralamasi dondurur: (kazanan, tum_adaylar)."""
    ilk = cekirdek["bas"]
    adaylar: list[dict] = []

    for servis in sorted(cekirdek["servisler"]):
        ait = [a for a in cekirdek["alarmlar"] if a["service"] == servis]
        if not ait:
            continue
        p_neden = 1.0 if all(a["alarm_type"] in NEDEN_TIPLERI for a in ait) else 0.5
        p_katman = {"altyapi": 1.0, "ara": 0.5, "uc": 0.15, "grafik_disi": 0.3}[
            grafik.katman(servis)]
        gecikme = (zaman(ait[0]) - ilk).total_seconds()
        p_zaman = max(0.0, 1.0 - gecikme / 600.0)
        p_sev = (sum(a["severity"] for a in ait) / len(ait)) / 5.0

        skor = 0.40 * p_neden + 0.25 * p_katman + 0.20 * p_zaman + 0.15 * p_sev
        adaylar.append({
            "servis": servis,
            "skor": round(skor, 3),
            "alarm_sayisi": len(ait),
            "ilk_alarm": ait[0]["timestamp"],
            "gecikme_sn": int(gecikme),
            "grafik_katmani": grafik.katman(servis),
            "yayilim_alani": len(grafik.yayilim_alani(servis)),
            "kirilim": {
                "nedensel_tip": round(0.40 * p_neden, 3),
                "grafik_katmani": round(0.25 * p_katman, 3),
                "zamansal_oncelik": round(0.20 * p_zaman, 3),
                "severity": round(0.15 * p_sev, 3),
            },
        })

    adaylar.sort(key=lambda x: (-x["skor"], x["ilk_alarm"]))
    return adaylar[0], adaylar


def topolojik_kok(cekirdek: dict, envanter: dict) -> dict | None:
    """Ag olaylarinda ortak kabin/DC arar.

    Birden fazla BAGIMSIZ servis ayni anda ve agirlikli olarak ayni kabinde
    baglanti kaybediyorsa kok servis degil altyapidir. Esik: kabin payi >= %40
    ve en az 3 farkli servis.
    """
    if cekirdek["aile"] != "ag":
        return None
    yer = Counter()
    for a in cekirdek["alarmlar"]:
        e = envanter.get(a["host"])
        if e:
            yer[(e["veri_merkezi"], e["kabin"])] += 1
    if not yer:
        return None
    (dc, kabin), n = yer.most_common(1)[0]
    pay = n / sum(yer.values())
    if pay >= 0.40 and len(cekirdek["servisler"]) >= 3:
        return {"dc": dc, "kabin": kabin, "pay": round(pay, 3), "alarm": n,
                "dagilim": {f"{k[0]}/{k[1]}": v for k, v in yer.most_common()}}
    return None


# --------------------------------------------------------------------------- #
# 4. Semptom atamasi
# --------------------------------------------------------------------------- #

def semptomlari_ata(alarmlar: list[dict], olaylar: list[dict],
                    grafik: Grafik, envanter: dict, profil: dict) -> None:
    """Her semptom/gurultu alarmini en uygun olaya atar ya da iliskisiz birakir."""
    for olay in olaylar:
        olay["uyeler"] = list(olay["cekirdek"]["alarmlar"])
        olay["_cekirdek_idler"] = {a["alarm_id"] for a in olay["cekirdek"]["alarmlar"]}
        kok = olay["kok_servis"]
        olay["_kapsam"] = ({kok} | grafik.yayilim_alani(kok)) if kok else set()
        olay["_kapsam"] |= olay["cekirdek"]["servisler"]

    for a in alarmlar:
        if any(a["alarm_id"] in o["_cekirdek_idler"] for o in olaylar):
            continue
        t = zaman(a)
        env = envanter.get(a["host"], {})
        en_iyi, en_iyi_skor, gerekce = None, 0.0, []

        for olay in olaylar:
            c = olay["cekirdek"]
            if not (c["bas"] - timedelta(seconds=MARJ_GERI_SN) <= t
                    <= c["son"] + timedelta(seconds=MARJ_ILERI_SN)):
                continue
            g: list[str] = ["zaman_penceresi"]
            skor = 0.30

            if a["service"] in olay["_kapsam"]:
                skor += 0.30
                g.append("kok_yayilim_alaninda")

            hedef = a["tekrar"]["hedef_servis"]
            if hedef and (hedef in olay["_kapsam"] or hedef == olay["kok_servis"]):
                skor += 0.25
                g.append(f"hedef={hedef}")

            if olay["topoloji"] and env:
                if (env["veri_merkezi"], env["kabin"]) == (
                        olay["topoloji"]["dc"], olay["topoloji"]["kabin"]):
                    skor += 0.30
                    g.append("ayni_kabin")

            if a["alarm_type"] in SEMPTOM_TIPLERI:
                skor += 0.10
                g.append("semptom_tipi")
            if profil[a["alarm_type"]]["gurultu_egilimi"]:
                skor -= 0.25
                g.append("gurultu_egilimli_tip")

            if skor > en_iyi_skor:
                en_iyi, en_iyi_skor, gerekce = olay, skor, g

        if en_iyi and en_iyi_skor >= ATAMA_ESIGI:
            en_iyi["uyeler"].append(a)
            a["_atama"] = {"olay": en_iyi["id"], "skor": round(en_iyi_skor, 2),
                           "gerekce": gerekce}
        else:
            a["_atama"] = None
            a["_eleme"] = (
                "BAKIM_SINIFI" if a["alarm_type"] in BAKIM_TIPLERI else
                "ARKA_PLAN_DUZGUN_DAGILIM" if profil[a["alarm_type"]]["gurultu_egilimi"] else
                "PENCERE_DISI" if not any(
                    o["cekirdek"]["bas"] - timedelta(seconds=MARJ_GERI_SN) <= t
                    <= o["cekirdek"]["son"] + timedelta(seconds=MARJ_ILERI_SN)
                    for o in olaylar) else
                "TOPOLOJI_ILISKISIZ"
            )


# --------------------------------------------------------------------------- #
# 5. Kart uretimi
# --------------------------------------------------------------------------- #

AKSIYON_SABLONU = {
    "ag": ("{yer} kabinindeki ag baglantisini ve switch port durumunu kontrol et; "
           "etkilenen hostlarda arayuz link durumunu dogrula", "nobetci-network"),
    "disk_full": ("{servis} uzerinde disk alanini bosalt veya genislet; "
                  "tablespace otomatik buyumesini dogrula", "nobetci-dba"),
    "ext_unreach": ("{servis} saglayicisiyla iletisime gec; devre kesici (circuit breaker) "
                    "devreye alarak cagrilari kuyrukla", "nobetci-entegrasyon"),
    "ext_slow": ("{servis} saglayicisiyla iletisime gec; timeout degerlerini gozden gecir",
                 "nobetci-entegrasyon"),
    "oom_risk": ("{servis} ornegini kontrollu yeniden baslat; heap dump al ve "
                 "bellek sizintisini analiz et", "nobetci-uygulama"),
    "gc_pressure": ("{servis} heap kullanimini izle; GC parametrelerini gozden gecir, "
                    "oom_risk'e donusmeden mudahale et", "nobetci-uygulama"),
    "batch_overlap": ("Cakisan toplu is pencerelerini ayir; {servis} zamanlamasini "
                      "erteleyerek DB uzerindeki es zamanli yuku dusur", "nobetci-batch"),
}


def kart_uret(olay: dict, grafik: Grafik, adaylar: list[dict]) -> dict:
    uyeler = olay["uyeler"]
    uyeler.sort(key=zaman)
    servisler = Counter(a["service"] for a in uyeler)
    tipler = Counter(a["alarm_type"] for a in uyeler)
    kok = olay["kok_servis"]
    topo = olay["topoloji"]
    kok_tip = Counter(a["alarm_type"] for a in olay["cekirdek"]["alarmlar"]).most_common(1)[0][0]

    if topo:
        hipotez = (f"{topo['dc']}/{topo['kabin']} kabininde ag katmani arizasi: "
                   f"{len(olay['cekirdek']['servisler'])} bagimsiz servis ayni anda "
                   f"baglanti kaybi bildirdi")
        sablon, sahip = AKSIYON_SABLONU["ag"]
        aksiyon = sablon.format(yer=f"{topo['dc']}/{topo['kabin']}")
    else:
        hipotez = f"{kok} uzerinde {kok_tip}"
        sablon, sahip = AKSIYON_SABLONU.get(
            kok_tip, ("Kok servis {servis} uzerinde ilgili bileseni incele", "nobetci-muhendis"))
        aksiyon = sablon.format(servis=kok)

    karsi = []
    for alt in adaylar[1:3]:
        karsi.append({
            "alternatif": f"{alt['servis']} ({alt['grafik_katmani']} katmani)",
            "neden_daha_zayif": (
                f"skor {alt['skor']} < {adaylar[0]['skor']}; "
                f"ilk alarmi {alt['gecikme_sn']} sn sonra geldi, "
                f"grafik katmani '{alt['grafik_katmani']}'"),
        })
    if topo:
        ikinci = topo["dagilim"]
        karsi.append({
            "alternatif": "Tek servis kaynakli ariza",
            "neden_daha_zayif": (
                f"Alarmlarin %{topo['pay']*100:.0f}'i tek kabinde toplandi "
                f"({topo['dagilim']}); birbirine bagimli olmayan servisler ayni anda "
                f"etkilendi, bu servis seviyesi bir arizayla aciklanamaz"),
        })

    return {
        "id": olay["id"],
        "durum": "ACIK",
        "kok_neden_hipotezi": hipotez,
        "kok_servis": kok,
        "kok_topoloji": f"{topo['dc']}/{topo['kabin']}" if topo else None,
        "gerekce": olay["gerekce"],
        "karsi_olasiliklar": karsi,
        "alarm_sayisi": len(uyeler),
        "zaman_araligi": {
            "baslangic": uyeler[0]["timestamp"],
            "bitis": uyeler[-1]["timestamp"],
            "sure_dk": round((zaman(uyeler[-1]) - zaman(uyeler[0])).total_seconds() / 60, 1),
        },
        "etkilenen_servisler": [{"servis": s, "alarm": n} for s, n in servisler.most_common()],
        "etkilenen_servis_sayisi": len(servisler),
        "en_yuksek_severity": max(a["severity"] for a in uyeler),
        "alarm_tipi_dagilimi": dict(tipler.most_common()),
        "aksiyon": {
            "id": f"ACT-{olay['id'].split('-')[1]}",
            "aciklama": aksiyon,
            "sahip": sahip,
            "durum": "ACIK",
            "olusturma": uyeler[0]["timestamp"],
        },
        "kok_aday_siralamasi": adaylar[:4],
        "kanit_alarmlari": [
            {"alarm_id": a["alarm_id"], "zaman": a["timestamp"][11:], "sev": a["severity"],
             "servis": a["service"], "tip": a["alarm_type"], "mesaj": a["message"]}
            for a in olay["cekirdek"]["alarmlar"][:6]
        ],
        "uye_alarm_idleri": [a["alarm_id"] for a in uyeler],
    }


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description="Alarm korelasyonu ve kok neden kartlari.")
    ap.add_argument("--detay", action="store_true", help="Kanit dokumunu de yaz.")
    args = ap.parse_args()

    if not GIRDI.exists():
        sys.exit(f"HATA: {GIRDI} yok. Once: python src/clean_alarms.py")

    alarmlar = json.loads(GIRDI.read_text(encoding="utf-8"))
    envanter = envanter_yukle()
    grafik = Grafik()
    profil = tip_profilleri(alarmlar)

    print(f"Yuklendi: {len(alarmlar)} alarm\n")
    print("=" * 78)
    print("1) TIP SINIFLANDIRMASI")
    print("=" * 78)
    print(f"  {'tip':16s} {'n':>5s} {'CV':>6s} {'svc':>4s} {'sev':>5s}  {'sinif':9s} gurultu")
    for tip, p in sorted(profil.items(), key=lambda x: -x[1]["cv"]):
        print(f"  {tip:16s} {p['sayi']:5d} {p['cv']:6.2f} {p['servis_yayilimi']:4d} "
              f"{p['ort_severity']:5.2f}  {p['nedensellik']:9s} "
              f"{'EVET' if p['gurultu_egilimi'] else ''}")

    cekirdekler = cekirdekleri_bul(alarmlar, profil)
    print(f"\n{'=' * 78}\n2) CEKIRDEK TESPITI -> {len(cekirdekler)} cekirdek\n{'=' * 78}")

    olaylar: list[dict] = []
    aday_kaydi: dict[str, list[dict]] = {}
    for i, c in enumerate(sorted(cekirdekler, key=lambda x: x["bas"]), start=1):
        topo = topolojik_kok(c, envanter)
        kazanan, adaylar = kok_sec(c, grafik, envanter)
        oid = f"OLAY-{i:03d}"

        if topo:
            gerekce = (
                f"{len(c['servisler'])} bagimsiz servis {c['bas'].strftime('%H:%M:%S')} - "
                f"{c['son'].strftime('%H:%M:%S')} arasinda ag alarmi uretti; "
                f"alarmlarin %{topo['pay']*100:.0f}'i {topo['dc']}/{topo['kabin']} "
                f"kabininde toplandi. Ortak neden servis degil kabin seviyesi altyapi.")
            kok = None
        else:
            k = kazanan
            gerekce = (
                f"{k['servis']} secildi (skor {k['skor']}): "
                f"nedensel tip +{k['kirilim']['nedensel_tip']}, "
                f"grafik katmani '{k['grafik_katmani']}' +{k['kirilim']['grafik_katmani']}, "
                f"zamansal oncelik +{k['kirilim']['zamansal_oncelik']} "
                f"(cekirdegin ilk alarmi), severity +{k['kirilim']['severity']}. "
                f"Yayilim alani {k['yayilim_alani']} servis.")
            kok = k["servis"]

        olaylar.append({"id": oid, "cekirdek": c, "kok_servis": kok,
                        "topoloji": topo, "gerekce": gerekce})
        aday_kaydi[oid] = adaylar
        yer = f"{topo['dc']}/{topo['kabin']}" if topo else kok
        print(f"  {oid}  {c['bas'].strftime('%H:%M')}-{c['son'].strftime('%H:%M')}  "
              f"aile={c['aile']:14s} kok={str(yer):22s} cekirdek={len(c['alarmlar'])}")

    semptomlari_ata(alarmlar, olaylar, grafik, envanter, profil)

    kartlar = [kart_uret(o, grafik, aday_kaydi[o["id"]]) for o in olaylar]
    kartlar.sort(key=lambda k: (-k["en_yuksek_severity"], k["zaman_araligi"]["baslangic"]))

    atanan = sum(k["alarm_sayisi"] for k in kartlar)
    elenen = Counter(a["_eleme"] for a in alarmlar if a.get("_eleme"))

    print(f"\n{'=' * 78}\n3) SONUC\n{'=' * 78}")
    print(f"  Olay karti           : {len(kartlar)}")
    print(f"  Karta atanan alarm   : {atanan} / {len(alarmlar)} "
          f"(%{atanan / len(alarmlar) * 100:.1f})")
    print(f"  Elenen (gurultu)     : {len(alarmlar) - atanan} "
          f"(%{(len(alarmlar) - atanan) / len(alarmlar) * 100:.1f})")
    for kod, n in elenen.most_common():
        print(f"      {kod:28s} {n:5d}")
    print(f"  INDIRGEME            : {len(alarmlar)} alarm -> {len(kartlar)} kart "
          f"(%{len(kartlar) / len(alarmlar) * 100:.2f})")

    print(f"\n{'=' * 78}\nKOK NEDEN KARTLARI\n{'=' * 78}")
    for k in kartlar:
        print(f"\n{'-' * 78}")
        print(f"{k['id']}  [{k['durum']}]{' ' * 34}en yuksek severity: {k['en_yuksek_severity']}")
        print(f"{'-' * 78}")
        print(f"  KOK NEDEN     : {k['kok_neden_hipotezi']}")
        print(f"  GEREKCE       : {k['gerekce']}")
        for c in k["karsi_olasiliklar"][:2]:
            print(f"  KARSI OLASILIK: {c['alternatif']}")
            print(f"                  -> {c['neden_daha_zayif']}")
        print(f"  ZAMAN         : {k['zaman_araligi']['baslangic'][11:]} - "
              f"{k['zaman_araligi']['bitis'][11:]}  ({k['zaman_araligi']['sure_dk']} dk)")
        print(f"  ALARM SAYISI  : {k['alarm_sayisi']}")
        print(f"  ETKILENEN     : {k['etkilenen_servis_sayisi']} servis — " +
              ", ".join(f"{s['servis']}({s['alarm']})" for s in k["etkilenen_servisler"][:7]))
        print(f"  ALARM TIPLERI : " +
              ", ".join(f"{t}:{n}" for t, n in list(k["alarm_tipi_dagilimi"].items())[:7]))
        a = k["aksiyon"]
        print(f"  AKSIYON {a['id']} : {a['aciklama']}")
        print(f"                  sahip={a['sahip']}  durum={a['durum']}")
        if args.detay:
            print("  KANIT:")
            for e in k["kanit_alarmlari"]:
                print(f"    {e['zaman']} sev{e['sev']} {e['servis']:20s} {e['tip']:14s} "
                      f"{e['mesaj'][:50]}")

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps({
        "uretim": {"girdi_alarm": len(alarmlar), "kart_sayisi": len(kartlar),
                   "atanan_alarm": atanan, "elenen_alarm": len(alarmlar) - atanan,
                   "eleme_gerekceleri": dict(elenen)},
        "tip_profilleri": profil,
        "kartlar": kartlar,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nYazildi: {CIKTI.relative_to(KOK)}")


if __name__ == "__main__":
    main()
