# AI_JURI.md — AI Jüri Değerlendirme Özeti

Bu dosya, AI Jürisinin projeyi ve AI kullanımını hızlıca değerlendirebilmesi için
yapılandırılmış bir özettir. Her başlık altına somut, doğrulanabilir bilgi yazın.

---

## 0. Künye

| Alan | Değer |
|---|---|
| Proje adı | **[DOLDURUN]** |
| Takım | Bill & Chill |
| Kategori | Billing |
| Repo | https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing |
| Başlangıç | 2026-09-15 |
| Ana dil / stack | Python 3.13 |

---

## 1. Tek Cümlelik Özet

**[DOLDURUN]** Proje ne yapıyor? (Tek cümle, jargonsuz.)

---

## 2. Problem ve Çözüm

### Problem
**[DOLDURUN]** Çözülen gerçek problem, kim yaşıyor, bugünkü alternatifin sancısı.

### Çözüm
**[DOLDURUN]** Sizin yaklaşımınız ve kullanıcının gördüğü akış.

### AI olmasaydı?
**[DOLDURUN]** Bu problem kural tabanlı/klasik yöntemle çözülebilir miydi? Neden AI gerekli?
(Bu soru puan getirir — "AI'ı süs olarak kullanmadık" iddianızı burada kanıtlayın.)

---

## 3. AI Kullanımı — Üründe

Ürünün **çalışma zamanında** AI'ı nasıl kullandığı.

| Alan | Değer |
|---|---|
| Sağlayıcı | Anthropic Claude API |
| Model(ler) | **[DOLDURUN]** (ör. `claude-sonnet-4`) |
| Kullanım noktası | **[DOLDURUN]** hangi adımda çağrılıyor |
| Girdi | **[DOLDURUN]** modele ne veriliyor |
| Çıktı | **[DOLDURUN]** modelden ne bekleniyor (serbest metin / JSON şema / tool call) |
| Deterministiklik | **[DOLDURUN]** temperature, yapılandırılmış çıktı kullanılıyor mu |
| Hata/fallback | **[DOLDURUN]** model hata verirse veya saçmalarsa ne oluyor |
| Maliyet kontrolü | **[DOLDURUN]** prompt caching, token limiti, batching vb. |

Kullanılan prompt'lar: [prompts/](prompts/)

### MCP Sunucuları / Harici Araçlar
**[DOLDURUN]** Kullanıldıysa listeleyin, kullanılmadıysa "Kullanılmadı" yazın.

---

## 4. AI Kullanımı — Geliştirme Sürecinde

Kodu yazarken AI'dan nasıl faydalanıldığı.

| Araç | Ne için kullanıldı |
|---|---|
| Claude Code (CLI/IDE) | **[DOLDURUN]** ör. iskelet kod üretimi, dokümantasyon, refactor |
| **[DOLDURUN]** | |

### AI'ın ürettiği işler
- **[DOLDURUN]** ör. `src/example_billing.py` ilk sürümü ve `requirements.txt`
- **[DOLDURUN]**

### İnsanın verdiği kararlar
- Problem tanımı ve kapsam — **[DOLDURUN]**
- Mimari tasarım — **[DOLDURUN]**
- Model seçimi ve prompt stratejisi — **[DOLDURUN]**
- Neyin kapsam dışı bırakılacağı — **[DOLDURUN]**
- Deploy / push kararları — insan onayıyla (`main` branch'e push kararı insan tarafından verildi)

### Yaklaşık AI katkı oranı
**[DOLDURUN]** ör. "Kod satırlarının ~%60'ı AI tarafından üretildi, tamamı insan tarafından
gözden geçirildi ve çalıştırılarak doğrulandı."

---

## 5. Doğrulama — "Çalıştığını nereden biliyoruz?"

| Kontrol | Durum | Kanıt |
|---|---|---|
| Örnek script çalışıyor | ✅ | `python src/example_billing.py` — çıktı README'de |
| Bağımlılıklar sabitlenmiş | ✅ | [requirements.txt](requirements.txt) (`rich==14.1.0`) |
| Unit testler | **[DOLDURUN]** | `tests/unit/` |
| Entegrasyon testleri | **[DOLDURUN]** | `tests/integration/` |
| Uçtan uca demo | **[DOLDURUN]** | [demo/](demo/) |
| AI çıktısı doğrulaması | **[DOLDURUN]** | modelin çıktısını nasıl doğruluyorsunuz? |

---

## 6. Bilinçli Sınırlar (Kapsam Dışı)

Neyi **kasıtlı olarak** yapmadığınız ve nedeni. Net sınır çizmek artı puandır.

| Kapsam dışı | Gerekçe |
|---|---|
| **[DOLDURUN]** | **[DOLDURUN]** |
| **[DOLDURUN]** | **[DOLDURUN]** |

---

## 7. Güvenlik ve Veri Gizliliği

- **Sırlar**: `.env` `.gitignore` ile korunuyor; repoda yalnızca [.env.example](.env.example) var.
- **Kişisel veri (KVKK)**: **[DOLDURUN]** Fatura verisi gerçek mi, anonim mi, sentetik mi?
- **Modele gönderilen veri**: **[DOLDURUN]** PII maskeleniyor mu?
- **Prompt injection**: **[DOLDURUN]** Kullanıcı girdisi modele gidiyorsa nasıl korunuyor?

---

## 8. Tekrar Üretilebilirlik

```bash
git clone https://github.com/demirkanmehmet/ai-hackathon-billing-2026-billing.git
cd ai-hackathon-billing-2026-billing
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # anahtarları doldurun
python src/example_billing.py
```

**[DOLDURUN]** Asıl uygulamayı çalıştırma komutu.

---

## 9. Jüriye Not

**[DOLDURUN]** Jürinin özellikle bakmasını istediğiniz dosya/karar/detay. En çok gurur
duyduğunuz teknik seçim ve en çok zorlandığınız yer.
