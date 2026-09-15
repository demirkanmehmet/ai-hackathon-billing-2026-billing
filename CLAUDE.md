# CLAUDE.md - Geliştirme ve AI Ajan Rehberi

Bu dosya, yapay zekâ ajanının (Claude/Cursor) uyacağı çalışma kurallarını ve AI Jürisi için geliştirme sürecinin kanıtlarını içerir.

## Proje Bilgileri

- **Proje Adı**: AI Hackathon 2026
- **Takım Adı**: Bill& Chill
- **Başlama Tarihi**: 2026-09-15
- **Birincil Yapay Zekâ Platformu**: SAKA (Turkcell Multi-LLM Platformu)
- **Kullanılan Modeller**: Claude 3.5 Sonnet / Claude 3 Opus (SAKA üzerinden)

---

## 🛑 Yapay Zekâ Ajanı Otomatik Çalışma Kuralları (Agent Directives)

*Ajan (Claude/Cursor), bu projedeki her işleminde aşağıdaki adımları otomatik olarak uygulamakla yükümlüdür:*

1. **Kod Yönetimi**: Tüm kaynak kodlar istisnasız `src/` klasörü altına yazılacaktır.
2. **Prompts Kaydı (Zorunlu Puan)**: Üretilen her modül, kritik yönlendirme veya karmaşık algoritma sonrasında prompt kaydı `prompts/` klasörüne eklenmelidir (`prompts/ai_activity_log.md` veya `prompts/<gorev_adi>.md`).
3. **Dokümantasyon Güncellemesi**: Mimari kararlar `docs/mimari.md`, aşamalar `docs/plan.md` dosyalarına işlenmelidir.
4. **Kanıt Eşleme**: `src/` içinde tamamlanan her kritik mantık için `AI_JURI.md` dosyasındaki dosya yolu ve satır aralığı kanıtı (`Kanıt: src/<dosya>:<satır_aralığı>`) güncellenmelidir.
5. **Güvenlik**: Gerçek veri kullanılmamalı, hassas değişkenler `.env.example` içinde tanımlanmalı, `.env` kesinlikle commit edilmemelidir.

---

## Geliştirme İş Akışı ve Rol Dağılımı

### Yapay Zekâ (SAKA / Claude) Sorumlulukları
- `src/` altındaki kod modüllerinin üretimi ve refactoring işlemleri
- Karar mekanizmaları için Açıklanabilirlik (XAI) ve gerekçe metinlerinin üretilmesi
- `prompts/` dizinindeki yönlendirme dosyalarının oluşturulması
- Dokümantasyon (`README.md`, `docs/`) ve birim test yazımı

### İnsan (Takım) Kararları ve Sorumlulukları
- Senaryo analizi ve veri şeması üzerindeki hipotez seçimi
- Mimari tasarım, modül sınırlarının çizilmesi ve X-Factor tespiti
- AI modelleri arasında çıktı karşılaştırması ve nihai onay
- Sahne sunumu, canlı demo akış tasarımı