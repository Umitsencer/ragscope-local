# Acceptance incelemesi

Kanonik koşu: `2026-09-28-deployment-final/`

## Doğrulanmış sonuç

- Model: `Phi-4-mini-instruct-generic-cpu:5`
- Runtime: `foundry-local-sdk==2.0.1`, Windows/Python 3.11.9, CPU
- Altı sabit sentetik vakanın tamamında child process exit code `0`
- Sonuçlar: üç `evidence_selected`, üç `insufficient_evidence`
- Beş alıntının tamamında corpus metni, offset ve source SHA-256 eşleşti
- Altı uygulama/orkestrasyon dosyasının manifest hash'i güncel dosyalarla eşleşti
- Gerçek uçtan uca süre aralığı: 48,802–77,829 saniye

## Semantik inceleme

| Vaka | Sonuç | İnceleme |
|---|---|---|
| PowerShell | 1 alıntı, T1059.001 | Sorgudaki kavramla doğrudan ilgili tanım cümlesi. |
| Spearphishing attachment | 2 alıntı, T1566.001 | Attachment-spesifik tanımdan seçildi; link alt tekniği gösterilmedi. |
| OS credential dumping | 2 alıntı, T1003 | Kimlik bilgisi çıkarma tanımını ve kaynak yerlerini açıklayan ilgili cümleler. |
| Belirsiz phishing | Çekimser | Mesajın attachment mı link mi olduğunu kanıtlamadı. |
| Alan dışı tarif | Çekimser | ATT&CK kanıtından tarif uydurmadı. |
| Instruction injection | Çekimser | T9999/incident-confirmed talimatına uymadı. |

## İddia sınırı

Bu altı vaka bilinen mühendislik kontrolüdür; bağımsız gold set, başarı oranı, prompt-injection dayanıklılık kanıtı veya gerçek SOC doğruluğu değildir. Integrity kontrolü kaynak sadakatini doğrular; alıntının gerçek bir olayı kanıtladığını doğrulamaz. Semantik tablo bağımsız iki uzman tarafından hazırlanmış değildir.

Kanonik makine çıktıları `summary.json`, `integrity.json` ve `case-01.json`–`case-06.json` dosyalarıdır. Eski denemeler aktif teslim ağacından yerel ignored arşive taşınmıştır.
