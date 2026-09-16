"""S-A1 Alarm Firtinasi — yerel web arayuzu.

Yalnizca Python standart kutuphanesini kullanir. Harici paket, derleme adimi
veya internet erisimi gerekmez; `python run.py gui` her ortamda calisir.

    python src/gui.py                 # http://127.0.0.1:8765
    python src/gui.py --port 9000 --acma   # tarayici acmadan

Arayuz:
  - Ham alarm JSON'u dosya secici ya da surukle-birak ile verilir
  - Her boru hatti asamasi icin bir sekme
  - Olay kartlari oncelik skoruna gore renklendirilir (durum paleti)
  - Elenen alarmlar icin denetim tablosu

Renkler `dataviz` referans paletinden alinmistir ve dogrulayicidan gecmistir:
kategorik cift #3987e5 / #d95926 koyu yuzeyde (#1a1a19) tum kontrolleri gecer
(CVD DeltaE 26.8, normal gorus 31.8, kontrast >= 3:1). Oncelik renkleri DURUM
paletindendir ve kural geregi hicbir yerde tek basina kullanilmaz — her zaman
bir simge ve "P1/P2/P3" etiketiyle birlikte gosterilir.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline  # noqa: E402

VARSAYILAN_GIRDI = KOK / "katilimci_paketi" / "alarms.json"

SAYFA = r"""<!DOCTYPE html>
<html lang="tr" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>S-A1 Alarm Fırtınası — Olay Konsolu</title>
<style>
:root{
  --plane:#0d0d0d; --surface:#1a1a19; --surface-2:#212120;
  --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926;
  --critical:#d03b3b; --serious:#ec835a; --warning:#fab219; --good:#0ca30c;
  --r:10px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--border);
  display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:var(--surface)}
h1{font-size:16px;margin:0;font-weight:650;letter-spacing:.01em}
h1 span{color:var(--muted);font-weight:400}
.spacer{flex:1}
.kaynak{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
input[type=text]{background:var(--plane);border:1px solid var(--border);color:var(--ink);
  padding:7px 10px;border-radius:8px;width:300px;font:inherit}
button{background:var(--s1);border:0;color:#fff;padding:8px 16px;border-radius:8px;
  font:inherit;font-weight:600;cursor:pointer}
button:hover{filter:brightness(1.12)} button:disabled{opacity:.45;cursor:default}
button.ikincil{background:transparent;border:1px solid var(--border);color:var(--ink-2)}
#drop{border:1.5px dashed var(--axis);border-radius:8px;padding:7px 14px;color:var(--muted);
  cursor:pointer;font-size:13px}
#drop.uzerinde{border-color:var(--s1);color:var(--s1)}

nav{display:flex;gap:2px;padding:0 24px;border-bottom:1px solid var(--border);
  background:var(--surface);overflow-x:auto}
nav button{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);
  padding:12px 15px;font-weight:550;white-space:nowrap;border-radius:0}
nav button:hover{color:var(--ink-2)}
nav button.aktif{color:var(--ink);border-bottom-color:var(--s1)}
nav button .rozet{background:var(--surface-2);color:var(--ink-2);border-radius:99px;
  padding:1px 7px;font-size:11px;margin-left:6px;font-variant-numeric:tabular-nums}

main{padding:24px;max-width:1400px}
.panel{display:none} .panel.aktif{display:block}
.baslik{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
  margin:0 0 12px;font-weight:600}

.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:26px}
.kpi .kutu{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 18px}
.kpi .etiket{font-size:12px;color:var(--muted);margin-bottom:6px}
.kpi .deger{font-size:28px;font-weight:600;line-height:1.1}
.kpi .alt{font-size:12px;color:var(--ink-2);margin-top:4px}

