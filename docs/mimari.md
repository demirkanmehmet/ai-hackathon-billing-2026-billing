# Mimari — Teknik Tasarım ve Kararlar

> Kapsam ve hedefler için [plan.md](plan.md), ilerleme kaydı için [fazlar.md](fazlar.md).

---

## 1. Genel Bakış

**[DOLDURUN]** Sistemi 3-4 cümleyle anlatın: hangi parçalar var, hangisi neyi yapıyor.

```
[DOLDURUN] — Bileşen diyagramı. Örnek iskelet:

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Girdi      │────▶│   İşleme     │────▶│    Çıktı     │
  │ (fatura      │     │ (hesaplama + │     │ (rapor /     │
  │  verisi)     │     │  AI analizi) │     │  uyarılar)   │
  └──────────────┘     └──────┬───────┘     └──────────────┘
                              │
                       ┌──────▼───────┐
                       │  Claude API  │
                       └──────────────┘
```

---

## 2. Bileşenler

| Bileşen | Dosya/Dizin | Sorumluluk |
|---|---|---|
| Örnek hesaplama | [src/example_billing.py](../src/example_billing.py) | `Decimal` ile kalem/KDV/toplam hesabı, `rich` ile tablo çıktısı |
| **[DOLDURUN]** veri okuma | `src/...` | **[DOLDURUN]** |
| **[DOLDURUN]** AI istemcisi | `src/...` | Claude API çağrısı, prompt derleme, yanıt doğrulama |
| **[DOLDURUN]** sunum | `src/...` | **[DOLDURUN]** CLI / web arayüzü |

---

## 3. Veri Akışı

**[DOLDURUN]** Bir isteğin baştan sona izlediği yol, adım adım:

1. **[DOLDURUN]** Kullanıcı ... sağlar
2. **[DOLDURUN]** Sistem ... doğrular / normalize eder
3. **[DOLDURUN]** ... Claude API'ye gönderilir
4. **[DOLDURUN]** Yanıt ... şemasına göre doğrulanır
5. **[DOLDURUN]** Sonuç kullanıcıya ... olarak sunulur

---

## 4. AI Entegrasyonu

| Konu | Karar |
|---|---|
| Sağlayıcı | Anthropic Claude API |
| Model | **[DOLDURUN]** |
| Neden bu model | **[DOLDURUN]** hız / maliyet / yetenek dengesi |
| Çağrı biçimi | **[DOLDURUN]** tek atış / tool use / agent döngüsü |
| Çıktı formatı | **[DOLDURUN]** serbest metin / JSON şema (`tool_use` ile zorunlu kılınmış) |
| Temperature | **[DOLDURUN]** — sayısal analizde 0.0 önerilir |
| Prompt kaynağı | [prompts/](../prompts/) |
| Yanıt doğrulama | **[DOLDURUN]** şema doğrulaması, aralık kontrolü, toplamların yeniden hesaplanması |
| Hata yönetimi | **[DOLDURUN]** retry, timeout, fallback davranışı |
| Maliyet kontrolü | **[DOLDURUN]** prompt caching, `max_tokens`, batch |

### Halüsinasyon önlemleri
**[DOLDURUN]** Parasal değerlerde modele güvenilmiyorsa bunu yazın — ör. "toplamlar
deterministik Python kodunda `Decimal` ile hesaplanır; model yalnızca açıklama/sınıflandırma
üretir." Bu ayrımı net yapmak jüri için önemlidir.

---

## 5. Teknik Kararlar (ADR)

### KR-001 — Parasal hesaplamalarda `Decimal`
- **Karar:** `float` yerine `decimal.Decimal` + `ROUND_HALF_UP`.
- **Gerekçe:** `float` ikili kayan nokta hatası nedeniyle parasal toplamlarda kuruş sapması üretir.
- **Sonuç:** Hesaplamalar tekrar üretilebilir; `src/example_billing.py` bu kuralı uygular.

### KR-002 — Bağımlılıkların sabitlenmesi
- **Karar:** `requirements.txt` içinde tam sürüm (`rich==14.1.0`).
- **Gerekçe:** Jürinin temiz bir klonda aynı sonucu alabilmesi.
- **Sonuç:** Kurulum tekrar üretilebilir.

### KR-003 — **[DOLDURUN]**
- **Karar:** **[DOLDURUN]**
- **Gerekçe:** **[DOLDURUN]**
- **Alternatifler:** **[DOLDURUN]** ve neden seçilmediği
- **Sonuç:** **[DOLDURUN]**

---

## 6. Dizin Yapısı

```
src/
├── example_billing.py     # örnek hesaplama (iskelet doğrulaması)
└── [DOLDURUN]             # asıl uygulama modülleri
```

**[DOLDURUN]** Modülleri nasıl böldünüz ve neden?

---

## 7. Güvenlik

- **Sırlar:** Ortam değişkenleriyle yönetiliyor; `.env` `.gitignore`'da (satır 151). Repoda
  yalnızca [.env.example](../.env.example) bulunur.
- **PII / KVKK:** **[DOLDURUN]** Fatura verisinde kişisel veri var mı, modele gitmeden önce
  maskeleniyor mu?
- **Prompt injection:** **[DOLDURUN]** Kullanıcı girdisi prompt'a giriyorsa nasıl izole ediliyor?
- **Girdi doğrulama:** **[DOLDURUN]**

---

## 8. Test Stratejisi

| Katman | Dizin | Ne test ediliyor |
|---|---|---|
| Unit | `tests/unit/` | **[DOLDURUN]** hesaplama fonksiyonları (`para`, `fatura_topla`), yuvarlama sınır durumları |
| Entegrasyon | `tests/integration/` | **[DOLDURUN]** modüller arası akış, AI istemcisi (mock yanıtla) |
| E2E | `tests/e2e/` | **[DOLDURUN]** uçtan uca senaryo |

**AI çağrıları testlerde nasıl ele alınıyor?** **[DOLDURUN]** (mock / kayıtlı yanıt / canlı çağrı)

---

## 9. Performans ve Ölçek

**[DOLDURUN]** Beklenen veri hacmi, yanıt süresi hedefi, darboğaz tahmini. Hackathon
kapsamında ölçek hedefi yoksa bunu açıkça yazın.

---

## 10. Teknik Borç

Bilinçli olarak ertelenenler:

| Konu | Neden ertelendi | Gerçek üründe ne gerekir |
|---|---|---|
| **[DOLDURUN]** | **[DOLDURUN]** | **[DOLDURUN]** |
