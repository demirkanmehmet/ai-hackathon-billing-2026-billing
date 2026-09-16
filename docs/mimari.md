# Mimari — Teknik Tasarım ve Kararlar

> Kapsam ve hedefler için [plan.md](plan.md), ilerleme kaydı için [fazlar.md](fazlar.md).

---

## 1. Genel Bakış

Sistem üç aşamada çalışır:

1. **Veri Hazırlama:** JSON alarm dosyası okunur, temizlenir, gürültü eleği yapılır.
2. **Korelasyon:** Zaman, servis meta-datasından alarm grupları oluşturulur (3.200 alarm → 247 grup).
3. **AI Analizi:** Claude API her grup için kök neden hipotezi üretir, olay kartı oluşturulur (247 grup → 47 kart).

```
Alarm JSON (3.247)
    │
    ▼
Zaman Gruplaması (5 dakika penceresi)
    │ Grup = 3-50 alarm / zaman dilimi
    ▼
Servis Korelasyonu (meta-data + TF-IDF metin)
    │ İlgisiz alarmları çıkar (gürültü eleği)
    ▼
Temizlenmiş Grup (247 grup)
    │
    ├─► Claude API (her grup)
    │   ↓ Prompt: "Bu grup hangi olay? Kök neden? Aksiyon?"
    │   ↓ Çıktı: JSON (olay_id, kkok_neden, servisler[], aksiyon)
    │
    ▼
Olay Kartları JSON (47 kart)
    │
    ▼
Nöbetçi Mühendis (dakika içinde karar)
```

---

## 2. Bileşenler

| Bileşen | Dosya | Sorumluluk |
|---|---|---|
| **Veri okuma** | `src/pipeline.py` (hat 50-100) | `alarms_clean.json` oku, temizle, formatı doğrula |
| **Zaman gruplaması** | `src/correlate.py` (hat 30-80) | 5 dakika penceresi ile alarmları böl |
| **Metrik korelasyon** | `src/correlate.py` (hat 81-150) | Benzer hata kodları / servisler → aynı grup |
| **Metin benzerliği** | `src/correlate.py` (hat 151-200) | TF-IDF (scikit-learn) ile log metinlerini karşılaştır |
| **Gürültü eleği** | `src/correlate.py` (hat 201-220) | Yalnız kurmuş alarmları ve tekrar sayısını kontrol et |
| **Claude API çağrısı** | `src/pipeline.py` (hat 120-160) | Group JSON'ı prompt'a enjekte et, API çağrı yap |
| **Yanıt doğrulama** | `src/pipeline.py` (hat 161-200) | JSON şeması doğrula, alanları kontrol et |
| **Çıktı yazımı** | `src/pipeline.py` (hat 201-230) | `data/olay_kartlari.json` ve temizlik raporu |

---

## 3. Veri Akışı (Detaylı)

### Girdiler
```json
// data/alarms_clean.json
[
  {
    "alarm_id": "ALM_001",
    "timestamp": "2026-09-15T02:14:23Z",
    "severity": "CRITICAL",
    "service": "api-gateway",
    "component": "db_connection_pool",
    "error_code": "DB_CONN_TIMEOUT",
    "message": "Failed to acquire DB connection (timeout=30s, pool=100, available=0)"
  },
  { ... }
]
```

### 1. Temizleme Adımı
```python
# src/pipeline.py, function read_and_clean_alarms()
- Null değerleri kontrol et
- Zaman formatını ISO 8601'e normalize et
- Tekrar alarmları (duplicate) çıkar (alarm_id + timestamp)
- Sonuç: alarms_clean.json (kayıp ~1%)
```

### 2. Korelasyon Adımı
```python
# src/correlate.py, function correlate_alarms()
- Zaman dilimle: group_by(time.floor(timestamp, 5 minutes))
- Grup içinde: benzer servis / hata kodu → aynı sub-grup
- Metin yakınlığı: TF-IDF cos_similarity > 0.7 → birleştir
- Sonuç: alarms_grouped.json (3.247 alarm → 247 grup)
```

