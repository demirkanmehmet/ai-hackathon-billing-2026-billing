# Alarm Fırtınası — AI Hackathon 2026

> Operasyon merkezindeki binlerce alarma makine öğrenmesi ve AI entegrasyonu ile anlam katan,
> nöbetçi mühendis için harekete geçebilir kararlar üreten alarm korelasyon sistemi.

| | |
|---|---|
| **Takım** | Bill & Chill |
| **Kategorisi** | Operasyon / Anomali Tespiti |
| **Repo** | https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing |
| **Demo** | Canlı terminal demo — bkz. `demo/` |
| **Durum** | Teslime hazır |

---

## 1. Problem

**Sahne:** Eylül gecesi, saat 02:14. Operasyon merkezindeki alarm sistemi çöküyor: dört saatlik
pencerede **3.000+ alarm** birbirini kovalıyor. Nöbetçi mühendis ekrana baktığında ayırt edemediği
şeyler var:
- Hangi alarm **kök neden**?
- Hangisi **türev sonuç** (başka alarmdan tetiklenen)?
- Hangisi **gürültü** (alakasız)?

**Bugünkü çözümün sancısı:** Alarmları bir bir okuyarak manuel korelasyon kurmak. Müdahale sırası
yanlış kurulur → çözüm süresi **saatler** tutar. İş kayıpları, müşteri şikayetleri.

---

## 2. Çözüm

**Ne inşa ettik:** AI destekli **Alarm Korelasyon ve İndirgemesi Sistemi**.

**Kullanıcı akışı:**
1. 3.000+ alarm JSON dosyası sisteme yüklenir
2. Sistem alarmlara **korelasyon analizi** uygular (zaman, meta-data, ilişki modelleri)
3. Claude AI, alarmları **anlamlı olaylara gruplandırır** ve her grup için:
   - **Kök neden hipotezi** (neden böyle oldu?)
   - **Etkilenen servisler** listesi
   - **Önerilen ilk aksiyon** (ne yapılmalı?)
4. İndirgeme sonucu: 3.000 alarm → **~15 olay kartı**
5. Nöbetçi mühendis bu kartları okuyup **dakika içinde** harekete geçer

**AI'ın rolü:**
- **Alarm Analizi:** Zaman, metrik, servis ilişkilerinden korelasyon modeli çıkarma
- **Neden-Sonuç Modelleme:** "Database bağlantı timeout" → "tüm API hataları" → "frontend timeout" zincirini anlatma
- **Söylemsel Açıklama:** Mühendisin anlayacağı doğal dilde gerekçeler üretme
- **Anomali Sınıflandırması:** Benzer geçmiş olaylarla karşılaştırma

## 3. Neden Önemli / Fark Yaratan Yan

**Klasik kural tabanlı yaklaşım:** "Eğer alarm X ve Y aynı dakikada gelirse, grup et" → Sabit,
yanlış pozitif yüksek.

**AI yaklaşımı:** Veriye bakıp dinamik olarak öğreniyor. Her olaya **gerekçe sumuyor** —
nöbetçi mühendis bu gerekçeyi okuyor ve **bağlamını anladığı için** güvenle hareket ediyor.
**İnsanın kontrolü** hep başta: AI önerir, insan karar verir.

---

## Hızlı Başlangıç

### Gereksinimler

- Python 3.11+
- `pip`
- Anthropic Claude API anahtarı

### Kurulum

