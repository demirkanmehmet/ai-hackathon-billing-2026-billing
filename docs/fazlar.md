# Fazlar — İlerleme Kaydı

> Her faz için: **ne yapıldı**, **AI ne yaptı**, **insan neye karar verdi**, **nasıl doğrulandı**.
> Jüri bu dosyadan sürecin gerçekten nasıl işlediğini okur — sonradan toplu yazmak yerine
> faz bittikçe doldurun.

Durum anahtarı: ✅ tamamlandı · 🔄 devam ediyor · ⬜ başlanmadı · ❌ iptal

---

## Genel Durum

| Faz | Başlık | Durum | Tarih |
|---|---|---|---|
| 0 | Kurulum ve iskelet | ✅ | 2026-09-15 |
| 1 | **[DOLDURUN]** | ⬜ | |
| 2 | **[DOLDURUN]** | ⬜ | |
| 3 | Demo ve teslim | ⬜ | |

---

## Faz 0 — Kurulum ve İskelet ✅

**Tarih:** 2026-09-15 – 2026-09-16

### Yapılanlar
- Repo iskeleti oluşturuldu (zorunlu dosyalar, `docs/`, `prompts/`, `demo/`, `src/`).
- Python ortamı doğrulandı (3.13) ve `requirements.txt` ile bağımlılık sabitlendi (`rich==14.1.0`).
- `src/example_billing.py` eklendi: `Decimal` tabanlı fatura hesaplama (ara toplam → KDV → genel toplam),
  `rich` ile tablo çıktısı.
- `.env.example` yazıldı; `.env` `.gitignore` ile korunuyor.

### AI'ın katkısı
- Örnek Python scriptinin üretimi ve `requirements.txt` oluşturulması.
- Dokümantasyon iskeletlerinin yazılması (README, AI_JURI, docs, prompts).

### İnsan kararları
- Kapsamın belirlenmesi ("örnek kod + kütüphane kurulumu + çalıştırma + push").
- `main` branch'e doğrudan push kararı.

### Doğrulama
```
$ python src/example_billing.py
Ara toplam : 554.40 TL
KDV (%20)  : 110.88 TL
Genel toplam: 665.28 TL
```
Commit: `669dfc2`

### Öğrenilenler / Takılınanlar
- **[DOLDURUN]** (yoksa "Yok" yazın)

---

## Faz 1 — **[DOLDURUN]** ⬜

**Tarih:** **[DOLDURUN]**

### Hedef
**[DOLDURUN]** Bu fazın sonunda ne çalışır durumda olacak?

### Yapılanlar
- **[DOLDURUN]**

### AI'ın katkısı
- **[DOLDURUN]** Hangi prompt kullanıldı? → [prompts/](../prompts/)

### İnsan kararları
- **[DOLDURUN]**

### Doğrulama
**[DOLDURUN]** Test çıktısı, ekran görüntüsü veya komut çıktısı.

### Öğrenilenler / Takılınanlar
- **[DOLDURUN]** Çalışmayan yaklaşımlar da yazın — jüri için değerlidir.

---

## Faz 2 — **[DOLDURUN]** ⬜

**Tarih:** **[DOLDURUN]**

### Hedef
**[DOLDURUN]**

### Yapılanlar
- **[DOLDURUN]**

### AI'ın katkısı
- **[DOLDURUN]**

### İnsan kararları
- **[DOLDURUN]**

### Doğrulama
**[DOLDURUN]**

### Öğrenilenler / Takılınanlar
- **[DOLDURUN]**

---

## Faz 3 — Demo ve Teslim ⬜

**Tarih:** **[DOLDURUN]**

### Kontrol listesi
- [ ] `README.md` tüm `[DOLDURUN]` alanları dolduruldu
- [ ] `AI_JURI.md` tamamlandı
- [ ] `submission.json` geçerli JSON ve güncel (`submitted_at` dolu)
- [ ] `.env.example` güncel, gerçek `.env` commit edilmemiş
- [ ] `docs/plan.md`, `docs/fazlar.md`, `docs/mimari.md` güncel
- [ ] `prompts/` içinde gerçekten kullanılan prompt'lar var
- [ ] `demo/` içinde ekran görüntüleri ve/veya video linki var
- [ ] Temiz bir klonda kurulum + çalıştırma adımları test edildi
- [ ] Testler geçiyor