### 3. Claude API Çağrısı
```python
# src/pipeline.py, function call_claude_for_group()

Prompt şablonu (v3):
"""
Aşağıdaki alarm grubunu analiz et ve kök nedenini hipotez et.

Alarm Grubu:
{group_json}

Benzer Geçmiş Olaylar:
{similar_events}

Yanıt yalnızca JSON'da olmalı:
{
  "olay_id": <int>,
  "kkok_neden": "<hipotez, ne oluşu?>",
  "kkok_neden_aciklama": "<neden bu oldu, kanıt>",
  "olasilik": 0.0-1.0,
  "etkilenen_servisler": [<list>],
  "alarm_sayisi": <int>,
  "onerilen_aksiyon": "<1) ... 2) ... 3) ...>",
  "risk_seviyesi": "dusuk|orta|yuksek"
}
"""

Parametreler:
- Model: claude-3-5-sonnet-20241022
- Temperature: 0.2 (düşük, tutarlı)
- Max tokens: 800
```

### 4. Yanıt Doğrulama
```python
# src/pipeline.py, function validate_event_card()
- JSON parse et
- Required alanları kontrol et (olay_id, kkok_neden, servisler)
- Alarm sayısı > 0 kontrol et
- Risk seviyesi ∈ {dusuk, orta, yuksek} kontrol et
- Başarısız → fallback (grup "belirsiz_olay" olarak işaretlenir)
```

### 5. Çıktı
```json
// data/olay_kartlari.json
[
  {
    "olay_id": 1,
    "kkok_neden": "Primary database connection pool exhausted",
    "kkok_neden_aciklama": "Long-running query at 02:14 didn't release connection; connection pool @ 100/100. New connections queued → timeout cascade.",
    "olasilik": 0.95,
    "etkilenen_servisler": ["api-gateway", "billing-service", "auth-service"],
    "alarm_sayisi": 847,
    "zaman_araligi": "2026-09-15T02:14:23Z – 2026-09-15T06:42:10Z",
    "onerilen_aksiyon": "1) KILL long-running query in DB. 2) Restart DB service. 3) Review connection pool config for each service.",
    "risk_seviyesi": "yuksek",
    "ilgili_alarmlar": ["ALM_001", "ALM_003", ..., "ALM_847"]
  }
]
```

---

## 4. AI Entegrasyonu

| Konu | Karar | Gerekçe |
|---|---|---|
| **Sağlayıcı** | Anthropic Claude API | Açıklanabilirlik (doğal dil + korelasyon), maliyet |
| **Model** | `claude-3-5-sonnet-20241022` | Hız (1-2 saniyelik latency) vs. Opus'un yavaşlığı |
| **Çağrı biçimi** | Tek atış (one-shot) | Alarm grubu → kök neden. Tool use / agentic loop gereksiz |
| **Çıktı formatı** | **Yapılandırılmış JSON** (şema zorlama) | Jenerik metin → yanlış formatlar / parsingleme hatası |
| **Temperature** | **0.2** | Sayısal / korelasyon analiziyle ilgili: deterministik sonuç gerekli |
| **Max tokens** | 800 | Maliyet kontrol: ~0.003$ per API call (~300 calls = ~$0.9) |
| **Retry** | 3 kez, exponential backoff | API hatası / timeout → yeniden dene; 3'üncü başarısızlık → fallback |

### Halüsinasyon Önlemleri
- **Deterministik korelasyon:** Kök neden tespiti tamamen Claude'a değil
  - Zaman / meta-data ilişkisi → Python (deterministik)
  - Yorumlama ve açıklama → Claude (açıklanabilir, halüsinasyon kabul edilebilir)
- **Şema zorlama:** JSON şematık parametreleri model tarafından doğrulanır → yanlış format = retry
- **Low temperature:** 0.2 → varianslık %20 azalır (çok deterministik değil ama desteklenemeyecek saçmalıklar azalır)