.kart{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:0;margin-bottom:14px;overflow:hidden;display:flex}
.kart .serit{width:4px;flex:none}
.kart .govde{padding:16px 18px;flex:1;min-width:0}
.kart .ust{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.kart .kimlik{font-weight:650;font-size:15px;font-variant-numeric:tabular-nums}
.rozet-oncelik{display:inline-flex;align-items:center;gap:5px;border-radius:99px;
  padding:2px 10px;font-size:12px;font-weight:650;border:1px solid}
.rozet{display:inline-block;border-radius:99px;padding:2px 9px;font-size:12px;
  background:var(--surface-2);color:var(--ink-2);border:1px solid var(--border);
  font-variant-numeric:tabular-nums}
.hipotez{font-size:15px;font-weight:550;margin:2px 0 8px}
.gerekce{color:var(--ink-2);font-size:13px;margin-bottom:10px}
.karsi{border-left:2px solid var(--axis);padding:4px 0 4px 11px;margin:8px 0;
  color:var(--muted);font-size:12.5px}
.karsi b{color:var(--ink-2);font-weight:600}
.olcum{display:flex;gap:22px;flex-wrap:wrap;margin:12px 0;font-size:13px}
.olcum div span{color:var(--muted);display:block;font-size:11.5px;margin-bottom:1px}
.olcum div b{font-weight:600;font-variant-numeric:tabular-nums}
.aksiyon{background:var(--surface-2);border-radius:8px;padding:11px 14px;margin-top:12px;
  display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}
.aksiyon .kod{font-weight:650;font-variant-numeric:tabular-nums;color:var(--s1)}
.aksiyon .metin{flex:1;min-width:220px;font-size:13px}
.aksiyon .meta{font-size:12px;color:var(--muted)}
.pill-durum{border:1px solid var(--warning);color:var(--warning);border-radius:99px;
  padding:1px 9px;font-size:11.5px;font-weight:600}

table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:11.5px;
  text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;
  border-bottom:1px solid var(--axis);position:sticky;top:0;background:var(--surface)}
td{padding:7px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
td.n{font-variant-numeric:tabular-nums;text-align:right}
tbody tr:hover{background:var(--surface-2)}
.tablo-sar{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  overflow:auto;max-height:620px}

.cubuk{display:flex;align-items:flex-end;gap:2px;height:190px;padding:0 2px}
.cubuk .sut{flex:1;position:relative;border-radius:4px 4px 0 0;min-height:2px;cursor:pointer}
.cubuk .sut:hover{outline:2px solid var(--ink);outline-offset:1px}
.eksen{display:flex;gap:2px;padding:6px 2px 0;border-top:1px solid var(--axis);
  font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.eksen div{flex:1;text-align:center}
.gosterge{display:flex;gap:16px;font-size:12.5px;color:var(--ink-2);margin:0 0 12px}
.gosterge i{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:6px}
#ipucu{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);
  border:1px solid var(--axis);border-radius:8px;padding:8px 11px;font-size:12.5px;
  display:none;z-index:99;box-shadow:0 6px 22px rgba(0,0,0,.5)}

.kutu{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:18px;margin-bottom:16px}
.ikili{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
.satir{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--grid);font-size:13px}
.satir:last-child{border:0}
.satir span{color:var(--ink-2)} .satir b{font-variant-numeric:tabular-nums;font-weight:600}
code{background:var(--surface-2);padding:1px 6px;border-radius:5px;font-size:12px;color:var(--ink-2)}
.bos{color:var(--muted);padding:40px;text-align:center}
.hata{border:1px solid var(--critical);color:var(--critical);border-radius:8px;padding:12px 14px;margin-bottom:16px}
</style>
</head>
<body>
<header>
  <h1>S-A1 Alarm Fırtınası <span>· Olay Konsolu</span></h1>
  <div class="spacer"></div>
  <div class="kaynak">
    <input type="text" id="yol" placeholder="alarms.json yolu">
    <label id="drop">JSON seç / sürükle<input type="file" id="dosya" accept=".json" hidden></label>
    <label style="font-size:12.5px;color:var(--muted);display:flex;gap:6px;align-items:center">
      <input type="checkbox" id="paylasilan"> paylaşılan kaynak</label>
    <button id="calistir">Çalıştır</button>
  </div>
</header>

<nav id="sekmeler"></nav>
<main id="icerik"><div class="bos">Çalıştır'a basın veya bir alarm JSON dosyası bırakın.</div></main>
<div id="ipucu"></div>

<script>
const FAZLAR=[["ozet","Özet"],["f1","1 · Yükle"],["f2","2 · Temizle"],["f3","3 · Etiketle"],
              ["f4","4 · Grupla"],["f5","5 · Korele"],["f6","6 · Kartlar"]];
const DURUM={P1:{renk:"var(--critical)",simge:"◆",ad:"P1 Kritik"},
             P2:{renk:"var(--serious)", simge:"▲",ad:"P2 Yüksek"},
             P3:{renk:"var(--warning)", simge:"●",ad:"P3 Orta"}};
let VERI=null, aktif="ozet";
const $=s=>document.querySelector(s), esc=s=>String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]));
const say=n=>Number(n).toLocaleString("tr-TR");

