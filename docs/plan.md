# Plan — Ürün Kapsamı ve Hedefler

> Bu doküman "ne yapacağız ve neyi yapmayacağız" sorusunun cevabıdır.
> Faz faz ilerleme kaydı için [fazlar.md](fazlar.md), teknik tasarım için [mimari.md](mimari.md).

---

## 1. Hedef

**[DOLDURUN]** Hackathon sonunda elinizde ne olacak? Tek cümlelik, ölçülebilir hedef.

## 2. Problem Tanımı

| Soru | Cevap |
|---|---|
| Kim? | **[DOLDURUN]** hedef kullanıcı |
| Ne zaman / hangi durumda? | **[DOLDURUN]** tetikleyici senaryo |
| Şu an nasıl çözüyor? | **[DOLDURUN]** mevcut alternatif |
| Neden yetersiz? | **[DOLDURUN]** sancı noktası |

## 3. Kullanıcı Hikâyeleri

- [ ] **[DOLDURUN]** Bir _[kullanıcı]_ olarak, _[eylem]_ yapmak istiyorum ki _[fayda]_.
- [ ] **[DOLDURUN]**
- [ ] **[DOLDURUN]**

Öncelik sırası: yukarıdan aşağı. İlk madde MVP'nin çekirdeğidir.

---

## 4. Kapsam

### 4.1 Kapsam İçi (MVP)

| # | Özellik | Neden gerekli | Durum |
|---|---|---|---|
| 1 | **[DOLDURUN]** | | ⬜ |
| 2 | **[DOLDURUN]** | | ⬜ |
| 3 | **[DOLDURUN]** | | ⬜ |

### 4.2 Kapsam Dışı (Bilinçli Sınırlar)

Net sınır çizmek hackathonda artı puandır — her satırın gerekçesi olmalı.

| Yapılmayacak | Gerekçe |
|---|---|
| **[DOLDURUN]** | **[DOLDURUN]** |
| **[DOLDURUN]** | **[DOLDURUN]** |

### 4.3 Yapılırsa İyi Olur (Nice-to-have)

- **[DOLDURUN]**

---

## 5. Başarı Kriterleri

Demo günü "başardık" diyebilmek için karşılanması gereken, ölçülebilir koşullar.

| # | Kriter | Nasıl ölçülür | Durum |
|---|---|---|---|
| 1 | **[DOLDURUN]** | **[DOLDURUN]** | ⬜ |
| 2 | **[DOLDURUN]** | **[DOLDURUN]** | ⬜ |

---

## 6. Veri

| Soru | Cevap |
|---|---|
| Veri kaynağı | **[DOLDURUN]** gerçek / anonimleştirilmiş / sentetik |
| Format | **[DOLDURUN]** CSV / JSON / DB |
| Hacim | **[DOLDURUN]** |
| Kişisel veri içeriyor mu? | **[DOLDURUN]** içeriyorsa nasıl maskeleniyor |

---

## 7. Riskler ve Önlemler

| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| Model çıktısı tutarsız/halüsinasyonlu | **[DOLDURUN]** | **[DOLDURUN]** | Yapılandırılmış çıktı (JSON şema) + doğrulama katmanı |
| API kotası/maliyeti aşılır | **[DOLDURUN]** | **[DOLDURUN]** | Token limiti, prompt caching, örneklem üzerinde test |
| Demo anında API erişilemez | **[DOLDURUN]** | **[DOLDURUN]** | Önceden kaydedilmiş örnek çıktı + demo videosu |
| **[DOLDURUN]** | | | |

---

## 8. Zaman Planı

Detaylı faz kaydı [fazlar.md](fazlar.md) dosyasında tutulur.

| Faz | Kapsam | Hedef tarih |
|---|---|---|
| Faz 0 — Kurulum | Repo iskeleti, bağımlılıklar, çalışan örnek | 2026-09-15 ✅ |
| Faz 1 — **[DOLDURUN]** | | **[DOLDURUN]** |
| Faz 2 — **[DOLDURUN]** | | **[DOLDURUN]** |
| Faz 3 — Demo & teslim | Demo kaydı, dokümantasyon, submission.json | **[DOLDURUN]** |
