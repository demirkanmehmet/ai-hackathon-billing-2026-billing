# Bill & Chill — AI Hackathon 2026

> **[DOLDURUN]** Projeyi bir cümleyle anlatan tagline.
> Örn: "Kurumsal telekom faturalarını AI ile analiz edip anormal kalemleri işaretleyen asistan."

| | |
|---|---|
| **Takım** | Bill & Chill |
| **Kategori** | Billing |
| **Repo** | https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing |
| **Demo** | **[DOLDURUN]** video/canlı demo linki → `demo/` |
| **Durum** | Geliştirme aşamasında |

---

## 1. Problem

**[DOLDURUN]** Hangi gerçek problemi çözüyorsunuz? Kim bu problemi yaşıyor ve bugün nasıl
çözüyor? Mevcut çözümün maliyeti/sancısı nedir?

## 2. Çözüm

**[DOLDURUN]** Ne inşa ettiniz? Kullanıcı hangi adımları izliyor, karşılığında ne alıyor?
AI'ın çözümdeki rolü tam olarak nedir (sadece "AI kullandık" değil — hangi karar noktasında,
hangi girdiyle, hangi çıktıyı üretiyor)?

## 3. Neden Önemli / Fark Yaratan Yan

**[DOLDURUN]** Bu yaklaşımın klasik kural tabanlı bir çözümden farkı nedir?

---

## Hızlı Başlangıç

### Gereksinimler

- Python 3.11+ (geliştirme ortamı: 3.13)
- `pip`

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
# .env dosyasını kendi anahtarlarınızla doldurun
```

> `.env` dosyası `.gitignore` ile korunuyor ve **asla** commit edilmez.
> Hangi değişkenin ne işe yaradığı için [.env.example](.env.example) dosyasına bakın.

### Çalıştırma

```bash
# Örnek fatura hesaplama scripti (iskelet doğrulaması)
python src/example_billing.py
```

Beklenen çıktı:

```
               Ornek Fatura / Bill & Chill
+--------------------------------------------------------+
| Aciklama              | Adet | Birim Fiyat |     Tutar |
|-----------------------+------+-------------+-----------|
| Mobil paket - 20 GB   |    1 |   349.90 TL | 349.90 TL |
| Ek data paketi - 5 GB |    2 |    79.50 TL | 159.00 TL |
| Yurt disi arama (dk)  |   14 |     3.25 TL |  45.50 TL |
+--------------------------------------------------------+
Ara toplam : 554.40 TL
KDV (%20)  : 110.88 TL
Genel toplam: 665.28 TL
```

**[DOLDURUN]** Asıl uygulamanın çalıştırma komutu (ör. `python -m src.main`, `streamlit run ...`).

---

## Proje Yapısı

```
ai-hackathon-billing-2026-billing/
├── README.md              # bu dosya
├── AI_JURI.md             # AI Jüri için yapılandırılmış özet
├── submission.json        # makine okunabilir künye
├── .env.example           # ortam değişkeni şablonu (gerçek .env commit EDİLMEZ)
├── CLAUDE.md              # AI asistan geliştirme rehberi / iş akışı
├── requirements.txt       # Python bağımlılıkları
├── docs/
│   ├── plan.md            # ürün planı ve kapsam
│   ├── fazlar.md          # faz faz ilerleme kaydı
│   └── mimari.md          # teknik mimari ve kararlar
├── prompts/               # kullanılan kritik prompt'lar
│   ├── system.md
│   ├── code-generation.md
│   └── analysis.md
├── demo/                  # ekran görüntüleri ve demo videosu
└── src/                   # kaynak kod
    └── example_billing.py
```

---

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [AI_JURI.md](AI_JURI.md) | AI kullanımının yapılandırılmış özeti |
| [docs/plan.md](docs/plan.md) | Kapsam, hedefler, başarı kriterleri |
| [docs/fazlar.md](docs/fazlar.md) | Faz faz ilerleme ve zaman çizelgesi |
| [docs/mimari.md](docs/mimari.md) | Sistem mimarisi, veri akışı, teknik kararlar |
| [prompts/](prompts/) | Üretimde kullanılan prompt'lar |
| [CLAUDE.md](CLAUDE.md) | AI asistan ile çalışma kuralları |

---

## Test

```bash
# [DOLDURUN] test komutu, ör:
# pytest tests/ -v
```

**[DOLDURUN]** Test stratejisi özeti — bkz. [CLAUDE.md](CLAUDE.md).

---

## Bilinen Sınırlamalar

Bilinçli olarak kapsam dışı bırakılanlar (gerekçeleriyle birlikte):

- **[DOLDURUN]** Sınır 1 — neden dışarıda bırakıldı
- **[DOLDURUN]** Sınır 2 — neden dışarıda bırakıldı

## Sonraki Adımlar

- [ ] **[DOLDURUN]**
- [ ] **[DOLDURUN]**

---

## Takım

| İsim | Rol | GitHub |
|---|---|---|
| Mehmet Demirkan | **[DOLDURUN]** | [@demirkanmehmet](https://github.com/demirkanmehmet) |
| **[DOLDURUN]** | | |

## Lisans

**[DOLDURUN]** (ör. MIT)