```bash
git clone https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing.git
cd ai-hackathon-billing-2026-billing

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Ortam Değişkenleri

```bash
cp .env.example .env
# ANTHROPIC_API_KEY alanını doldur
```

> `.env` dosyası `.gitignore` ile korunuyor ve **asla** commit edilmez.

### Çalıştırma

#### 1. Alarm Korelasyon Pipeline'ı

Alarm dosyasını işle ve olay kartları oluştur:

```bash
python -m src.pipeline data/alarms_clean.json
```

Çıktı: `data/olay_kartlari.json` (anlamlı olaylar ve kök neden hipotezleri)

#### 2. Korelasyon Analizi

```bash
python -m src.correlate data/alarms_clean.json data/olay_kartlari.json
```

Alarmlar arasındaki ilişkileri göster.

#### 3. İşlenmiş Verileri Zenginleştir

```bash
python -m src.enrich_alarms data/alarms_clean.json data/olay_kartlari.json
```

Her alarma meta-bilgi ve bağlam ekle.

---

## Proje Yapısı

```
ai-hackathon-billing-2026-billing/
├── README.md              # bu dosya
├── AI_JURI.md             # AI Jüri için yapılandırılmış özet
├── submission.json        # makine okunabilir künye
├── .env.example           # ortam değişkeni şablonu
├── CLAUDE.md              # AI asistan rehberi
├── requirements.txt       # Python bağımlılıkları
├── data/
│   ├── alarms_clean.json              # temiz alarm verisi (~3000 alarm)
│   ├── alarms_processed.json          # işlenmiş alarmlar
│   ├── alarms_grouped.json            # zaman dilimlerine göre gruplandırılmış
│   ├── olay_kartlari.json             # AI tarafından üretilen olay kartları
│   └── pipeline/                      # pipeline ara verileri
├── docs/
│   ├── plan.md            # ürün planı ve kapsam
│   ├── fazlar.md          # faz faz ilerleme kaydı
│   └── mimari.md          # teknik mimari ve kararlar
├── prompts/               # kullanılan kritik prompt'lar
│   ├── system.md          # sistem prompt (Olay Analiziyle İlgili)
│   ├── code-generation.md # geliştirme prompt'ları
│   └── analysis.md        # korelasyon ve kök neden tespiti
├── demo/                  # ekran görüntüleri ve demo
└── src/                   # kaynak kod
    ├── pipeline.py        # ana işlem hattı
    ├── correlate.py       # alarm korelasyonu
    ├── enrich_alarms.py   # veri zenginleştirme
    └── add_kaynak_servis.py # servis meta-data ekleme
```

---

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [AI_JURI.md](AI_JURI.md) | AI kullanımının yapılandırılmış özeti |
| [docs/plan.md](docs/plan.md) | Kapsam, hedefler, başarı kriterleri |
| [docs/fazlar.md](docs/fazlar.md) | Faz faz ilerleme ve zaman çizelgesi |
| [docs/mimari.md](docs/mimari.md) | Sistem mimarisi, veri akışı, teknik kararlar |
| [prompts/](prompts/) | Üretimde kullanılan AI prompt'ları |
| [CLAUDE.md](CLAUDE.md) | AI asistan ile çalışma kuralları |

---

## Kütüphaneler

- **Claude API** (Anthropic): Alarm korelasyon analizi ve kök neden tespiti
- **pandas**: Veri işleme ve analiz
- **numpy**: Sayısal hesaplamalar
- **python-dateutil**: Zaman işlemleri

---

## Bilinen Sınırlamalar

Bilinçli olarak kapsam dışı bırakılanlar:

- **Gerçek zamanlı akış işleme:** Yüksek frekans akışları için optimize edilmemiştir. Toplu işleme (batch) için tasarlanmıştır.
- **Kullanıcı yönetimi ve oturum:** Hackathon kapsamında yetkilendirme uygulanmamıştır.
- **Kalıcı veritabanı:** Veriler bellek içinde ve JSON dosyalarında saklanır; prodüktif dağıtım için veritabanı gereklidir.

## Sonraki Adımlar

- [ ] Kalıcı veritabanı entegrasyonu (PostgreSQL)
- [ ] Gerçek zamanlı Kafka/RabbitMQ desteği
- [ ] Web dashboard arayüzü
- [ ] Benzer geçmiş olayları veri tabanında indexleme

---

## Takım

| İsim | Rol | GitHub |
|---|---|---|
| Mehmet Demirkan | Pipeline ve korelasyon modeli | [@demirkanmehmet](https://github.com/demirkanmehmet) |
| Furkan Bayram | AI prompt ve açıklanabilirlik | |
| Murat Kaan Aksoy | Veri ön işleme ve analiz | |

## Lisans

MIT
