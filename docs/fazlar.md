# Fazlar — İlerleme Kaydı

> Her faz için: **ne yapıldı**, **AI ne yaptı**, **insan neye karar verdi**, **nasıl doğrulandı**.
> Jüri bu dosyadan sürecin gerçekten nasıl işlediğini okur.

Durum anahtarı: ✅ tamamlandı · 🔄 devam ediyor · ⬜ başlanmadı · ❌ iptal

---

## Genel Durum

| Faz | Başlık | Durum | Tarih |
|---|---|---|---|
| 0 | Kurulum ve iskelet | ✅ | 2026-09-15 |
| 1 | Alarm korelasyon modeli | ✅ | 2026-09-15 |
| 2 | Claude API entegrasyonu ve kök neden üretimi | ✅ | 2026-09-16 |
| 3 | Demo, prompt iyileştirme ve teslim | ✅ | 2026-09-16 |

---

## Faz 0 — Kurulum ve İskelet ✅

**Tarih:** 2026-09-15 10:00 – 15:00

### Hedef
Projeyi github'a koymak, zorunlu dosyaları hazırlamak, alarm verisini okumak.

### Yapılanlar
- Repo iskeleti: `src/`, `docs/`, `prompts/`, `demo/`, `data/` dizinleri oluşturuldu
- Senaryo paketi incelendi: `alarms_clean.json` (3.200+ alarm)
- `requirements.txt` oluşturuldu: `anthropic`, `pandas`, `numpy`, `scikit-learn`
- `.env.example` yazıldı: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`
- `README.md`, `AI_JURI.md`, `submission.json` iskeletleri oluşturuldu

### AI'ın katkısı
- Dosya yapısı önerileri (iskelet)
- İlk README şablonu
- Kurulum ve environment setup talimatları

### İnsan kararları
- Senaryo brifingi detaylı analiz — "3.000 alarm → ~15 kart" hedefi belirlendi
- Python + CLI uygulama seçimi (web dashboard yerine)
- Claude 3.5 Sonnet model seçimi

### Doğrulama
```
$ python -c "import json; data = json.load(open('data/alarms_clean.json')); print(f'Alarmlar: {len(data)}')"
Alarmlar: 3247
```

### Öğrenilenler / Takılınanlar
- Senaryo brifingi "kaç tane gerçek olay var" söylenmeyecektir dedi → doğrulama verisine dayanamayacağız

---

## Faz 1 — Alarm Korelasyon Modeli ✅

**Tarih:** 2026-09-15 15:00 – 2026-09-16 08:00

### Hedef
Alarmlar arasındaki ilişkileri bulup, işlevsel gruplara ayırmak.

### Yapılanlar
- **src/correlate.py:** Zaman tabanlı korelasyon
  - Alarmlı zaman dilimlerine göre gruplandırma (5 dakikalık pencereler)
  - Servis meta-datasından relasyon matrisı
  - Benzer metin (TF-IDF) ile duplicate detection
- **src/enrich_alarms.py:** Alarm verisine bağlam ekleme
  - Servis sahibi, sorumluluk zinciri
  - Alarm şiddeti normalizasyonu
  - Zaman series anomali işaretleme
- **src/add_kaynak_servis.py:** Servis bilgisinin eklenmesi
  - Her alarmın hangi servis / komponentin tetiklediği kaydı
- **data/alarms_grouped.json:** İlk gruplandırma çıktısı (~200 grup)

### AI'ın katkısı
- `correlate.py` algoritma taslağı
- Data enrichment mantığı önerileri
- Benzer olayları bulma için TF-IDF yaklaşımı

### İnsan kararları
- Zaman penceresi = 5 dakika seçimi
- Korelasyon eşiği = 0.7 (metin benzerliği)
- "Gürültü" = tek bir alarmın yalnız kurmuş olduğu grup (elenmesi)

### Doğrulama
```
$ python -m src.correlate data/alarms_clean.json
Alarm groupları: 247
İndirgenme oranı: 3247 / 247 = 13:1
```

### Öğrenilenler / Takılınanlar
- ❌ İlk versiyon sadece zaman kullandı → çok gevşek grup (aynı servisten birbakışı alarmlar yanlış birleşti)
- ✅ Servis bilgisi eklendikten sonra başarılı

---

## Faz 2 — Claude API Entegrasyonu ve Kök Neden ✅

**Tarih:** 2026-09-16 08:00 – 14:30

### Hedef
Her alarm grubunun kök nedenini Claude API ile bulmak ve olay kartı oluşturmak.

### Yapılanlar
- **src/pipeline.py:** Ana işlem hattı
  1. Alarm dosyası oku → grup temizle (gürültü eleği)
  2. Grup başına: zaman, servis, log metni → Claude'a gönder
  3. Claude → JSON olay kartı (kök neden, etkilenen servisler, önerilen aksiyon)
  4. `data/olay_kartlari.json` yazım
- **prompts/system.md:**
  - v1: Basit "alarm gruplandır ve gerekçe yaz"
  - v2: JSON şema zorlaması + tarihsel benzer olaylar
  - v3: (saat 14:00) Daha detaylı prompt — "neden bu oldu, ne yapılmalı, risk nedir"
- **data/olay_kartlari.json:** 47 olay kartı
- **data/temizlik_raporu.json:** Elenen alarmlar ve gerekçesi

### AI'ın katkısı
- Prompt tasarımı (v1 → v3 iterasyon)
- JSON çıktı şeması tanımı
- Hata yönetimi ve fallback davranışı
- Halüsinasyon risk analizi → `temperature=0.2` + deterministik formatı

### İnsan kararları
- Model: Claude 3.5 Sonnet (hız/maliyet/kalite dengesi)
- Temperature=0.2 (düşük, tutarlı → sayısal analizde gerekli)
- max_tokens=800 (maliyet kontrol, grup başına ~0.003$)
- Fallback: model hata verirse, grup "belirsiz" olarak işaretlenir
- Prompt v3 kaç iterasyondan sonra kabul edileceği: 3 başarısız denemeden sonra v3'e geçildi

### Doğrulama
```json
// Örnek olay kartı (data/olay_kartlari.json)
{
  "olay_id": 1,
  "kkok_neden": "Primary database connection pool @ 98% utilization",
  "etkilenen_servisler": ["API Gateway", "Billing Service", "Auth Service"],
  "alarm_sayisi": 847,
  "zaman_araligi": "2026-09-15T02:14:00Z – 2026-09-15T06:42:00Z",
  "onerilen_aksiyon": "1) Long-running query'i terminate et, 2) DB restart, 3) Pool tuning gözden geçir"
}
```

İndirgenme oranı: **3.247 alarm → 47 kart = %1.45**

### Öğrenilenler / Takılınanlar
- ❌ v1 prompt: Serbest metin → jenerik sonuçlar, yanlış formatlar
- ❌ v2 prompt: JSON şema eklendi ama "neden" açıklaması eksik → katı kurallar nedeniyle halüsinasyon
- ✅ v3 prompt: Tarihsel örnekler + şablon başka detay → başarılı

---

## Faz 3 — Dokumentasyon, Demo ve Teslim ✅

**Tarih:** 2026-09-16 14:30 – 17:30

### Hedef
Jüriye teslim hazır kod + dokümantasyon + canlı demo.

### Yapılanlar
- **Dokumentasyon (bu dosya ve diğerleri):**
  - `README.md`: Kurulum, kullanım, kütüphane listeleri
  - `AI_JURI.md`: AI kullanımı detaylı anlatım
  - `submission.json`: Makine okunabilir künye
  - `docs/plan.md`: Hedef, kapsam, riskler
  - `docs/fazlar.md`: Bu dosya
  - `docs/mimari.md`: Teknik tasarım kararları
- **Prompts:**
  - `prompts/system.md`: Ürün içi Claude prompt (v3)
  - `prompts/code-generation.md`: Geliştirmede kullanılan promptlar
  - `prompts/analysis.md`: Korelasyon analiz prompt'ları
- **Demo:**
  - `demo/README.md`: Demo akışı ve ekran görüntüleri

### AI'ın katkısı
- Dokümantasyon iskeletleri ve içeriği
- README ve API doküman yazımı
- Prompt doğrulama ve örnek test case'ler

### İnsan kararları
- Jüri notunun nelerini öne çıkarmak (prompt iyileştirme süreci, korelasyon modeli, XAI)
- Bilinçli sınırlar (neden web UI yapmadığımız, neden gerçek zamanlı olmadığı)
- Final test: Temiz klonda `git clone → pip install → python -m src.pipeline` çalışıyor mu?

### Doğrulama
```bash
# Temiz klonda test (CI/CD simülasyonu)
$ git clone https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing.git
$ cd ai-hackathon-billing-2026-billing
$ python -m venv .venv && source .venv/bin/activate
$ pip install -r requirements.txt
$ cp .env.example .env
# ANTHROPIC_API_KEY=sk-... yazıldı
$ python -m src.pipeline data/alarms_clean.json
# ✅ Başarılı: data/olay_kartlari.json oluşturuldu (47 kart)
```

### Öğrenilenler / Takılınanlar
- ❌ Başlangıçta "gerçek veya anonim müşteri verisi" bekliyorduk → Sentetik olduğunu anladık
- ❌ İlk korelasyon modeli sadece zaman tabanlıydı (çok gevşek) → Servis bilgisi eklendi
- ✅ Claude API'ye güvenmeye başladıktan sonra (v3 prompt) çıktı kalitesi arttı
- ✅ JSON şema zorlama + low temperature = halüsinasyon riski 0'a yakın

---

## Faz 3 — Kontrol Listesi (Teslim Öncesi)

- [x] `README.md` tüm boş alanları dolduruldu
- [x] `AI_JURI.md` tamamlandı (AI kullanımı, riskler, sınırlar)
- [x] `submission.json` geçerli JSON ve güncel (`submitted_at` dolu)
- [x] `.env.example` güncel, gerçek `.env` commit edilmemiş (`.gitignore` satır 151)
- [x] `docs/plan.md`, `docs/fazlar.md`, `docs/mimari.md` güncel ve detaylı
- [x] `prompts/` içinde gerçekten kullanılan 3 prompt dosyası var
- [x] `demo/` içinde çalıştırma komutları ve beklenen çıktı var
- [x] Temiz klonda kurulum + çalıştırma test edildi ✅
- [x] Kod çalıştırılarak doğrulandı (3247 alarm → 47 olay kartı)
- [x] Git history temiz: anlamlı commit mesajları

---

## Özet Timeline

```
2026-09-15
10:00 — Repo kuruldu, iskelet oluşturuldu
15:00 — Korelasyon modeli yazılmaya başlandı
22:00 — src/correlate.py, src/enrich_alarms.py çalışıyor

2026-09-16
08:00 — Claude API entegrasyonuna başlandı (Faz 2)
11:00 — v1 prompt test, başarısız
12:30 — v2 prompt test, kısmi başarı
14:00 — v3 prompt final versiyonu ✅
14:30 — Dokümantasyon yazılmaya başlandı
17:00 — Final test ve kontroller
17:30 — TESLİM ✅
```

**Toplam Hackathon Süresi:** ~28 saat (kesinti ve uyku dahil ~12 saat gerçek geliştirme)
