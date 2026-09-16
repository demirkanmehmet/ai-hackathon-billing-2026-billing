"""S-A1 Alarm Firtinasi — uctan uca boru hatti.

Girdi : katilimci_paketi/alarms.json (ham, 3000 alarm)
Cikti : data/pipeline/*.json  ve ekrana aksiyon kartlari

    python src/pipeline.py                    # tam kosu
    python src/pipeline.py --detay            # kanit dokumu ile
    python src/pipeline.py --asama 3          # yalnizca ilk 3 asamayi kosur
    python src/pipeline.py --paylasilan-kaynak  # paylasilan kaynak yayilimini ac

LLM KULLANILMAZ. Tum cikarimlar deterministik koddur: ayni girdi -> ayni cikti.
Bu bilincli bir karardir; juri repoyu klonlayip kostugunda ayni kartlari gormeli
ve her kararin gerekcesi skor kirilimindan okunabilmelidir.

================================================================================
ASAMALAR
================================================================================
  1 YUKLE     ham alarm + host envanteri + bagimlilik grafigi
  2 TEMIZLE   duplike taramasi, kalite denetimi, siralama
  3 ETIKETLE  envanter/bagimlilik zenginlestirmesi + ALARM BAZINDA SKORLAMA
  4 GRUPLA    tekrar zincirleri -> temsilci + sayac
  5 KORELE    cekirdek tespiti -> kok secimi -> semptom atamasi
  6 KARTLASTIR  oncelik skoru + sahip + durum ile aksiyon kartlari

================================================================================
SKORLAMA MEKANIZMASI (Asama 3)
================================================================================
Her alarm 0-1 arasi bir `sinyal_skoru` alir. Bes bilesenin agirlikli toplami,
tekrar konumuna gore sonumlendirilir:

  0.26  nadirlik      Alarmin dustugu anda kendi tipinin taban oranina gore
                      ne kadar yogunlastigi. ORNEK BAZINDA hesaplanir: normalde
                      gurultu olan bir tip, kendi patlamasi sirasinda yuksek
                      skor alir. Tip listesine gomulu "bu tip gurultudur"
                      varsayimindan bu yuzden daha iyidir.
  0.22  nedensellik   NEDEN tipi mi (altyapi arizasi) yoksa SEMPTOM mu.
  0.22  siddet        severity / 5
  0.15  is_kritikligi Host envanterindeki is kritikligi.
  0.15  topoloji      Servisin grafik katmani x yayilim alani genisligi.

  x tekrar_sonumu     Zincirin k. alarmi: 1 / (1 + 0.15*(k-1)).
                      Ayni olgunun besinci tekrari, birincisi kadar bilgi
                      tasimaz; ama sifirlanmaz cunku sureklilik de bilgidir.
  x cok_kaynak        Zinciri birden fazla izleme sistemi dogruladiysa +%5/sistem.

Gurultu karari bu skora gore verilir (GURULTU_ESIGI), sabit tip listesine gore
degil. Tip listeleri yalnizca `nedensellik` bilesenini besler.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parent.parent
VARSAYILAN_GIRDI = KOK / "katilimci_paketi" / "alarms.json"
HOSTS = KOK / "katilimci_paketi" / "host_inventory.csv"
DEPS = KOK / "katilimci_paketi" / "service_dependencies.csv"
CIKTI_DIZIN = KOK / "data" / "pipeline"

# --------------------------------------------------------------------------- #
# Sabitler
# --------------------------------------------------------------------------- #

NEDEN_TIPLERI = {
    "network_down", "pkt_loss", "disk_full", "ext_unreach", "ext_slow",
    "batch_overlap", "oom_risk", "gc_pressure",
}
SEMPTOM_TIPLERI = {
    "timeout", "conn_refused", "http_5xx", "latency_high", "txn_fail",
    "thread_pool", "db_conn_pool", "db_write_fail", "batch_slow", "queue_backlog",
}
BAKIM_TIPLERI = {
    "cert_expiry", "backup_warn", "log_rotate", "ntp_drift",
    "disk_warn", "mem_high", "cpu_high", "network_flap",
}
# Ayni fiziksel olgunun farkli asamalari; ayri cekirdek olusturmamalidirlar.
TIP_AILESI = {
    "network_down": "ag", "pkt_loss": "ag", "network_flap": "ag",
    "gc_pressure": "bellek", "oom_risk": "bellek",
    "ext_unreach": "dis_servis", "ext_slow": "dis_servis",
    "disk_full": "disk", "batch_overlap": "batch",
}
KRITIKLIK_PUAN = {"kritik": 1.0, "yuksek": 0.75, "orta": 0.5, "dusuk": 0.25}
KATMAN_PUAN = {"altyapi": 1.0, "ara": 0.55, "uc": 0.20, "grafik_disi": 0.30}

# Iliskisel alarmlarda hedef servis mesajda gecer; zincir bolmede sart.
HEDEF_KALIPLARI = (
    re.compile(r"^([a-z0-9-]+) servisine"),
    re.compile(r"^([a-z0-9-]+) baglantisi"),
    re.compile(r"^Dis servis ([a-z0-9-]+)"),
)
ILISKISEL_TIPLER = {"timeout", "conn_refused", "ext_unreach", "ext_slow"}

# --------------------------------------------------------------------------- #
# SINYAL SKORU AGIRLIKLARI
# --------------------------------------------------------------------------- #
# Bu agirliklar veri uzerinde olculerek secildi. Olcut: olaya atanan alarmlarin
# skor ortalamasi ile gurultunun skor ortalamasi arasindaki AYRIM (Cohen's d).
# Denenen varyantlar ve elde edilen ayrim:
#
#   nadirlik .26 / nedensellik .22 / siddet .22 / kritiklik .15 / topoloji .15  -> d=1.688
#   nadirlik .26 / nedensellik .34 / siddet .22 / kritiklik .09 / topoloji .09  -> d=1.815
#   nadirlik .32 / nedensellik .38 / siddet .30 / kritiklik .00 / topoloji .00  -> d=1.863  <-
#   nadirlik .28 / nedensellik .45 / siddet .27 / kritiklik .00 / topoloji .00  -> d=1.865
#
# is_kritikligi ve topoloji SINYAL skorundan cikarildi. Gerekce olcumdur:
#   is_kritikligi : olay-gurultu ortalama farki yalnizca +0.0077. 56 hostun 36'si
#                   "kritik" oldugu icin bilesen neredeyse sabit; bilgi tasimiyor.
#   topoloji      : fark -0.0117, yani TERS calisiyordu. Arka plan gurultusu tum
#                   servislere esit yayildigi icin altyapi katmanindan da bolca
#                   gurultu geliyor (yuksek puan alir); turev alarmlar ise uc
#                   katman servislerinde yogunlasiyor (dusuk puan alir).
#
# Ikisi de sistemden ATILMADI, dogru yere tasindi:
#   is_kritikligi -> oncelik_skoru() icinde "kritik servis sayisi" olarak
#   topoloji      -> kok_sec() icinde 0.25 agirlikla (orada dogru soruyu cevapliyor:
#                    "bu servis makul bir kok mu?" — "bu alarm bilgilendirici mi?" degil)
AGIRLIK = {"nedensellik": 0.38, "nadirlik": 0.32, "siddet": 0.30}

# Nedensellik sinifinin skora katkisi. Siniflar arasi mesafe, olculen atanma
# oranlarina dayanir: neden %100, semptom %60.5, bakim %8.0 olaya atandi.
NEDENSELLIK_PUAN = {"neden": 1.0, "semptom": 0.55, "bakim": 0.10}

# Esikler — hepsi tek yerde, kalibrasyon icin.
ZINCIR_BOSLUK_SN = 300        # tekrar zinciri kirilma esigi
NADIRLIK_PENCERE_DK = 2       # ornek bazinda yogunluk penceresi (+/-)
NADIRLIK_TAVAN = 5.0          # taban oranin kac kati "tam nadir" sayilir
# Yeni agirliklarla olculen dagilim: NEDEN alarmlari min 0.816 / ort 0.966,
# BAKIM alarmlari max 0.543 / ort 0.235. Iki sinif ORTUSMUYOR.
GURULTU_ESIGI = 0.36          # bakim sinifinin p95'i (0.352) hemen ustu
CEKIRDEK_ESIGI = 0.55         # en dusuk NEDEN alarmindan (0.816) belirgin altta:
                              # esik guvenli, farkli veride de olay kaybettirmez
CEKIRDEK_BOSLUK_SN = 600      # cekirdek icindeki iki neden alarmi arasi bosluk
MARJ_GERI_SN = 180            # semptom penceresi: nedenden once
MARJ_ILERI_SN = 900           # semptom penceresi: nedenden sonra (etki gecikir)
ATAMA_ESIGI = 0.45            # semptomun olaya atanmasi icin gereken skor
ASGARI_CEKIRDEK_ALARM = 3     # bundan kucuk cekirdek olay sayilmaz


def zaman(a: dict) -> datetime:
    return datetime.fromisoformat(a["timestamp"])


def bolum(baslik: str) -> None:
    print(f"\n{'=' * 78}\n{baslik}\n{'=' * 78}")


# =========================================================================== #
# ASAMA 1 — YUKLE
# =========================================================================== #

class Grafik:
    """Servis bagimlilik grafigi. Kenar: kaynak --bagimlidir--> hedef."""

    def __init__(self, yol: Path) -> None:
        self.yukari: dict[str, list[dict]] = defaultdict(list)
        self.asagi: dict[str, list[dict]] = defaultdict(list)
        self.kenarlar: set[tuple[str, str]] = set()
        self.servisler: set[str] = set()
        with yol.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                k, h = r["kaynak_servis"], r["hedef_servis"]
                self.servisler.update((k, h))
                self.kenarlar.add((k, h))
                self.yukari[k].append({"servis": h, "kritiklik": r["kritiklik"],
                                       "tip": r["bagimlilik_tipi"]})
                self.asagi[h].append({"servis": k, "kritiklik": r["kritiklik"],
                                      "tip": r["bagimlilik_tipi"]})
        self._yayilim: dict[str, set[str]] = {}
        self._paylasilan: dict[str, set[str]] = {}

    def _gecisli(self, bas: str, komsu: dict[str, list[dict]]) -> set[str]:
        gorulen: set[str] = set()
        kuyruk = deque(k["servis"] for k in komsu.get(bas, []))
        while kuyruk:
            s = kuyruk.popleft()
            if s in gorulen or s == bas:
                continue
            gorulen.add(s)
            kuyruk.extend(k["servis"] for k in komsu.get(s, []))
        return gorulen

    def yayilim_alani(self, servis: str) -> set[str]:
        """servis bozulursa gecisli olarak etkilenecek servisler."""
        if servis not in self._yayilim:
            self._yayilim[servis] = self._gecisli(servis, self.asagi)
        return self._yayilim[servis]

    def kok_adaylari(self, servis: str) -> set[str]:
        """servisteki arizanin kokunde olabilecek gecisli servisler."""
        return self._gecisli(servis, self.yukari)

    def paylasilan_kaynak_alani(self, servis: str) -> set[str]:
        """Yayilim alanina, alt akistaki servislerin PAYLASTIGI hedefleri ve
        o hedeflerin diger tuketicilerini ekler.

        Gerekce: batch_overlap ornegi. batch-scheduler bozulunca reconciliation
        ve report batch'leri ayni anda kosar; ikisi de subscriber-db'yi sorgular
        ve havuzu tuketir. subscriber-db grafikte batch-scheduler'in alt akisinda
        DEGIL, yan kardesidir. Tek yonlu yayilim bu sicramayi goremez.

        Bu genisletme fazla birlestirme riski tasir (paylasilan altyapi uzerinden
        her sey birbirine baglanabilir), bu yuzden varsayilan olarak KAPALIDIR.
        """
        if servis in self._paylasilan:
            return self._paylasilan[servis]
        alan = set(self.yayilim_alani(servis))
        hedefler: set[str] = set()
        for s in alan | {servis}:
            hedefler.update(k["servis"] for k in self.yukari.get(s, []))
        for h in hedefler:
            alan.add(h)
            alan.update(k["servis"] for k in self.asagi.get(h, []))
        alan.discard(servis)
        self._paylasilan[servis] = alan
        return alan

    def katman(self, servis: str) -> str:
        if servis not in self.servisler:
            return "grafik_disi"
        if not self.yukari.get(servis):
            return "altyapi"
        if not self.asagi.get(servis):
            return "uc"
        return "ara"


def asama1_yukle(girdi: Path) -> tuple[list[dict], dict[str, dict], Grafik]:
    bolum("ASAMA 1 — YUKLE")
    alarmlar = json.loads(girdi.read_text(encoding="utf-8"))
    with HOSTS.open(encoding="utf-8-sig", newline="") as f:
        envanter = {r["host"]: r for r in csv.DictReader(f)}
    grafik = Grafik(DEPS)
    print(f"  Alarm            : {len(alarmlar)}")
    print(f"  Host envanteri   : {len(envanter)}")
    print(f"  Bagimlilik kenari: {len(grafik.kenarlar)} ({len(grafik.servisler)} servis)")
    t = sorted(a["timestamp"] for a in alarmlar)
    print(f"  Gozlem penceresi : {t[0][11:]} - {t[-1][11:]}")
    return alarmlar, envanter, grafik


# =========================================================================== #
# ASAMA 2 — TEMIZLE
# =========================================================================== #

def _icerik_imzasi(a: dict) -> str:
    return json.dumps({k: v for k, v in a.items() if k != "alarm_id"},
                      sort_keys=True, ensure_ascii=False)


def asama2_temizle(alarmlar: list[dict], envanter: dict) -> tuple[list[dict], dict]:
    bolum("ASAMA 2 — TEMIZLE")

    # --- duplike taramasi ---
    id_tekrar = {k: v for k, v in Counter(a["alarm_id"] for a in alarmlar).items() if v > 1}
    imza: dict[str, list[str]] = defaultdict(list)
    for a in alarmlar:
        imza[_icerik_imzasi(a)].append(a["alarm_id"])
    tam_dup = {i: ids for i, ids in imza.items() if len(ids) > 1}

    cakisma: dict[tuple, list[dict]] = defaultdict(list)
    for a in alarmlar:
        cakisma[(a["timestamp"], a["host"], a["alarm_type"])].append(a)
    cakisan = {k: v for k, v in cakisma.items() if len(v) > 1}
    # Farkli izleme sistemleri ayni olguyu bildiriyorsa bu duplike degildir.
    cok_kaynakli = sum(1 for v in cakisan.values()
                       if len({x["source_system"] for x in v}) == len(v))

    print(f"  Tekrarlanan alarm_id : {len(id_tekrar)}")
    print(f"  Tam kayit duplikesi  : {len(tam_dup)} grup")
    print(f"  Ayni sn+host+tip     : {len(cakisan)} "
          f"(cok kaynakli {cok_kaynakli}, supheli {len(cakisan) - cok_kaynakli})")

    # --- kalite denetimi ---
    bulgu: Counter = Counter()
    for a in alarmlar:
        if not re.fullmatch(r"ALM-\d{5}", str(a.get("alarm_id", ""))):
            bulgu["alarm_id_formati"] += 1
        if not isinstance(a.get("severity"), int) or not 1 <= a["severity"] <= 5:
            bulgu["severity_aralik_disi"] += 1
        if a.get("alarm_type") not in NEDEN_TIPLERI | SEMPTOM_TIPLERI | BAKIM_TIPLERI:
            bulgu["bilinmeyen_alarm_tipi"] += 1
        if set(a.get("tags") or {}) != {"veri_merkezi", "kabin", "ortam"}:
            bulgu["tags_anahtar_farkli"] += 1
        e = envanter.get(a.get("host", ""))
        if not e:
            bulgu["envanterde_olmayan_host"] += 1
        elif e["servis"] != a.get("service"):
            bulgu["servis_uyusmazligi"] += 1
    print(f"  Kalite bulgusu       : {sum(bulgu.values())}"
          + (f"  {dict(bulgu)}" if bulgu else "  (temiz)"))

    # --- temizlik: gercek duplikeleri dusur, zamana gore sirala ---
    gorulen: set[str] = set()
    temiz, dusen = [], []
    for a in alarmlar:
        s = _icerik_imzasi(a)
        (dusen if s in gorulen else temiz).append(a["alarm_id"] if s in gorulen else a)
        gorulen.add(s)
    temiz.sort(key=lambda a: (a["timestamp"], a["alarm_id"]))
    print(f"  Dusurulen duplike    : {len(dusen)}")
    print(f"  Cikti                : {len(temiz)} kayit, (timestamp, alarm_id) sirali")

    return temiz, {"tekrarlanan_id": len(id_tekrar), "tam_duplike": len(tam_dup),
                   "cakisan_anahtar": len(cakisan), "cok_kaynakli_cakisma": cok_kaynakli,
                   "kalite_bulgulari": dict(bulgu), "dusurulen": dusen}


# =========================================================================== #
# ASAMA 3 — ETIKETLE (zenginlestirme + skorlama)
# =========================================================================== #

def hedef_servis(a: dict) -> str | None:
    if a["alarm_type"] not in ILISKISEL_TIPLER:
        return None
    for kalip in HEDEF_KALIPLARI:
        m = kalip.match(a["message"])
        if m:
            return m.group(1)
    return None


def tip_profilleri(alarmlar: list[dict]) -> dict[str, dict]:
    """Tip bazinda zamansal dagilim profili ve dakika histogrami."""
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
            "_kova": kova,
            "_taban_dk": mu,
        }
    return profil


def nadirlik(a: dict, profil: dict, t0: datetime) -> float:
    """Alarmin dustugu andaki yerel yogunlugun taban orana bolumu, 0-1'e sikistirilmis.

    ORNEK BAZINDA calisir: `mem_high` genelde gurultudur ama bir servis 3 dakikada
    20 mem_high uretiyorsa o ornekler yuksek skor alir. Tip seviyesinde "bu tip
    gurultudur" demek bu bilgiyi kaybeder.
    """
    p = profil[a["alarm_type"]]
    if p["_taban_dk"] <= 0:
        return 0.0
    dk = min(119, int((zaman(a) - t0).total_seconds() // 60))
    lo, hi = max(0, dk - NADIRLIK_PENCERE_DK), min(120, dk + NADIRLIK_PENCERE_DK + 1)
    yerel = sum(p["_kova"][lo:hi]) / (hi - lo)
    return min(yerel / p["_taban_dk"] / NADIRLIK_TAVAN, 1.0)


def asama3_etiketle(alarmlar: list[dict], envanter: dict, grafik: Grafik) -> dict:
    bolum("ASAMA 3 — ETIKETLE (zenginlestirme + alarm skorlamasi)")
    profil = tip_profilleri(alarmlar)
    t0 = min(zaman(a) for a in alarmlar)

    for a in alarmlar:
        servis = a["service"]
        env = envanter.get(a["host"], {})
        katman = grafik.katman(servis)
        yayilim = grafik.yayilim_alani(servis)
        hedef = hedef_servis(a)

        a["etiket"] = {
            "kaynak_servis": servis,
            "hedef_servis": hedef,
            "is_kritikligi": env.get("is_kritikligi"),
            "veri_merkezi": env.get("veri_merkezi"),
            "kabin": env.get("kabin"),
            "grafik_katmani": katman,
            "yayilim_alani_sayisi": len(yayilim),
            "bagimli_oldugu_sayisi": len(grafik.yukari.get(servis, [])),
            "nedensellik": profil[a["alarm_type"]]["nedensellik"],
            "tip_ailesi": TIP_AILESI.get(a["alarm_type"]),
            "bagimlilik_eslesmesi": (
                "iliskisel_degil" if hedef is None else
                "kendine" if hedef == servis else
                "dogrudan" if (servis, hedef) in grafik.kenarlar else
                "gecisli" if hedef in grafik.yayilim_alani(hedef) | grafik.kok_adaylari(servis)
                else "yol_yok"),
        }

        p_nadir = nadirlik(a, profil, t0)
        p_neden = NEDENSELLIK_PUAN[a["etiket"]["nedensellik"]]
        p_sev = a["severity"] / 5.0

        ham = (AGIRLIK["nedensellik"] * p_neden
               + AGIRLIK["nadirlik"] * p_nadir
               + AGIRLIK["siddet"] * p_sev)
        a["skor"] = {
            "ham": round(ham, 4),
            "kirilim": {
                "nedensellik": round(AGIRLIK["nedensellik"] * p_neden, 4),
                "nadirlik": round(AGIRLIK["nadirlik"] * p_nadir, 4),
                "siddet": round(AGIRLIK["siddet"] * p_sev, 4),
            },
            # Bilgi amacli tasinir; sinyal skoruna GIRMEZ (gerekce: AGIRLIK notu).
            # is_kritikligi oncelik skorunda, topoloji kok seciminde kullanilir.
            "sinyal_disi": {
                "is_kritikligi": KRITIKLIK_PUAN.get(env.get("is_kritikligi", ""), 0.5),
                "topoloji": round(KATMAN_PUAN[katman]
                                  * (0.5 + 0.5 * min(len(yayilim) / 8.0, 1.0)), 4),
            },
        }

    dagilim = Counter(round(a["skor"]["ham"], 1) for a in alarmlar)
    print(f"  Etiket alani eklendi : {len(alarmlar)} alarm")
    print(f"  Ham skor dagilimi    :")
    for k in sorted(dagilim):
        print(f"      {k:.1f}  {'#' * (dagilim[k] // 12):40s} {dagilim[k]:5d}")
    return profil


# =========================================================================== #
# ASAMA 4 — GRUPLA
# =========================================================================== #

def asama4_grupla(alarmlar: list[dict]) -> list[dict]:
    """Tekrar zincirleri kurar ve sinyal skorunu zincir konumuna gore sonumlendirir.

    Zincir anahtarina HEDEF SERVIS dahildir: ayni host+tip farkli hedeflere alarm
    uretiyorsa ayri zincirlere bolunur. Aksi halde uc ayri olayin kaniti tek
    zincirde eriyip gider.
    """
    bolum("ASAMA 4 — GRUPLA (tekrar zincirleri)")
    zincirler: dict[tuple, list[dict]] = defaultdict(list)
    for a in alarmlar:
        zincirler[(a["host"], a["service"], a["alarm_type"],
                   a["etiket"]["hedef_servis"])].append(a)

    gruplar: list[dict] = []
    sayac = 0
    for anahtar, grup in zincirler.items():
        grup.sort(key=zaman)
        parca: list[dict] = []
        onceki: datetime | None = None
        parcalar: list[list[dict]] = []
        for a in grup:
            t = zaman(a)
            if onceki and (t - onceki).total_seconds() > ZINCIR_BOSLUK_SN:
                parcalar.append(parca)
                parca = []
            parca.append(a)
            onceki = t
        parcalar.append(parca)

        for p in parcalar:
            sayac += 1
            gid = f"GRP-{sayac:05d}"
            kaynaklar = sorted({x["source_system"] for x in p})
            cok_kaynak_carpani = 1.0 + 0.05 * (len(kaynaklar) - 1)
            for i, a in enumerate(p):
                sonum = 1.0 / (1.0 + 0.15 * i)
                a["grup"] = {
                    "grup_id": gid,
                    "anahtar": "|".join(str(x) for x in anahtar),
                    "boyut": len(p),
                    "sira": i + 1,
                    "temsilci_mi": i == 0,
                    "ilk": p[0]["timestamp"],
                    "son": p[-1]["timestamp"],
                    "sure_sn": int((zaman(p[-1]) - zaman(p[0])).total_seconds()),
                    "kaynak_sistemler": kaynaklar,
                }
                a["skor"]["tekrar_sonumu"] = round(sonum, 3)
                a["skor"]["cok_kaynak_carpani"] = round(cok_kaynak_carpani, 3)
                a["skor"]["sinyal"] = round(
                    min(a["skor"]["ham"] * sonum * cok_kaynak_carpani, 1.0), 4)
            gruplar.append({"grup_id": gid, "anahtar": anahtar, "uyeler": p})

    temsilci = sum(1 for a in alarmlar if a["grup"]["temsilci_mi"])
    boyut = Counter(g["uyeler"].__len__() for g in gruplar)
    print(f"  Zincir sayisi        : {len(gruplar)}")
    print(f"  Temsilci kayit       : {temsilci}  (ekran gurultusu "
          f"-%{(1 - temsilci / len(alarmlar)) * 100:.0f}, veri kaybi yok)")
    print(f"  En uzun zincir       : {max(boyut)} alarm")
    yuksek = sum(1 for a in alarmlar if a["skor"]["sinyal"] >= GURULTU_ESIGI)
    print(f"  Sinyal skoru >= {GURULTU_ESIGI} : {yuksek} alarm "
          f"(%{yuksek / len(alarmlar) * 100:.1f})")
    return gruplar


# =========================================================================== #
# ASAMA 5 — KORELE
# =========================================================================== #

def cekirdekleri_bul(alarmlar: list[dict]) -> list[dict]:
    nedenler = sorted(
        (a for a in alarmlar
         if a["etiket"]["nedensellik"] == "neden" and a["skor"]["sinyal"] >= CEKIRDEK_ESIGI),
        key=zaman)
    if not nedenler:
        return []

    zincirler: dict[tuple, list[dict]] = defaultdict(list)
    for a in nedenler:
        zincirler[(TIP_AILESI.get(a["alarm_type"], a["alarm_type"]), a["service"])].append(a)

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

    parcalar.sort(key=lambda p: zaman(p["alarmlar"][0]))
    cekirdekler: list[dict] = []
    for p in parcalar:
        bas, son = zaman(p["alarmlar"][0]), zaman(p["alarmlar"][-1])
        for c in cekirdekler:
            if c["aile"] == p["aile"] and bas <= c["son"] + timedelta(seconds=CEKIRDEK_BOSLUK_SN):
                c["alarmlar"].extend(p["alarmlar"])
                c["servisler"].add(p["servis"])
                c["bas"], c["son"] = min(c["bas"], bas), max(c["son"], son)
                break
        else:
            cekirdekler.append({"aile": p["aile"], "servisler": {p["servis"]},
                                "alarmlar": list(p["alarmlar"]), "bas": bas, "son": son})

    for c in cekirdekler:
        c["alarmlar"].sort(key=zaman)
    return [c for c in cekirdekler if len(c["alarmlar"]) >= ASGARI_CEKIRDEK_ALARM]


def kok_sec(c: dict, grafik: Grafik) -> list[dict]:
    adaylar = []
    for servis in sorted(c["servisler"]):
        ait = [a for a in c["alarmlar"] if a["service"] == servis]
        if not ait:
            continue
        p_neden = 1.0 if all(a["alarm_type"] in NEDEN_TIPLERI for a in ait) else 0.5
        p_katman = KATMAN_PUAN[grafik.katman(servis)]
        gecikme = (zaman(ait[0]) - c["bas"]).total_seconds()
        p_zaman = max(0.0, 1.0 - gecikme / 600.0)
        p_sinyal = sum(a["skor"]["sinyal"] for a in ait) / len(ait)
        skor = 0.35 * p_neden + 0.25 * p_katman + 0.20 * p_zaman + 0.20 * p_sinyal
        adaylar.append({
            "servis": servis, "skor": round(skor, 3), "alarm_sayisi": len(ait),
            "ilk_alarm": ait[0]["timestamp"], "gecikme_sn": int(gecikme),
            "grafik_katmani": grafik.katman(servis),
            "yayilim_alani": len(grafik.yayilim_alani(servis)),
            "ort_sinyal_skoru": round(p_sinyal, 3),
            "kirilim": {"nedensel_tip": round(0.35 * p_neden, 3),
                        "grafik_katmani": round(0.25 * p_katman, 3),
                        "zamansal_oncelik": round(0.20 * p_zaman, 3),
                        "sinyal_skoru": round(0.20 * p_sinyal, 3)},
        })
    adaylar.sort(key=lambda x: (-x["skor"], x["ilk_alarm"]))
    return adaylar


def topolojik_kok(c: dict) -> dict | None:
    """Ag olaylarinda ortak kabin arar: bagimsiz servisler ayni anda ve ayni
    kabinde baglanti kaybediyorsa kok servis degil altyapidir."""
    if c["aile"] != "ag":
        return None
    yer = Counter((a["etiket"]["veri_merkezi"], a["etiket"]["kabin"]) for a in c["alarmlar"])
    (dc, kabin), n = yer.most_common(1)[0]
    pay = n / sum(yer.values())
    if pay >= 0.40 and len(c["servisler"]) >= 3:
        return {"dc": dc, "kabin": kabin, "pay": round(pay, 3),
                "dagilim": {f"{k[0]}/{k[1]}": v for k, v in yer.most_common()}}
    return None


GEREKCE_TANIMLARI = {
    "BAKIM_SINIFI":
        "Alarm tipi bakim/bilgi sinifinda. Bu tipler gozlem penceresine duzgun "
        "yayilir, tum servislere dokunur ve dusuk siddetlidir; bir olayin parcasi "
        "degil, surekli akan arka plandir.",
    "DUSUK_SINYAL_SKORU":
        "Alarmin sinyal skoru gurultu esiginin altinda kaldi. Tipi nedensel degil, "
        "dustugu anda kendi tipinin taban oranina gore bir yogunlasma yok ve "
        "siddeti dusuk.",
    "PENCERE_DISI":
        "Alarm hicbir olayin zaman penceresine dusmuyor. Tespit edilen olaylarin "
        "hicbiriyle zamansal ortusmesi yok.",
    "OLAYA_BAGLANAMADI":
        "Alarm bir olayin zaman penceresine dusuyor ancak topolojik veya "
        "bagimlilik baglantisi kurulamadi; ayni anda olmasi tek basina "
        "nedensellik kanitlamaz.",
}


def gerekce_uret(a: dict, profil: dict) -> None:
    """Gurultu kararini sayisal dayanagiyla birlikte insan okunur hale getirir.

    Denetim gorunumunun cekirdegi. "Neden elendi?" sorusu tek kelimelik bir kodla
    degil, karari ureten esik/skor karsilastirmasiyla cevaplanmalidir; aksi halde
    eleme dogrulanabilir olmaz.
    """
    kor = a["korelasyon"]
    tip = a["alarm_type"]
    p = profil[tip]
    skor = a["skor"]
    kosullar, ceza = kor.pop("_kosullar", None) or ([], [])

    if a["etiket"]["nedensellik"] == "bakim":
        kod = "BAKIM_SINIFI"
        ozet = (f"'{tip}' bakim sinifinda: {p['sayi']} alarmi 120 dakikaya duzgun "
                f"yayilmis (CV {p['cv']}), {p['servis_yayilimi']}/27 servise dokunmus, "
                f"ortalama siddet {p['ort_severity']}. Bu profil arka plan "
                f"gurultusunun imzasidir.")
    elif skor["sinyal"] < GURULTU_ESIGI:
        kod = "DUSUK_SINYAL_SKORU"
        ozet = (f"Sinyal skoru {skor['sinyal']}, gurultu esigi {GURULTU_ESIGI}. "
                f"Esigin {round(GURULTU_ESIGI - skor['sinyal'], 3)} altinda.")
    elif not kosullar:
        kod = "PENCERE_DISI"
        ozet = (f"{a['timestamp'][11:]} aninda acik bir olay penceresi yok; "
                f"tespit edilen olaylarin hicbiriyle zamansal ortusme bulunmuyor.")
    else:
        kod = "OLAYA_BAGLANAMADI"
        eksik = [k[0] for k in kosullar if not k[1]]
        ozet = (f"En yakin olay {kor['en_yakin_olay']}: atama skoru "
                f"{kor['atama_skoru']} < esik {ATAMA_ESIGI}. "
                f"Karsilanmayan kosullar: {', '.join(eksik)}.")

    # Skorun hangi bileseninin eksik kaldigi
    azami = {"nedensellik": AGIRLIK["nedensellik"], "nadirlik": AGIRLIK["nadirlik"],
             "siddet": AGIRLIK["siddet"]}
    eksikler = sorted(((azami[b] - v, b, v) for b, v in skor["kirilim"].items()),
                      reverse=True)
    fark, en_eksik_ad, en_eksik_v = eksikler[0]

    kor["gerekce_kodu"] = kod
    kor["gerekce"] = ozet
    kor["gerekce_tanimi"] = GEREKCE_TANIMLARI[kod]
    kor["sinyal_skoru_detayi"] = {
        "deger": skor["sinyal"],
        "gurultu_esigi": GURULTU_ESIGI,
        "esigi_gecti_mi": skor["sinyal"] >= GURULTU_ESIGI,
        "kirilim": skor["kirilim"],
        "en_zayif_bilesen": f"{en_eksik_ad} = {en_eksik_v} "
                            f"(azami {azami[en_eksik_ad]}, {round(fark, 3)} eksik)",
        "tekrar_sonumu": skor.get("tekrar_sonumu"),
        "zincir_konumu": f"{a['grup']['sira']}/{a['grup']['boyut']}",
    }
    kor["tip_profili"] = {
        "tip": tip, "nedensellik_sinifi": a["etiket"]["nedensellik"],
        "toplam_alarm": p["sayi"], "zamansal_cv": p["cv"],
        "servis_yayilimi": f"{p['servis_yayilimi']}/27",
        "ortalama_severity": p["ort_severity"],
    }
    if kosullar:
        kor["olay_yakinligi"] = {
            "en_yakin_olay": kor["en_yakin_olay"],
            "atama_skoru": kor["atama_skoru"],
            "atama_esigi": ATAMA_ESIGI,
            "eksik_puan": round(ATAMA_ESIGI - kor["atama_skoru"], 3),
            "kosullar": [{"ad": ad, "saglandi": s, "puan": p_ if s else 0.0,
                          "azami_puan": p_, "aciklama": acik}
                         for ad, s, p_, acik in kosullar],
            "cezalar": ceza,
            "karari_degistirecek": next(
                (f"'{ad}' kosulu saglansaydi (+{p_}) esik gecilirdi"
                 for ad, s, p_, _ in kosullar
                 if not s and kor["atama_skoru"] + p_ >= ATAMA_ESIGI),
                "Tek bir kosul degisikligi esigi gectirmezdi"),
        }


def asama5_korele(alarmlar: list[dict], grafik: Grafik, paylasilan: bool,
                  profil_ref: dict) -> list[dict]:
    bolum("ASAMA 5 — KORELE")
    cekirdekler = cekirdekleri_bul(alarmlar)
    print(f"  Cekirdek (sinyal >= {CEKIRDEK_ESIGI}) : {len(cekirdekler)}")

    olaylar: list[dict] = []
    for i, c in enumerate(sorted(cekirdekler, key=lambda x: x["bas"]), start=1):
        topo = topolojik_kok(c)
        adaylar = kok_sec(c, grafik)
        kok = None if topo else adaylar[0]["servis"]
        kapsam = set(c["servisler"])
        if kok:
            kapsam |= {kok}
            kapsam |= (grafik.paylasilan_kaynak_alani(kok) if paylasilan
                       else grafik.yayilim_alani(kok))
        olaylar.append({"id": f"OLAY-{i:03d}", "cekirdek": c, "kok_servis": kok,
                        "topoloji": topo, "adaylar": adaylar, "kapsam": kapsam,
                        "uyeler": list(c["alarmlar"]),
                        "_cekirdek": {a["alarm_id"] for a in c["alarmlar"]}})
        yer = f"{topo['dc']}/{topo['kabin']}" if topo else kok
        print(f"    OLAY-{i:03d} {c['bas'].strftime('%H:%M')}-{c['son'].strftime('%H:%M')} "
              f"aile={c['aile']:11s} kok={str(yer):22s} cekirdek={len(c['alarmlar']):3d}")

    for a in alarmlar:
        if any(a["alarm_id"] in o["_cekirdek"] for o in olaylar):
            a["korelasyon"] = {
                "karar": "CEKIRDEK", "rol": "cekirdek",
                "olay": next(o["id"] for o in olaylar if a["alarm_id"] in o["_cekirdek"]),
                "atama_skoru": 1.0,
                "gerekce": f"Kok sinyali: nedensel tip '{a['alarm_type']}' ve sinyal "
                           f"skoru {a['skor']['sinyal']} >= cekirdek esigi {CEKIRDEK_ESIGI}",
            }
            continue
        t = zaman(a)
        en_iyi, en_skor, en_kosul = None, 0.0, None
        for o in olaylar:
            c = o["cekirdek"]
            if not (c["bas"] - timedelta(seconds=MARJ_GERI_SN) <= t
                    <= c["son"] + timedelta(seconds=MARJ_ILERI_SN)):
                continue
            hedef = a["etiket"]["hedef_servis"]
            # Her kosul: (ad, saglandi_mi, puan, aciklama). Saglanmayanlar da
            # kaydedilir; denetim gorunumunde "ne eksikti" sorusu bu listeden
            # cevaplanir.
            kosullar = [
                ("zaman_penceresi", True, 0.30,
                 f"Alarm, olayin {c['bas'].strftime('%H:%M:%S')}-"
                 f"{c['son'].strftime('%H:%M:%S')} cekirdek penceresine "
                 f"(-{MARJ_GERI_SN}sn/+{MARJ_ILERI_SN}sn marjla) dusuyor"),
                ("kok_yayilim_alaninda", a["service"] in o["kapsam"], 0.30,
                 f"Servis '{a['service']}' olayin etki alaninda"
                 + ("" if a["service"] in o["kapsam"]
                    else f" DEGIL (alan: {sorted(o['kapsam'])[:5]}...)")),
                ("hedef_eslesmesi",
                 bool(hedef) and (hedef in o["kapsam"] or hedef == o["kok_servis"]), 0.25,
                 (f"Iliskisel alarmin hedefi '{hedef}' olay zincirinde"
                  if hedef else "Alarm iliskisel degil, hedef servis icermiyor")),
                ("ayni_kabin",
                 bool(o["topoloji"]) and (a["etiket"]["veri_merkezi"],
                                          a["etiket"]["kabin"]) == (o["topoloji"]["dc"],
                                                                    o["topoloji"]["kabin"]),
                 0.30,
                 (f"Host {a['etiket']['veri_merkezi']}/{a['etiket']['kabin']} kabininde, "
                  f"olayin koku {o['topoloji']['dc']}/{o['topoloji']['kabin']}"
                  if o["topoloji"] else "Olayin topolojik koku yok, kabin kosulu gecersiz")),
                ("semptom_tipi", a["etiket"]["nedensellik"] == "semptom", 0.10,
                 f"Nedensellik sinifi '{a['etiket']['nedensellik']}'"),
            ]
            s = sum(p for _, saglandi, p, _ in kosullar if saglandi)
            ceza = []
            if a["skor"]["sinyal"] < GURULTU_ESIGI:
                s -= 0.25
                ceza.append({
                    "ad": "dusuk_sinyal_cezasi", "puan": -0.25,
                    "aciklama": f"Sinyal skoru {a['skor']['sinyal']} < "
                                f"gurultu esigi {GURULTU_ESIGI}"})
            if s > en_skor:
                en_iyi, en_skor, en_kosul = o, s, (kosullar, ceza)

        if en_iyi and en_skor >= ATAMA_ESIGI:
            en_iyi["uyeler"].append(a)
            a["korelasyon"] = {
                "karar": "OLAYA_ATANDI", "olay": en_iyi["id"], "rol": "turev",
                "atama_skoru": round(en_skor, 3), "atama_esigi": ATAMA_ESIGI,
                "saglanan_kosullar": [k[0] for k in en_kosul[0] if k[1]],
            }
        else:
            a["korelasyon"] = {
                "karar": "GURULTU", "olay": None, "rol": "gurultu",
                "atama_skoru": round(en_skor, 3), "atama_esigi": ATAMA_ESIGI,
                "en_yakin_olay": en_iyi["id"] if en_iyi else None,
                "_kosullar": en_kosul,
            }

    for a in alarmlar:
        if a["korelasyon"]["karar"] == "GURULTU":
            gerekce_uret(a, profil_ref)

    atanan = sum(1 for a in alarmlar if a["korelasyon"]["olay"])
    elenen = Counter(a["korelasyon"]["gerekce_kodu"]
                     for a in alarmlar if not a["korelasyon"]["olay"])
    print(f"  Atanan   : {atanan} / {len(alarmlar)} (%{atanan / len(alarmlar) * 100:.1f})")
    print(f"  Elenen   : {len(alarmlar) - atanan} "
          f"(%{(len(alarmlar) - atanan) / len(alarmlar) * 100:.1f})")
    for k, v in elenen.most_common():
        print(f"      {k:26s} {v:5d}")
    return olaylar


# =========================================================================== #
# ASAMA 6 — KARTLASTIR
# =========================================================================== #

AKSIYON = {
    "ag": ("{yer} kabinindeki switch port durumunu ve etkilenen hostlarin arayuz "
           "link durumunu kontrol et", "nobetci-network"),
    "disk_full": ("{s} uzerinde disk alanini bosalt/genislet; tablespace otomatik "
                  "buyumesini dogrula", "nobetci-dba"),
    "ext_unreach": ("{s} saglayicisiyla iletisime gec; devre kesici devreye alarak "
                    "cagrilari kuyrukla", "nobetci-entegrasyon"),
    "ext_slow": ("{s} saglayicisiyla iletisime gec; timeout ve retry politikasini "
                 "gozden gecir", "nobetci-entegrasyon"),
    "oom_risk": ("{s} ornegini kontrollu yeniden baslat; heap dump alarak sizintiyi "
                 "analiz et", "nobetci-uygulama"),
    "gc_pressure": ("{s} heap kullanimini izle; oom_risk'e donusmeden GC parametrelerini "
                    "gozden gecir", "nobetci-uygulama"),
    "batch_overlap": ("Cakisan toplu is pencerelerini ayir; {s} zamanlamasini erteleyerek "
                      "es zamanli DB yukunu dusur", "nobetci-batch"),
}


def oncelik_skoru(uyeler: list[dict], kapsam: set[str], envanter: dict) -> dict:
    """Kartin mudahale onceligi. Nobetci muhendis hangi karta once bakmali?"""
    p_sev = max(a["severity"] for a in uyeler) / 5.0
    kritik = {a["service"] for a in uyeler
              if a["etiket"]["is_kritikligi"] == "kritik"}
    p_kritik = min(len(kritik) / 5.0, 1.0)
    p_yayilim = min(len(kapsam) / 8.0, 1.0)
    p_hacim = min(len(uyeler) / 300.0, 1.0)
    sure_dk = (zaman(uyeler[-1]) - zaman(uyeler[0])).total_seconds() / 60
    p_sure = min(sure_dk / 45.0, 1.0)
    skor = 0.30 * p_sev + 0.25 * p_kritik + 0.20 * p_yayilim + 0.15 * p_hacim + 0.10 * p_sure
    return {
        "skor": round(skor, 3),
        "sinif": "P1" if skor >= 0.75 else "P2" if skor >= 0.55 else "P3",
        "kirilim": {"severity": round(0.30 * p_sev, 3),
                    "kritik_servis": round(0.25 * p_kritik, 3),
                    "yayilim": round(0.20 * p_yayilim, 3),
                    "hacim": round(0.15 * p_hacim, 3),
                    "sureklilik": round(0.10 * p_sure, 3)},
        "kritik_servisler": sorted(kritik),
    }


def asama6_kartlastir(olaylar: list[dict], envanter: dict) -> list[dict]:
    bolum("ASAMA 6 — KARTLASTIR")
    kartlar = []
    for o in olaylar:
        uyeler = sorted(o["uyeler"], key=zaman)
        topo, kok, adaylar = o["topoloji"], o["kok_servis"], o["adaylar"]
        kok_tip = Counter(a["alarm_type"] for a in o["cekirdek"]["alarmlar"]).most_common(1)[0][0]

        if topo:
            hipotez = (f"{topo['dc']}/{topo['kabin']} kabininde ag katmani arizasi: "
                       f"{len(o['cekirdek']['servisler'])} bagimsiz servis es zamanli "
                       f"baglanti kaybi bildirdi")
            gerekce = (f"Cekirdek alarmlarinin %{topo['pay'] * 100:.0f}'i tek kabinde "
                       f"({topo['dc']}/{topo['kabin']}) toplandi. Birbirine bagimli olmayan "
                       f"{len(o['cekirdek']['servisler'])} servis ayni anda etkilendi; "
                       f"ortak neden servis katmaninda olamaz.")
            sablon, sahip = AKSIYON["ag"]
            aksiyon = sablon.format(yer=f"{topo['dc']}/{topo['kabin']}")
        else:
            k = adaylar[0]
            hipotez = f"{kok} uzerinde {kok_tip}"
            gerekce = (f"{kok} secildi (skor {k['skor']}): nedensel tip "
                       f"+{k['kirilim']['nedensel_tip']}, grafik katmani "
                       f"'{k['grafik_katmani']}' +{k['kirilim']['grafik_katmani']}, "
                       f"zamansal oncelik +{k['kirilim']['zamansal_oncelik']}, "
                       f"ortalama sinyal skoru {k['ort_sinyal_skoru']} "
                       f"+{k['kirilim']['sinyal_skoru']}. "
                       f"Yayilim alani {k['yayilim_alani']} servis.")
            sablon, sahip = AKSIYON.get(kok_tip, ("{s} uzerinde ilgili bileseni incele",
                                                  "nobetci-muhendis"))
            aksiyon = sablon.format(s=kok)

        karsi = [{"alternatif": f"{x['servis']} ({x['grafik_katmani']} katmani)",
                  "neden_daha_zayif": (f"skor {x['skor']} < {adaylar[0]['skor']}; ilk alarmi "
                                       f"{x['gecikme_sn']} sn sonra geldi")}
                 for x in adaylar[1:3]]
        if topo:
            karsi.append({
                "alternatif": "Tek servis kaynakli ariza",
                "neden_daha_zayif": (f"Alarm dagilimi {topo['dagilim']}; tek servis "
                                     f"arizasi bagimsiz servisleri es zamanli etkileyemez")})

        oncelik = oncelik_skoru(uyeler, o["kapsam"], envanter)
        servisler = Counter(a["service"] for a in uyeler)

        kartlar.append({
            "id": o["id"], "durum": "ACIK", "oncelik": oncelik,
            "kok_neden_hipotezi": hipotez, "kok_servis": kok,
            "kok_topoloji": f"{topo['dc']}/{topo['kabin']}" if topo else None,
            "gerekce": gerekce, "karsi_olasiliklar": karsi,
            "alarm_sayisi": len(uyeler),
            "zaman_araligi": {
                "baslangic": uyeler[0]["timestamp"], "bitis": uyeler[-1]["timestamp"],
                "sure_dk": round((zaman(uyeler[-1]) - zaman(uyeler[0])).total_seconds() / 60, 1)},
            "etkilenen_servisler": [{"servis": s, "alarm": n} for s, n in servisler.most_common()],
            "etkilenen_servis_sayisi": len(servisler),
            "en_yuksek_severity": max(a["severity"] for a in uyeler),
            "alarm_tipi_dagilimi": dict(Counter(a["alarm_type"] for a in uyeler).most_common()),
            "aksiyon": {"id": f"ACT-{o['id'].split('-')[1]}", "aciklama": aksiyon,
                        "sahip": sahip, "durum": "ACIK",
                        "olusturma": uyeler[0]["timestamp"], "kapanis": None},
            "kok_aday_siralamasi": adaylar[:4],
            "kanit_alarmlari": [
                {"alarm_id": a["alarm_id"], "zaman": a["timestamp"][11:],
                 "sev": a["severity"], "servis": a["service"], "tip": a["alarm_type"],
                 "sinyal_skoru": a["skor"]["sinyal"], "mesaj": a["message"]}
                for a in o["cekirdek"]["alarmlar"][:6]],
            "uye_alarm_idleri": [a["alarm_id"] for a in uyeler],
        })

    kartlar.sort(key=lambda k: -k["oncelik"]["skor"])
    print(f"  Kart sayisi : {len(kartlar)}")
    for k in kartlar:
        print(f"    {k['id']} [{k['oncelik']['sinif']}] skor={k['oncelik']['skor']:.3f} "
              f"{k['alarm_sayisi']:4d} alarm  {k['kok_neden_hipotezi'][:44]}")
    return kartlar


# =========================================================================== #

def kartlari_yaz(kartlar: list[dict], detay: bool) -> None:
    bolum("AKSIYON KARTLARI")
    for k in kartlar:
        o = k["oncelik"]
        print(f"\n{'-' * 78}")
        print(f"{k['id']}  [{k['durum']}]  ONCELIK {o['sinif']} ({o['skor']})"
              f"{' ' * 12}sev{k['en_yuksek_severity']}")
        print(f"{'-' * 78}")
        print(f"  KOK NEDEN      : {k['kok_neden_hipotezi']}")
        print(f"  GEREKCE        : {k['gerekce']}")
        for c in k["karsi_olasiliklar"][:2]:
            print(f"  KARSI OLASILIK : {c['alternatif']}")
            print(f"                   -> {c['neden_daha_zayif']}")
        print(f"  ZAMAN          : {k['zaman_araligi']['baslangic'][11:]} - "
              f"{k['zaman_araligi']['bitis'][11:]}  ({k['zaman_araligi']['sure_dk']} dk)")
        print(f"  ALARM          : {k['alarm_sayisi']}")
        print(f"  ETKILENEN      : {k['etkilenen_servis_sayisi']} servis — " +
              ", ".join(f"{s['servis']}({s['alarm']})" for s in k["etkilenen_servisler"][:6]))
        print(f"  ONCELIK KIRILIMI: " +
              " ".join(f"{a}={b}" for a, b in o["kirilim"].items()))
        a = k["aksiyon"]
        print(f"  >> {a['id']}      : {a['aciklama']}")
        print(f"                   sahip={a['sahip']}  durum={a['durum']}")
        if detay:
            print("  KANIT:")
            for e in k["kanit_alarmlari"]:
                print(f"    {e['zaman']} sev{e['sev']} skor{e['sinyal_skoru']:.2f} "
                      f"{e['servis']:20s} {e['tip']:13s} {e['mesaj'][:44]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Alarm firtinasi uctan uca boru hatti.")
    ap.add_argument("--girdi", type=Path, default=VARSAYILAN_GIRDI)
    ap.add_argument("--detay", action="store_true", help="Kanit dokumunu yaz.")
    ap.add_argument("--asama", type=int, default=6, choices=range(1, 7),
                    help="Yalnizca ilk N asamayi kosur.")
    ap.add_argument("--paylasilan-kaynak", action="store_true",
                    help="Yayilim alanina paylasilan kaynak sicramasini ekle (fazla "
                         "birlestirme riski tasir, varsayilan kapali).")
    args = ap.parse_args()

    if not args.girdi.exists():
        sys.exit(f"HATA: {args.girdi} bulunamadi.")
    CIKTI_DIZIN.mkdir(parents=True, exist_ok=True)

    print(f"S-A1 ALARM FIRTINASI — UCTAN UCA BORU HATTI")
    print(f"Girdi: {args.girdi.relative_to(KOK)}   LLM: kullanilmiyor (deterministik)")

    alarmlar, envanter, grafik = asama1_yukle(args.girdi)
    if args.asama < 2:
        return

    alarmlar, temizlik = asama2_temizle(alarmlar, envanter)
    (CIKTI_DIZIN / "02_temiz.json").write_text(
        json.dumps(alarmlar, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.asama < 3:
        return

    profil = asama3_etiketle(alarmlar, envanter, grafik)
    (CIKTI_DIZIN / "03_etiketli.json").write_text(
        json.dumps(alarmlar, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.asama < 4:
        return

    gruplar = asama4_grupla(alarmlar)
    (CIKTI_DIZIN / "04_gruplu.json").write_text(json.dumps(
        [{"grup_id": g["grup_id"], "anahtar": [str(x) for x in g["anahtar"]],
          "boyut": len(g["uyeler"]),
          "alarm_idler": [a["alarm_id"] for a in g["uyeler"]]} for g in gruplar],
        ensure_ascii=False, indent=2), encoding="utf-8")
    if args.asama < 5:
        return

    olaylar = asama5_korele(alarmlar, grafik, args.paylasilan_kaynak, profil)
    if args.asama < 6:
        return

    kartlar = asama6_kartlastir(olaylar, envanter)
    kartlari_yaz(kartlar, args.detay)

    atanan = sum(k["alarm_sayisi"] for k in kartlar)
    ozet = {
        "girdi": str(args.girdi.relative_to(KOK)),
        "llm_kullanildi": False,
        "paylasilan_kaynak_modu": args.paylasilan_kaynak,
        "alarm_sayisi": len(alarmlar),
        "tekrar_zinciri": len(gruplar),
        "kart_sayisi": len(kartlar),
        "atanan_alarm": atanan,
        "elenen_alarm": len(alarmlar) - atanan,
        "indirgeme_orani": round(len(kartlar) / len(alarmlar), 5),
        "temizlik": temizlik,
        "esikler": {
            "ZINCIR_BOSLUK_SN": ZINCIR_BOSLUK_SN, "GURULTU_ESIGI": GURULTU_ESIGI,
            "CEKIRDEK_ESIGI": CEKIRDEK_ESIGI, "CEKIRDEK_BOSLUK_SN": CEKIRDEK_BOSLUK_SN,
            "MARJ_GERI_SN": MARJ_GERI_SN, "MARJ_ILERI_SN": MARJ_ILERI_SN,
            "ATAMA_ESIGI": ATAMA_ESIGI,
        },
    }
    elenenler = [a for a in alarmlar if not a["korelasyon"]["olay"]]
    kod_ozeti = Counter(a["korelasyon"]["gerekce_kodu"] for a in elenenler)
    (CIKTI_DIZIN / "05_denetim.json").write_text(json.dumps({
        "ozet": ozet,
        "eleme_gerekce_kodlari": {
            kod: {"alarm_sayisi": kod_ozeti[kod], "tanim": GEREKCE_TANIMLARI[kod]}
            for kod in kod_ozeti},
        "esik_aciklamalari": {
            "GURULTU_ESIGI": f"{GURULTU_ESIGI} — sinyal skoru bunun altinda kalan alarm "
                             f"gurultu adayidir. Olculen dagilim: NEDEN sinifi min 0.816, "
                             f"BAKIM sinifi max 0.543 — iki sinif ortusmuyor.",
            "ATAMA_ESIGI": f"{ATAMA_ESIGI} — bir alarmin olaya turev olarak baglanmasi icin "
                           f"gereken asgari kosul skoru.",
            "agirliklar": AGIRLIK,
        },
        "tip_profilleri": {k: {x: y for x, y in v.items() if not x.startswith("_")}
                           for k, v in profil.items()},
        "elenen_alarmlar": [
            {"alarm_id": a["alarm_id"], "zaman": a["timestamp"][11:],
             "host": a["host"], "servis": a["service"], "tip": a["alarm_type"],
             "severity": a["severity"], "mesaj": a["message"],
             **{k: v for k, v in a["korelasyon"].items() if k != "rol"}}
            for a in elenenler],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (CIKTI_DIZIN / "06_kartlar.json").write_text(json.dumps(
        {"ozet": ozet, "kartlar": kartlar}, ensure_ascii=False, indent=2), encoding="utf-8")

    bolum("OZET")
    print(f"  {len(alarmlar)} alarm -> {len(gruplar)} tekrar zinciri -> {len(kartlar)} kart")
    print(f"  Indirgeme        : %{ozet['indirgeme_orani'] * 100:.2f}")
    print(f"  Atanan / elenen  : {atanan} / {len(alarmlar) - atanan}")
    print(f"  LLM              : kullanilmadi")
    for f in sorted(CIKTI_DIZIN.glob("*.json")):
        print(f"  yazildi: {f.relative_to(KOK)}")


if __name__ == "__main__":
    main()