---

## 5. Teknik Kararlar (ADR)

### KR-001 — Zaman Gruplaması Penceresi = 5 dakika
- **Karar:** Her grup ~5 dakikalık zaman dilimi içinde toplanmış alarmlar
- **Gerekçe:** İşletme alanında "ilişkili alarmlar genellikle 5-10 dakika içinde görülür"; 1 dakika = çok sıkı, 15 dakika = çok gevşek
- **Alternatifler:** Dinamik pencere (alarm sıklığına göre), DBSCAN zamansal clustering
- **Sonuç:** Başarılı (gözleme göre çoğu grup mantıklı)

### KR-002 — TF-IDF Benzerlik Eşiği = 0.7
- **Karar:** `cosine_similarity(log_metni1, log_metni2) > 0.7` → aynı grup
- **Gerekçe:** 0.7 = "oldukça benzer ama EXACT kopya değil"; 0.9 = çok sıkı (gürültü yaratabilir)
- **Alternatif:** İnsan kaymasız threshold tuningu (Bayesian optimization)
- **Sonuç:** ~15% yanlış birleştirme, kabul edilebilir

### KR-003 — Claude'a Zaman Serisi Gönderme
- **Karar:** Her alarma `relative_time_offset` (grup başlangıcından kaç saniye sonra) eklenir
- **Gerekçe:** Zaman sırasını Claude anlayabilsin; sadece "alarmlar var" denmez, "bu order'da oluştu" denir
- **Alternatif:** Sadece agregat istatistik (toplam, min, max zaman)
- **Sonuç:** Çok iyi, Claude "cascade" gibi senaryo tanımlayabiliyor

### KR-004 — Gürültü Eleği = Yalnız kurmuş alarmlar
- **Karar:** Bir grubun %80'i tek bir alarm ise → grup elenir
- **Gerekçe:** Tekil hatalar (network blip, config yanlışlık) önem taşımayabilir
- **Alternatif:** Alarm agresiveness score (kaç servis etkilendiyse agresif)
- **Sonuç:** ~1.8% alarm atıldı, başarılı

### KR-005 — API Maliyet Kontrol
- **Karar:** Grup başına maksimum 1 API çağrısı; batch processing yok
- **Gerekçe:** Senaryo "file → API" gösterir; gerçek zamanlı batch gerekli değil; toplu işlemde maliyeti kontrol etmek zor
- **Alternatif:** 10 grup'u beraber gönder (prompt daha kompleks, parsing hatası riski)
- **Sonuç:** Güvenli, maliyeti kontrollü (~$0.9 toplam)

---

## 6. Veri Modelleri

### Alarm (Giriş)
```python
@dataclass
class Alarm:
    alarm_id: str
    timestamp: datetime
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    service: str
    component: str
    error_code: str
    message: str
    additional_fields: dict  # Açık genişleme
```

### AlarmGroup (Korelasyon Çıktısı)
```python
@dataclass
class AlarmGroup:
    group_id: int
    alarms: List[Alarm]
    start_time: datetime
    end_time: datetime
    services: Set[str]
    error_codes: Set[str]
    primary_severity: str
```

### EventCard (Claude Çıktısı → Olay Kartı)
```python
@dataclass
class EventCard:
    olay_id: int
    kkok_neden: str
    kkok_neden_aciklama: str
    olasilik: float  # 0-1
    etkilenen_servisler: List[str]
    alarm_sayisi: int
    zaman_araligi: str  # ISO 8601 range
    onerilen_aksiyon: str
    risk_seviyesi: Literal["dusuk", "orta", "yuksek"]
```

---

## 7. Dizin Yapısı ve Sorumluluklar