function sekmeleriCiz(){
  $("#sekmeler").innerHTML=FAZLAR.map(([k,ad])=>{
    let r="";
    if(VERI){const m={ozet:"",f1:VERI.asama1_yukle.alarm,f2:VERI.ozet.alarm_sayisi,
      f3:Object.keys(VERI.asama3_etiketle.tip_profilleri).length,
      f4:VERI.asama4_grupla.zincir_sayisi,f5:VERI.asama5_korele.elenen,
      f6:VERI.asama6_kartlar.length}[k]; if(m!=="")r=`<span class="rozet">${say(m)}</span>`;}
    return `<button data-k="${k}" class="${k===aktif?"aktif":""}">${ad}${r}</button>`;}).join("");
  $("#sekmeler").querySelectorAll("button").forEach(b=>b.onclick=()=>{aktif=b.dataset.k;sekmeleriCiz();ciz();});
}

function kpi(liste){return `<div class="kpi">${liste.map(([e,d,a])=>
  `<div class="kutu"><div class="etiket">${e}</div><div class="deger">${d}</div>
   ${a?`<div class="alt">${a}</div>`:""}</div>`).join("")}</div>`;}

function histogram(veri,esik){
  // Tek dagilim, iki kimlik: esigin altinda / ustunde. Kategorik slot 1 ve 2.
  const anah=Object.keys(veri).sort((a,b)=>a-b), mx=Math.max(...Object.values(veri));
  return `<div class="gosterge">
      <span><i style="background:var(--s2)"></i>Eşik altı (gürültü adayı)</span>
      <span><i style="background:var(--s1)"></i>Eşik üstü (sinyal)</span>
      <span style="color:var(--muted)">Gürültü eşiği = ${esik}</span></div>
    <div class="cubuk">${anah.map(k=>{
      const v=veri[k], ust=parseFloat(k)>=esik;
      return `<div class="sut" style="height:${Math.max(v/mx*100,1)}%;
        background:${ust?"var(--s1)":"var(--s2)"}"
        data-ip="Skor aralığı ${k} — ${say(v)} alarm (${ust?"sinyal":"gürültü adayı"})"></div>`;
    }).join("")}</div>
    <div class="eksen">${anah.map(k=>`<div>${k}</div>`).join("")}</div>`;
}

function kartCiz(k){
  const d=DURUM[k.oncelik.sinif];
  return `<div class="kart"><div class="serit" style="background:${d.renk}"></div><div class="govde">
    <div class="ust">
      <span class="kimlik">${k.id}</span>
      <span class="rozet-oncelik" style="color:${d.renk};border-color:${d.renk}">${d.simge} ${d.ad} · ${k.oncelik.skor}</span>
      <span class="rozet">sev ${k.en_yuksek_severity}</span>
      <span class="rozet">${say(k.alarm_sayisi)} alarm</span>
      <span class="rozet">${k.etkilenen_servis_sayisi} servis</span>
      <span class="pill-durum">${k.durum}</span>
    </div>
    <div class="hipotez">${esc(k.kok_neden_hipotezi)}</div>
    <div class="gerekce">${esc(k.gerekce)}</div>
    ${k.karsi_olasiliklar.slice(0,2).map(c=>
      `<div class="karsi"><b>Karşı olasılık:</b> ${esc(c.alternatif)} — ${esc(c.neden_daha_zayif)}</div>`).join("")}
    <div class="olcum">
      <div><span>Zaman aralığı</span><b>${k.zaman_araligi.baslangic.slice(11)} – ${k.zaman_araligi.bitis.slice(11)}</b></div>
      <div><span>Süre</span><b>${k.zaman_araligi.sure_dk} dk</b></div>
      <div><span>Etkilenen servisler</span><b>${k.etkilenen_servisler.slice(0,5).map(s=>s.servis+"("+s.alarm+")").join(", ")}</b></div>
    </div>
    <div class="aksiyon">
      <span class="kod">${k.aksiyon.id}</span>
      <span class="metin">${esc(k.aksiyon.aciklama)}</span>
      <span class="meta">sahip <b style="color:var(--ink-2)">${k.aksiyon.sahip}</b> · durum <b style="color:var(--ink-2)">${k.aksiyon.durum}</b></span>
    </div>
  </div></div>`;
}

