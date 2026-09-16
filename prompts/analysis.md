# Analiz Prompt'ları

Fatura/veri analizi görevlerinde modele verilen prompt'lar.

**Kullanıldığı yer:** **[DOLDURUN]** `src/...`
**Model:** **[DOLDURUN]**

---

## 1. Fatura Kalemi Sınıflandırma

```text
[DOLDURUN] — İskelet:

Aşağıdaki fatura kalemlerini kategorilere ayır.

Kalemler:
{kalemler}

Kategoriler: [DOLDURUN: kategori listesi]

Kurallar:
- Her kalemi tam olarak bir kategoriye ata.
- Kategorisi belirsizse "diger" kullan ve gerekçe yaz.
- Tutarları değiştirme veya yeniden hesaplama.

Çıktı (yalnızca JSON):
{
  "kalemler": [
    {"aciklama": "...", "kategori": "...", "guven": 0.0, "gerekce": "..."}
  ]
}
```

**Doğrulama:** **[DOLDURUN]** Çıktı şemaya göre doğrulanıyor mu? Kalem sayısı girdiyle
eşleşiyor mu kontrol ediliyor mu?

---

## 2. Anormallik Tespiti

```text
[DOLDURUN] — İskelet:

Müşterinin son {n} aylık fatura geçmişi ve bu ayki faturası aşağıda.

Geçmiş: {gecmis}
Bu ay:  {bu_ay}

Bu ayki faturada dikkat çeken sapmaları listele.

Kurallar:
- Yüzdelik değişimleri sen hesaplama; sana verilmiş olanları kullan.
- Yalnızca veriyle desteklenen sapmaları bildir.
- Sapma yoksa boş liste döndür; zorlama.

Çıktı (yalnızca JSON):
{
  "sapmalar": [
    {"kalem": "...", "aciklama": "...", "onem": "dusuk|orta|yuksek"}
  ]
}
```

**Doğrulama:** **[DOLDURUN]**

---

## 3. Müşteriye Açıklama Üretimi

```text
[DOLDURUN] — İskelet:

Aşağıdaki fatura farkını müşterinin anlayacağı sade bir Türkçeyle açıkla.

Veri: {fark_detayi}

Kurallar:
- En fazla 3 cümle.
- Teknik jargon kullanma.
- Rakamları veriden aynen aktar; yuvarlama veya yeniden hesaplama yapma.
- Özür dileme veya taahhütte bulunma.
```

**Doğrulama:** **[DOLDURUN]**

---

## Ortak İlkeler

Bu dizindeki tüm analiz prompt'larında geçerli:

1. **Model hesap yapmaz.** Tüm parasal hesaplar `Decimal` ile Python tarafında yapılır;
   modele hesaplanmış değerler verilir. Gerekçe: [docs/mimari.md](../docs/mimari.md).
2. **Yapılandırılmış çıktı.** Serbest metin yerine JSON şema — programatik doğrulanabilsin.
3. **Boş sonuç meşrudur.** Model "bulunamadı" diyebilmeli; bulgu uydurmaya zorlanmamalı.
4. **Düşük temperature.** Analiz görevlerinde `0.0`.
