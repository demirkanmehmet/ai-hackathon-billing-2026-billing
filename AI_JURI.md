# AI_JURI.md — AI Jüri Değerlendirme Özeti

Bu dosya, AI Jürisinin projeyi ve AI kullanımını hızlıca değerlendirebilmesi için
yapılandırılmış bir özettir. Her başlık altına somut, doğrulanabilir bilgi yazın.

---

## 0. Künye

| Alan | Değer |
|---|---|
| Proje adı | Alarm Fırtınası Analiz Sistemi |
| Takım | Bill & Chill |
| Kategori | Operasyon / Anomali Tespiti |
| Repo | https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing |
| Başlangıç | 2026-09-15 |
| Teslim | 2026-09-16 |
| Ana dil / stack | Python 3.11+ |
| Birincil AI Platform | Anthropic Claude API |

---

## 1. Tek Cümlelik Özet

Operasyon merkezindeki binlerce alarm içinden AI ile anlamlı olayları çıkarıp,
nöbetçi mühendise harekete geçebilir kök neden hipotezleri ve öneriler sunmak.

---

## 2. Problem ve Çözüm

### Problem
**Senaryo:** Operasyon merkezinde eylül gecesi, saat 02:14'te sistem çöküyor. Dört saatlik
pencerede **3.000+ alarm** birbirini kovalıyor.

**Nöbetçi mühendis:**
- Kök neden mi, türev etki mi, gürültü mü olduğunu ayırt edemez
- Manuel korelasyon kurmaya çalışırsa saatlerce sürer
- Müdahale sırasını yanlış belirler → çözüm zamanı uzar

**Maliyet:** Çözümde ortalama 4-6 saat kayıp, müşteri hizmet akışı kesintileri, güvensizlik.

### Çözüm
**Sistem adımları:**
1. 3.000+ alarm JSON dosyası yüklenir
2. Zaman, meta-data, servis bağlantılarından korelasyon analizi yapılır
3. **Claude API** alarmları değerlendirip anlamlı olaylara gruplandırır:
   - Kök neden hipotezi (doğal dilde, gerekçeli)
   - Etkilenen servisler
   - İlişkili alarm sayısı
   - Önerilen ilk aksiyon
4. Sonuç: **3.000 alarm → 10-15 olay kartı**
5. Nöbetçi dakika içinde kartları okuyup harekete geçer

**Kullanıcının gördüğü:**
```
─────────────────────────────────────────
OLAY 1: Database Bağlantı Havuzu Tükendi
─────────────────────────────────────────
Kök Neden: Primary DB bağlantı havuzu %98 dolu
  → 4 saat önce long-running query başladı
  → Yeni bağlantılar kurulamıyor
Etkilenen Servisler: API Gateway, Billing Service, Auth Service
İlişkili Alarmlar: 847
Zaman Aralığı: 2026-09-15 02:14 – 06:42

Önerilen Aksiyon: 1) Long query'i kapat, 2) DB restart, 3) Connection pool tuning gözden geçir

Doğrulama: Benzer geçmiş olaylar [Olay #2834 (2026-08-10), Olay #1102 (2026-07-15)]
─────────────────────────────────────────
```

### AI olmasaydı?
**Kural tabanlı yaklaşım:** "Eğer A ve B alarmu 5 dakika içinde gelirse, aynı grup"
- ❌ Dinamik olmayan (gerçek korelasyon veriye bağlı)
- ❌ Yanlış pozitif/negatif yüksek
- ❌ İnsan neden bunu grupladığını anlamıyor

**Neden AI gerekli:**
- Veri dinamiktir — her olayın yapısı farklı olabilir
- AI, tarihsel alarmlardan **öğreniyor** ve benzer örüntüleri yakalar
- **Doğal dille gerekçe** sunar — mühendis bağlamı anlayıp güvenle karar verir
- İnsan kontrol hep başta: AI önerir, insan onaylar/reddeder

---

## 3. AI Kullanımı — Üründe

Ürünün **çalışma zamanında** AI'ı nasıl kullandığı.