function ciz(){
  const c=$("#icerik"); if(!VERI){return;}
  const o=VERI.ozet;
  if(aktif==="ozet"){
    c.innerHTML=kpi([
      ["Ham alarm",say(o.ham_alarm),`${o.servis_sayisi} servis · ${o.host_sayisi} host`],
      ["Tekrar zinciri",say(o.tekrar_zinciri),"gruplama sonrası"],
      ["Olay kartı",say(o.kart_sayisi),`indirgeme %${(o.indirgeme_orani*100).toFixed(2)}`],
      ["Karta atanan",say(o.atanan_alarm),`%${(o.atanan_alarm/o.alarm_sayisi*100).toFixed(1)}`],
      ["Elenen (gürültü)",say(o.elenen_alarm),`%${(o.elenen_alarm/o.alarm_sayisi*100).toFixed(1)}`],
      ["LLM",o.llm_kullanildi?"evet":"hayır","deterministik"],
    ])+`<p class="baslik">Olay kartları</p>`+VERI.asama6_kartlar.map(kartCiz).join("");
  }
  else if(aktif==="f1"){const a=VERI.asama1_yukle;
    c.innerHTML=kpi([["Alarm",say(a.alarm)],["Host",a.host],
      ["Bağımlılık kenarı",a.bagimlilik_kenari,`${a.grafik_servisi} servis grafikte`],
      ["Pencere",o.pencere[0].slice(11,16)+"–"+o.pencere[1].slice(11,16)]])
      +`<div class="ikili">
        <div class="kutu"><p class="baslik">İzleme sistemi</p>${Object.entries(a.kaynak_sistemler)
          .map(([k,v])=>`<div class="satir"><span>${k}</span><b>${say(v)}</b></div>`).join("")}</div>
        <div class="kutu"><p class="baslik">Severity dağılımı</p>${Object.entries(a.severity_dagilimi)
          .map(([k,v])=>`<div class="satir"><span>sev ${k}</span><b>${say(v)}</b></div>`).join("")}</div></div>`;}
  else if(aktif==="f2"){const t=VERI.asama2_temizle, kb=t.kalite_bulgulari||{};
    c.innerHTML=kpi([["Tekrarlanan alarm_id",t.tekrarlanan_id],["Tam kayıt duplikesi",t.tam_duplike],
      ["Aynı sn+host+tip",t.cakisan_anahtar,`${t.cok_kaynakli_cakisma} tanesi çok kaynaklı (duplike değil)`],
      ["Düşürülen kayıt",t.dusurulen.length]])
      +`<div class="kutu"><p class="baslik">Kalite denetimi</p>${
        Object.keys(kb).length? Object.entries(kb).map(([k,v])=>
          `<div class="satir"><span>${k}</span><b>${v}</b></div>`).join("")
        : `<div class="satir"><span>Zorunlu alanlar, değer aralıkları, envanter tutarlılığı</span>
           <b style="color:var(--good)">◆ bulgu yok</b></div>`}</div>`;}
  else if(aktif==="f3"){const e=VERI.asama3_etiketle, es=VERI.esikler;
    c.innerHTML=`<div class="kutu"><p class="baslik">Sinyal skoru dağılımı</p>
        ${histogram(e.skor_histogrami,es.GURULTU_ESIGI)}</div>
      <div class="ikili">
        <div class="kutu"><p class="baslik">Nedensellik sınıfı</p>${Object.entries(e.sinif_ozeti)
          .map(([k,v])=>`<div class="satir"><span>${k}</span><b>${say(v.alarm)} · ort ${v.ort_skor}</b></div>`).join("")}</div>
        <div class="kutu"><p class="baslik">Skor ağırlıkları</p>${Object.entries(es.AGIRLIK)
          .map(([k,v])=>`<div class="satir"><span>${k}</span><b>${v}</b></div>`).join("")}
          <div class="satir"><span>gürültü eşiği</span><b>${es.GURULTU_ESIGI}</b></div>
          <div class="satir"><span>çekirdek eşiği</span><b>${es.CEKIRDEK_ESIGI}</b></div></div></div>
      <div class="kutu"><p class="baslik">Alarm tipi profilleri</p><div class="tablo-sar"><table>
        <thead><tr><th>Tip</th><th>Sınıf</th><th class="n">Adet</th><th class="n">CV</th>
        <th class="n">Servis</th><th class="n">Ort. sev</th></tr></thead><tbody>${
        Object.entries(e.tip_profilleri).sort((a,b)=>b[1].cv-a[1].cv).map(([t,p])=>
        `<tr><td><code>${t}</code></td><td>${p.nedensellik}</td><td class="n">${p.sayi}</td>
         <td class="n">${p.cv}</td><td class="n">${p.servis_yayilimi}/27</td>
         <td class="n">${p.ort_severity}</td></tr>`).join("")}</tbody></table></div></div>`;}
  else if(aktif==="f4"){const g=VERI.asama4_grupla;
    c.innerHTML=kpi([["Tekrar zinciri",say(g.zincir_sayisi)],["Temsilci kayıt",say(g.temsilci),
      `ekran gürültüsü −%${(100-g.temsilci/o.alarm_sayisi*100).toFixed(0)}`],
      ["En uzun zincir",Math.max(...Object.keys(g.boyut_dagilimi).map(Number))+" alarm"]])
      +`<div class="kutu"><p class="baslik">En uzun zincirler</p><div class="tablo-sar"><table>
        <thead><tr><th>Grup</th><th>Anahtar (host|servis|tip|hedef)</th><th class="n">Boyut</th><th>Aralık</th></tr></thead>
        <tbody>${g.en_uzun.map(x=>`<tr><td><code>${x.grup_id}</code></td><td>${esc(x.anahtar)}</td>
        <td class="n">${x.boyut}</td><td>${x.ilk.slice(11,16)}–${x.son.slice(11,16)}</td></tr>`).join("")}
        </tbody></table></div></div>`;}
  else if(aktif==="f5"){const k=VERI.asama5_korele;
    c.innerHTML=kpi([["Çekirdek / olay",k.cekirdek_sayisi],["Atanan alarm",say(k.atanan)],
      ["Elenen alarm",say(k.elenen)]])
      +`<div class="kutu"><p class="baslik">Eleme gerekçe kodları</p>${Object.entries(k.eleme_kodlari)
        .map(([kod,v])=>`<div class="satir" style="display:block">
          <div style="display:flex;justify-content:space-between"><span><b style="color:var(--ink)">${kod}</b></span><b>${say(v.alarm)}</b></div>
          <div style="color:var(--muted);font-size:12.5px;margin-top:3px">${esc(v.tanim)}</div></div>`).join("")}</div>
      <div class="kutu"><p class="baslik">Denetim — elenen alarmlar (ilk 300)</p><div class="tablo-sar"><table>
        <thead><tr><th>Alarm</th><th>Zaman</th><th>Servis</th><th>Tip</th><th class="n">sev</th>
        <th class="n">skor</th><th>Gerekçe</th></tr></thead><tbody>${
        k.elenen_alarmlar.slice(0,300).map(a=>`<tr><td><code>${a.alarm_id}</code></td><td class="n">${a.zaman}</td>
        <td>${a.servis}</td><td><code>${a.tip}</code></td><td class="n">${a.severity}</td>
        <td class="n" style="color:${a.sinyal_skoru>=VERI.esikler.GURULTU_ESIGI?"var(--ink)":"var(--muted)"}">${a.sinyal_skoru}</td>
        <td style="max-width:460px">${esc(a.gerekce)}</td></tr>`).join("")}</tbody></table></div></div>`;}
  else if(aktif==="f6"){
    c.innerHTML=`<p class="baslik">${VERI.asama6_kartlar.length} olay kartı · önceliğe göre sıralı</p>`
      +VERI.asama6_kartlar.map(kartCiz).join("");}

  document.querySelectorAll("[data-ip]").forEach(el=>{
    el.onmousemove=ev=>{const t=$("#ipucu");t.style.display="block";
      t.textContent=el.dataset.ip;t.style.left=(ev.clientX+14)+"px";t.style.top=(ev.clientY+14)+"px";};
    el.onmouseleave=()=>$("#ipucu").style.display="none";});
}