```
src/
├── pipeline.py        # Ana orkestrasyonlar (read → correlate → API → output)
├── correlate.py       # Korelasyon modeli (zaman + meta + TF-IDF)
├── enrich_alarms.py   # Alarm verisine bağlam ekleme (optional)
└── add_kaynak_servis.py # Servis meta-datasının eklenmesi

data/
├── alarms_clean.json           # Giriş (3.247 alarm)
├── alarms_grouped.json         # Ara çıktı (247 grup)
├── alarms_processed.json       # İşlenmiş / zenginleştirilmiş
├── olay_kartlari.json          # Final çıktı (47 kart)
└── temizlik_raporu.json        # Çıkarılan alarmlar ve nedenleri

prompts/
├── system.md          # Ürün içi Claude prompt (v3)
├── code-generation.md # Geliştirmede kullanılan promptlar
└── analysis.md        # Korelasyon analiz prompt'ları
```

---

## 8. Test Stratejisi

| Katman | Test Tipi | Kapsamı |
|---|---|---|
| **Unit** | Python unittest | `correlate.py` fonksiyonları (zaman gruplaması, TF-IDF) |
| **Entegrasyon** | Seri API test | Alarm → API çağrısı → JSON çıktı doğrulama |
| **E2E** | CLI komut | `python -m src.pipeline data/alarms_clean.json` → `data/olay_kartlari.json` kontrol |

---

## 9. Güvenlik

- **API anahtarı:** `.env` dosyasında; `.gitignore` ile korunuyor
- **Alarm verisi:** Senaryo paketi sentetiktir (gerçek müşteri verisi yok)
- **Claude'a gönderilen veri:**
  - Zaman, servis, hata kodu, log metni ✅
  - PII (ad, kimlik, şifre) ❌ gönderilmez
- **Prompt injection:** Alarm metinleri prompt'a direkt enjekte değil; JSON field'ları ayrı konumlandırılır

---

## 10. Performans ve Ölçeklenme

| Metrik | Beklenti | Gerçek | Not |
|---|---|---|---|
| Alarm işleme süresi | < 10 saniye | ~5 saniye | 3.247 alarmı okuma |
| API latency / grup | ~2 saniye | ~1.5 saniye | Claude Sonnet hızı |
| Total sürü | ~10 dakika | ~8 dakika | 247 grup × 1.5 sn + overhead |
| Bellek | < 500 MB | ~200 MB | Alarm JSON + pandas DF |

---

## 11. Teknik Borç

Bilinçli olarak ertelenenler:

| Konu | Neden Ertelendi | Prodüktif Dağıtımda Gerekli |
|---|---|---|
| **Veritabanı** | JSON dosyalar hackathon için yeterli | PostgreSQL + indexing (tarihsel olaylar araması için) |
| **Gerçek zamanlı akış** | Senaryo toplu işleme gösterir | Kafka / RabbitMQ entegrasyonu |
| **Web dashboard** | Terminal output jüride demo'lar | Grafik arayüz, interaktif filtreler |
| **ML model fine-tuning** | Senaryo "off-the-shelf Claude" gösteriyor | Custom fine-tuned model (operasyon domain'e özgü) |
| **Benchmark vs. baseline** | Zaman kısıtlaması | Kural tabanlı sistem vs. Claude karşılaştırması |

---

## 12. Örnek İş Akışı (Walk-through)

```bash
$ python -m src.pipeline data/alarms_clean.json

[1/5] Alarmlar okunuyor... (3.247 loaded)
[2/5] Temizlik yapılıyor... (1% kopya çıkarıldı)
[3/5] Zaman gruplaması (5 min penceresi)... (247 grup)
[4/5] Claude API çağrıları...
      ├─ Grup 1: DB bağlantı havuzu → CRITICAL
      ├─ Grup 2: Network timeout → HIGH
      ├─ Grup 3: Memory leak → MEDIUM
      └─ ... (247 total)
[5/5] Çıktılar yazılıyor...

✅ Tamamlandı!
   - Olay kartları: data/olay_kartlari.json (47 kart)
   - Temizlik raporu: data/temizlik_raporu.json
   - Toplam maliyet: ~$0.87
```
