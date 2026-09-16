# prompts/

Projede **gerçekten kullanılan** kritik prompt'lar. Jüri bu dizinden AI'ı nasıl
yönlendirdiğinizi okur — sonradan güzelleştirilmiş değil, çalıştırdığınız hâlini koyun.

## Dosyalar

| Dosya | Amaç | Nerede kullanılıyor |
|---|---|---|
| [system.md](system.md) | Ürün içindeki modele verilen sistem talimatı | **[DOLDURUN]** `src/...` |
| [code-generation.md](code-generation.md) | Geliştirme sırasında kod üretimi için | Claude Code |
| [analysis.md](analysis.md) | Fatura/veri analizi görevleri için | **[DOLDURUN]** `src/...` |

## Kurallar

1. **Gerçek prompt'ları koyun.** Kısaltılmış veya sonradan düzenlenmiş sürüm değil.
2. **Sırları temizleyin.** API anahtarı, müşteri adı, gerçek fatura numarası bırakmayın.
3. **Değişkenleri işaretleyin.** Şablon değişkenleri için `{degisken_adi}` kullanın.
4. **Sürüm notu düşün.** Prompt'u değiştirdiyseniz neden değiştirdiğinizi yazın —
   "v1 toplamları yanlış okuyordu, v2'de tablo formatını örnekle gösterdik" gibi notlar
   jüri için değerlidir.