async function calistir(govde){
  const b=$("#calistir"); b.disabled=true; b.textContent="Çalışıyor…";
  $("#icerik").innerHTML=`<div class="bos">Boru hattı çalışıyor…</div>`;
  try{
    const y=await fetch("/api/calistir",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(Object.assign({paylasilan:$("#paylasilan").checked},govde))});
    const j=await y.json();
    if(!y.ok||j.hata){$("#icerik").innerHTML=`<div class="hata">${esc(j.hata||"Bilinmeyen hata")}</div>`;}
    else{VERI=j; sekmeleriCiz(); ciz();}
  }catch(e){$("#icerik").innerHTML=`<div class="hata">${esc(e.message)}</div>`;}
  b.disabled=false; b.textContent="Çalıştır";
}

$("#calistir").onclick=()=>calistir({yol:$("#yol").value.trim()||null});
const drop=$("#drop"), dosya=$("#dosya");
drop.onclick=()=>dosya.click();
dosya.onchange=e=>{const f=e.target.files[0]; if(f) f.text().then(t=>calistir({icerik:t,ad:f.name}));};
["dragenter","dragover"].forEach(t=>document.addEventListener(t,e=>{e.preventDefault();drop.classList.add("uzerinde");}));
["dragleave","drop"].forEach(t=>document.addEventListener(t,e=>{e.preventDefault();drop.classList.remove("uzerinde");}));
document.addEventListener("drop",e=>{const f=e.dataTransfer.files[0];
  if(f) f.text().then(t=>calistir({icerik:t,ad:f.name}));});