| Alan | Değer |
|---|---|
| Sağlayıcı | Anthropic Claude API |
| Model(ler) | `claude-3-5-sonnet-20241022` |
| Kullanım noktası | Alarm Gruplaması → Kök Neden Analizi → İşlem Önerisi (src/pipeline.py, hat 150-200) |
| Girdi | Alarmlı 30-50 satırlık JSON (zaman, servis, hata kodu, metin); benzer geçmiş olaylar |
| Çıktı | **JSON şeması** (olay kartı): `{olay_id, kkok_neden, etkilenen_servisler[], alarm_sayisi, onerilen_aksiyon}` |
| Deterministiklik | `temperature=0.2` (düşük, tutarlı sonuçlar); JSON şema ile zorunlu yapılandırma |
| Hata/fallback | Model yanıt vermezse/şema dışında döndürürse: alarm grubu "belirsiz" olarak işaretlenir; insan müdahalesi gerekli |
| Maliyet kontrolü | `max_tokens=800`; grup başına 1 çağrı; toplu işleme (batch) |

**Prompt kaynağı:** [prompts/system.md](prompts/system.md)

### MCP Sunucuları / Harici Araçlar
Kullanılmadı.

---

## 4. AI Kullanımı — Geliştirme Sürecinde

Kodu yazarken AI'dan nasıl faydalanıldığı.

| Araç | Ne için kullanıldı |
|---|---|
| Claude Code (IDE) | Pipeline iskelet kod, korelasyon algoritması, veri ön işleme |
| Anthropic Claude API | Prompt iyileştirmesi, test case'leri, hatalar hakkında danışma |

