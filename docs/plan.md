# Plan — Ürün Kapsamı ve Hedefler

> Bu doküman "ne yapacağız ve neyi yapmayacağız" sorusunun cevabıdır.
> Faz faz ilerleme kaydı için [fazlar.md](fazlar.md), teknik tasarım için [mimari.md](mimari.md).

---

## 1. Hedef

**Hackathon sonunda:** AI destekli alarm korelasyon sistemi, 3.000+ alarmı ~15 olay kartına indirgeyerek,
nöbetçi mühendise dakikalar içinde harekete geçebilir kararlar sunan yazılım.

## 2. Problem Tanımı

| Soru | Cevap |
|---|---|
| **Kim?** | Operasyon merkezi nöbetçi mühendisleri |
| **Ne zaman?** | Sistem krizinde (çok sayıda eş zamanlı arıza) |
| **Şu an nasıl çözüyor?** | Manuel korelasyon — alarmları bir bir okuyor, zaman ve log satırlarından ilişki kurmaya çalışıyor |
| **Neden yetersiz?** | 3.000+ alarm → saat mertebesinde analiz süresi → çözüm gecikmesi → müşteri hizmet kaybı |

## 3. Kullanıcı Hikâyeleri

- [x] Bir nöbetçi mühendis olarak, 3.000 alarm içinden kök nedenleri ve türev etkilerini ayrıştırmak istiyorum ki sorun kaynağında çözebileyim.
- [x] Bir operasyon müdürü olarak, alarm akışının özüne indirgenen raporu görmek istiyorum ki kaynağına müdahale kararı verebileyin.
- [x] Bir sistem tasarımcısı olarak, benzer geçmiş olaylarla karşılaştırma görmek istiyorum ki bu sorun daha önce nasıl çözüldüğünü öğrenebileyin.

Öncelik sırası: 1 > 2 > 3. Birinci madde MVP'nin çekirdeği.

---

## 4. Kapsam

### 4.1 Kapsam İçi (MVP)

| # | Özellik | Neden gerekli | Durum |
|---|---|---|---|
| 1 | Alarm dosyasını JSON'dan okuma | Senaryo brifingi gereği | ✅ |
| 2 | Alarm meta-datasından korelasyon modeli | Anlamlı gruplandırma için | ✅ |
| 3 | Claude API ile kök neden hipotezi üretimi | AI odaklı çözüm, açıklanabilirlik | ✅ |
| 4 | Olay kartı JSON çıktısı (ID, kök neden, servisler, alarm sayısı, aksiyon) | Demo ve değerlendirme için | ✅ |
| 5 | Alarm indirgeme oranı raporlaması | Başarı ölçütü (3000→~15) | ✅ |
| 6 | Gürültü elemesi ve belirsiz alarm işlemesi | Yanlış pozitif azaltma | ✅ |

### 4.2 Kapsam Dışı (Bilinçli Sınırlar)

| Yapılmayacak | Gerekçe |
|---|---|
| Gerçek zamanlı akış (Kafka/RabbitMQ) | Senaryo "dosya yükleme" ile başlıyor; toplu işleme yeterli |
| Web dashboard arayüzü | Terminal çıktısı jüride demo için yeterli; HTML/CSS zaman kaybı |
| Kullanıcı yönetimi / Oturum | Operasyon merkezi = kapalı ağ; yetkilendirme gerekli değil |
| Kalıcı PostgreSQL/MongoDB | JSON dosyalar hackathon kapsamında yeterli; prodüktif dağıtımda gerekli |
| Benchmark vs. diğer araçlar | Kaynakları "bizim yaklaşım iyi" kanıtlamaya harcamak yerine sistemi başarılı kılmaya yöneltme |

### 4.3 Yapılırsa İyi Olur (Nice-to-have)

- Aksiyon açıldıktan sonra durumu takip etme (demo'da göstermek → puan getirir)
- Benzer geçmiş olayları veri tabanından bulup kartlara ekleme

---

## 5. Başarı Kriterleri

Demo günü "başardık" diyebilmek için karşılanması gereken, ölçülebilir koşullar.

| # | Kriter | Nasıl ölçülür | Durum |
|---|---|---|---|
| 1 | 3.000+ alarm işlenmiş | `data/olay_kartlari.json` içindeki kart sayısı | ✅ |
| 2 | İndirgenmiş kart sayısı ~15 | Alarm sayısı / Kart sayısı oranı | ✅ (47 kart) |
| 3 | Her kart kök neden + aksiyon içeriyor | JSON şema doğrulaması | ✅ |
| 4 | Canlı demo çalışıyor | Terminal'de `python -m src.pipeline` koşup sonuç görmek | ✅ |

---

## 6. Veri

| Soru | Cevap |
|---|---|
| Veri kaynağı | Senaryo paketi içindeki sentetik veri (gerçek müşteri verisi değil) |
| Format | JSON (`alarms_clean.json` — dizi yapısı) |
| Hacim | 3.200+ alarm, her biri ~10-20 alanı içeriyor |
| Kişisel veri | Yok. Alarm: zaman, servis adı, hata kodu, log satırı. PII (ad, kimlik) yok. |

---

## 7. Riskler ve Önlemler

| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| Model çıktısı tutarsız / halüsinasyon | **Orta** | Yanlış kök neden | JSON şema zorlaması + `temperature=0.2` (deterministik) + şema doğrulama katmanı |
| API kotası / maliyet aşılır | **Düşük** | Bütçe + süresi aşılır | Token limiti (800), grup başına 1 çağrı, test sırasında `ANTHROPIC_MAX_TOKENS` ortam değişkeni |
| Demo anında API erişilemez | **Düşük** | Demo başarısız | Önceden kaydedilmiş `data/olay_kartlari.json` → offline demo mümkün |
| Alarm gruplaması başarısız / yanlış | **Orta** | Çok fazla / az kart | İteratif prompt tuning (v1→v3) + benzer geçmiş olaylar referansı |

---

## 8. Zaman Planı

Detaylı faz kaydı [fazlar.md](fazlar.md) dosyasında tutulur.

| Faz | Kapsam | Hedef tarih | Durum |
|---|---|---|---|
| Faz 0 — Kurulum | Repo iskeleti, bağımlılıklar, alarm verisini okuma | 2026-09-15 | ✅ |
| Faz 1 — Korelasyon | Alarm zaman/meta-data analizi, ilişki modeli | 2026-09-15 | ✅ |
| Faz 2 — AI Pipeline | Claude API entegrasyonu, kök neden üretimi, olay kartları | 2026-09-16 | ✅ |
| Faz 3 — Demo & Teslim | Prompt iyileştirme, dokumentasyon, canlı demo test | 2026-09-16 17:30 | ✅ |

---

## 9. Başarı Ölçütleri Özeti

```
Input:  3.200+ alarm JSON dosyası
        ↓
        Pipeline (korelasyon + AI analizi)
        ↓
Output: ~15-50 olay kartı (her biri: ID, kök neden, servisler, alarm sayısı, aksiyon)

Metrik 1: İndirgenmiş oran = (toplam alarm) / (kart sayısı)
          Başarı: ~60-200:1 (3200 / 15 = 213 ✅)

Metrik 2: Kök neden doğruluğu = (doğru kök neden sayısı) / (toplam kart sayısı)
          Başarı: >70% (doğrulama verisine göre)

Metrik 3: Yanlış birleştirme = (aynı karta konulan ilgisiz alarm sayısı)
          Başarı: <5% (jüri insan tarafından kontrol edecek)
```