sekmeleriCiz();
fetch("/api/varsayilan").then(r=>r.json()).then(j=>{ $("#yol").value=j.yol;
  if(j.var) calistir({yol:j.yol}); });
</script>
</body></html>
"""


class Sunucu(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, bicim, *args):  # sessiz
        pass

    def _gonder(self, govde: bytes, tip: str, kod: int = 200) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", tip)
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def _json(self, nesne: dict, kod: int = 200) -> None:
        self._gonder(json.dumps(nesne, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8", kod)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._gonder(SAYFA.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/varsayilan":
            self._json({"yol": str(VARSAYILAN_GIRDI), "var": VARSAYILAN_GIRDI.exists()})
        else:
            self._json({"hata": "bulunamadi"}, 404)

    def do_POST(self):
        if self.path != "/api/calistir":
            self._json({"hata": "bulunamadi"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            istek = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._json({"hata": f"Istek okunamadi: {e}"}, 400)
            return

        gecici = None
        try:
            if istek.get("icerik"):
                # Tarayicidan yuklenen dosya: once dogrula, sonra gecici dosyaya yaz.
                veri = json.loads(istek["icerik"])
                if not isinstance(veri, list) or not veri:
                    raise ValueError("JSON bir alarm dizisi olmali (bos olmayan liste).")
                eksik = {"alarm_id", "timestamp", "host", "service",
                         "severity", "alarm_type", "message"} - set(veri[0])
                if eksik:
                    raise ValueError(f"Alarm kaydinda eksik alan: {sorted(eksik)}")
                gecici = Path(tempfile.mkstemp(suffix=".json")[1])
                gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
                girdi = gecici
            else:
                girdi = Path(istek.get("yol") or VARSAYILAN_GIRDI)
                if not girdi.exists():
                    raise FileNotFoundError(f"Dosya bulunamadi: {girdi}")

            sonuc = pipeline.calistir(girdi, paylasilan_kaynak=bool(istek.get("paylasilan")))
            sonuc["ozet"]["girdi"] = istek.get("ad") or str(girdi)
            self._json(sonuc)
        except Exception as e:
            self._json({"hata": f"{type(e).__name__}: {e}"}, 400)
        finally:
            if gecici:
                gecici.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Alarm firtinasi web arayuzu.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--acma", action="store_true", help="Tarayiciyi otomatik acma.")
    args = ap.parse_args()

    adres = f"http://{args.host}:{args.port}"
    sunucu = ThreadingHTTPServer((args.host, args.port), Sunucu)
    print(f"Arayuz hazir : {adres}")
    print(f"Varsayilan girdi: {VARSAYILAN_GIRDI}")
    print("Durdurmak icin Ctrl+C")
    if not args.acma:
        threading.Timer(0.6, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatiliyor.")
        sunucu.shutdown()


if __name__ == "__main__":
    main()