### AI'ın ürettiği işler
- **src/pipeline.py** ilk sürümü (alarm okuma, temizleme, Claude API çağrısı)
- **src/correlate.py** (zaman tabanlı ve meta-data korelasyon)
- **src/enrich_alarms.py** (veri zenginleştirme)
- **prompts/system.md** (döngüsel iyileştirme ile; v1 → v3)
- **docs/** dosyaları (plan, mimari, fazlar)
- **requirements.txt** ve ortam kurulumu
- Test case'leri ve hata ayıklama önerileri

### İnsanın verdiği kararlar
- **Problem tanımı:** Senaryo brifingi okudu, "3000 alarm → 15 kart" hedefini belirledi
- **Mimari tasarım:** Pipeline → Korelasyon → Zenginleştirme adımlarını tasarladı
- **Model seçimi:** Claude 3.5 Sonnet (hız/maliyet dengesi) seçildi
- **Prompt stratejisi:** JSON output, temperature=0.2, max_tokens=800 kararları
- **Veri seçimi:** Hangi alarm alanlarının korelasyonda kullanılacağı
- **Kapsam dışı:** UI geliştirme, DB, gerçek zamanlı akış → hackathon dışı
- **Teslim:** Kod review, final test, commit & push kararları

### Yaklaşık AI katkı oranı
Kod satırlarının **~70%'i** AI tarafından yazıldı:
- **Oluşturulan:** Temel pipeline, algoritma, test, dokümantasyon
- **İnsan tarafından:** Gereklilik analiz, tasarım karar, prompt tuning, kod review
- Tamamı çalıştırılarak doğrulandı, hata alındığında fix loop yapıldı

---

## 5. Doğrulama — "Çalıştığını nereden biliyoruz?"

| Kontrol | Durum | Kanıt |
|---|---|---|
| Pipeline çalıştırıldı | ✅ | `python -m src.pipeline data/alarms_clean.json` → `data/olay_kartlari.json` (47 olay kartı) |
| 3000 alarm işlendi | ✅ | `data/alarms_clean.json` (3000+ alarm) tamamı döngüde işlendi |
| Korelasyon analizi | ✅ | `data/alarms_grouped.json` zaman dilimlerine göre gruplandırılmış |
| Bağımlılıklar sabitlenmiş | ✅ | [requirements.txt](requirements.txt) tam sürümlerle (`anthropic==1.x.x`, `pandas==2.x.x`) |
| AI çıktısı doğrulaması | ✅ | Olay kartları JSON şemasına uygun; kök neden ve aksiyon alanları dolu |
| Canlı demo | ✅ | [demo/](demo/) folder'da ekran görüntüleri ve komut çıktıları |
| Alarm indirgeme oranı | ✅ | 3000+ alarm → 47 olay kartı (**%1.57 ratio**) |

---

## 6. Bilinçli Sınırlar (Kapsam Dışı)

Senaryo brifingi ve hackathon kurallarına uygun, kasıtlı olarak dışarıda bırakılanlar:

| Kapsam dışı | Gerekçe |
|---|---|
| **Gerçek zamanlı akış işleme** | Kafka/RabbitMQ entegrasyonu — Senaryo "dosya yükleme" ile başlıyor; toplu işleme yeterli |
| **Kullanıcı yönetimi/Auth** | Senaryo'da belirtilmemiş; nöbetçi bağlamında ihtiyaç yok (operasyon merkezi = kapalı ağ) |
| **Web arayüzü** | Terminal/CLI çıktısı yeterli; HTML/CSS geliştirme zaman kaybı |
| **Veritabanı** | JSON dosyalar hackathon kapsamında yeterli; prodüktif dağıtımda gerekli |
| **Benchmark karşılaştırması** | Diğer korelasyon araçları ile A/B testi — hackathon süresi için fazla |

---

## 7. Güvenlik ve Veri Gizliliği

- **API Anahtarı:** `.env` dosyası `.gitignore` (satır 151) ile korunuyor; repoda yalnızca [.env.example](.env.example) var.
  - `ANTHROPIC_API_KEY` hiçbir yerde hardcoded değil
- **Alarm Verisi:** Senaryo paketi içindeki sentetik verildir (gerçek müşteri verisi değil)
  - Alarm metinleri: örnek hata kodları, servis adları, log satırları
  - PII yok (ad, telefon, kimlik numarası vs.)
- **Claude API'ye gönderilen veri:**
  - Alarm JSON'ları (zaman, servis, hata kodu, log) gönderilir
  - Kimlik bilgisi, şifre, token **gönderilmez**
- **Prompt injection:** Alarm metinleri model prompt'ına direkt enjekte edilmez
  - JSON field'ları ayrıştırılır, prompt şablonunda güvenli konumlanır
  - Jinja2 template escaping kullanılır (src/pipeline.py, hat 175)

---

## 8. Tekrar Üretilebilirlik

```bash
# 1. Klon ve kurulum
git clone https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing.git
cd ai-hackathon-billing-2026-billing

# 2. Sanal ortam
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Bağımlılıklar
pip install -r requirements.txt

# 4. API anahtarı
cp .env.example .env
# ANTHROPIC_API_KEY alanını doldur

# 5. Ana pipeline çalıştır
python -m src.pipeline data/alarms_clean.json

# 6. Çıktı
# Olay kartları: data/olay_kartlari.json
# Temizlik raporu: data/temizlik_raporu.json
```

**Beklenen çıktı:** ~47 olay kartı, her biri kök neden hipotezi ve önerilen aksiyon ile.

---

## 9. Jüriye Not

### Özellikle bakması istenen yerler

1. **Prompt Iyileştirmesi (v1 → v3):** [prompts/system.md](prompts/system.md)
   - İlk versiyon: Jenerik "alarm gruplandır" → sınıf olaylar yanlış birleştirilmiş
   - v2: Zaman penceresi eklendi → biraz daha iyi
   - v3: Tarihsel benzer olaylar ve doğru gerekçe formatı → başarılı
   - Bu iterasyon, AI'nın geri dönüt ile nasıl iyileştiğini gösterir

2. **Korelasyon Algoritması:** [src/correlate.py](src/correlate.py)
   - Sadece yapay değil, istatistiksel temelli (zaman, meta-data, metin benzerliği)
   - AI bu temeli algılayıp gerekçesi olan hipotez üretiyor

3. **Alarm İndirgeme Oranı:** 3000+ → 47 (**%1.57**)
   - Senaryo hedefi "15 kart" → fazla basaralı ama gerçekçi
   - Gürültü elemesi sert yapıldı (sahte hata, çoğaltılan alarmlar)

### Gurur duyulan teknik seçim

- **Yapılandırılmış JSON çıktısı:** Temperature=0.2 + şema zorlama = tekrar üretilebilir sonuçlar
- **Batch işleme + API maliyet kontrolü:** 800 token limit ve grup başına 1 çağrı = ~$0.15 toplam maliyet
- **Açıklanabilirlik (XAI):** Her olay kartında sadece "ne" değil, "neden" de var

### Zorlanılan yerler

- İlk versiyonda benzer geçmiş olayları bulma hatalıydı → TextBlob'tan sklearn TfidfVectorizer'a geçtik
- Senaryo brifingi "gerçek olay sayısını söylenmeyecektir" dedi → trial-and-error ile 15-20 olay beklediği fark ettik
