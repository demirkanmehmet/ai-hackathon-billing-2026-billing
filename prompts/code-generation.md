# Kod Üretimi Prompt'ları — Geliştirme Süreci

Claude Code ile çalışırken kullanılan prompt'lar. Kalıcı kurallar [CLAUDE.md](../CLAUDE.md)
dosyasında tanımlıdır ve her oturumda otomatik yüklenir.

---

## Gerçekten Kullanılanlar

### 1. Örnek fatura scripti (Faz 0) — kullanıldı ✅

```text
örnek bir python kodu dene kütüphane install gereksin install et, kodu run et
ve github commit ve push işlemlerini tamamla.
```

**Sonuç:** [src/example_billing.py](../src/example_billing.py) + [requirements.txt](../requirements.txt),
çalıştırılarak doğrulandı, commit `669dfc2`.

### 2. Repo iskeleti (Faz 0) — kullanıldı ✅

```text
projemde eksik dizin dosya vs ekle
<hackathon zorunlu dizin yapısı>
```

**Sonuç:** Bu dizin dahil tüm zorunlu dosya/dizinler oluşturuldu.

### 3. **[DOLDURUN]**

```text
[DOLDURUN] Kullandığınız prompt'u aynen buraya yapıştırın.
```

**Sonuç:** **[DOLDURUN]**

---

## Şablonlar

Tekrar kullanmak için hazır kalıplar.

### Yeni modül

```text
[dosya yolu] içine [görev] yapan bir modül yaz.

Bağlam:
- Mevcut kod stili: [referans dosya]
- Bağımlılık: yalnızca requirements.txt'de olanlar

Gereksinimler:
- [gereksinim 1]
- Parasal değerlerde Decimal kullan, float kullanma
- Hata durumunda [davranış]

Yazdıktan sonra çalıştır ve çıktısını göster.
```

### Refactor

```text
[dosya] dosyasını [hedef] için refactor et.
Davranışı DEĞİŞTİRME — sadece yapıyı iyileştir.
Değişiklikten sonra mevcut testleri çalıştır ve geçtiklerini doğrula.
```

### Test yazma

```text
[dosya] için pytest testleri yaz.
Kapsa: mutlu yol, sınır durumlar (sıfır adet, negatif tutar, yuvarlama),
hatalı girdi. Testleri çalıştır ve sonucu göster.
```

---

## Notlar

- **İşe yarayan:** **[DOLDURUN]** ör. "çalıştır ve çıktısını göster" demek, doğrulanmamış
  kod teslim edilmesini engelledi.
- **İşe yaramayan:** **[DOLDURUN]** Başarısız prompt denemelerini de yazın.
