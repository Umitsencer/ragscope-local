# Proje durumu

Son doğrulama: 2026-09-30

## Amaç ve kapsam

RAGScope Local, Microsoft Foundry Local üzerinde MITRE ATT&CK retrieval ve doğrulanabilir extractive source-selection gösteren yerel eğitim prototipidir. Ürün; SOC kararı, olay doğrulama, hukuki görüş veya production-ready güvenlik sistemi değildir.

## Aktif mimari

- `src/ragscope/security.py`: sorgu, chat, embedding ve kaynak sınırları.
- `src/ragscope/foundry.py`: Foundry Local SDK 2.x task/response doğrulamalı adapter.
- `scripts/demo_local_retrieval.py`: dense retrieval ve kanıt kartları.
- `scripts/demo_local_extractive.py`: span-ID seçimi, scope guard, review ve exact-source render.
- `scripts/run_rag_acceptance.py`: sabit altı-vaka gerçek model koşusu ve uygulama manifesti.
- `scripts/verify_acceptance_integrity.py`: case, corpus, quote ve code-hash bütünlüğü.

Mimari ve tehdit sınırları [ARCHITECTURE.md](ARCHITECTURE.md) ile [SECURITY.md](../SECURITY.md) içinde açıklanır.

## Doğrulanmış sonuçlar

Retrieval test split'i 2.626 sorgudur:

- BM25: MRR `0,292483`, Hit@1 `0,177075`, Hit@10 `0,520944`.
- Foundry dense: MRR `0,537134`, Hit@1 `0,408225`, Hit@10 `0,793983`.
- RRF (`k=10`, yalnız dev'de seçildi): MRR `0,519792`, Hit@1 `0,383092`, Hit@10 `0,782559`; dense'i geçmedi.
- SAGE kontrollü alt küme exact-child Hit@1: `0,377382 → 0,385372`; bootstrap fark aralığı `[0, 0,015980]`, sıfırı içeriyor.

Kanonik JSON'lar `data/evaluation/` ve açıklama [EVALUATION.md](EVALUATION.md) içindedir.

Gerçek Foundry acceptance (`data/acceptance/2026-09-28-deployment-final/`):

- Altı sabit sentetik vakanın 6/6 süreci exit `0`.
- PowerShell, spearphishing attachment ve credential dumping ilgili kanıt seçti.
- Belirsiz phishing, alan dışı soru ve instruction injection çekimser kaldı.
- Beş alıntının corpus offset/hash kontrolü geçti.
- Altı uygulama dosyasının manifest hash'i eşleşti.
- CPU süreleri `48,802–77,829` saniye.

Bu sonuç bağımsız gold veya görülmemiş-soru kalite sonucu değildir. Ayrıntı: [acceptance incelemesi](../data/acceptance/REVIEW.md).

## Teslim durumu

- Aktif teslim ağacı tarihsel deneylerden temizlendi; eski artefactlar ignored `archive/` altında yerelde tutuluyor.
- Paket `src/` layout ile editable kuruluyor.
- CI Windows/Python 3.11 üzerinde lint, format, compile, unit/integration contract testleri, proje ve bağımlılık kontrollerini çalıştırıyor.
- Actions tam commit SHA ile sabit; Dependabot yapılandırılmış.
- Güvenlik politikası, mimari, evaluation ve teslim belgeleri güncel.
- 2026-09-30 teslim kapısı: Ruff lint/format, compile, **75 test**, yerel bağlantı/hash denetimi, `pip check` ve Git diff kontrolleri geçti.
- Remote: `https://github.com/Umitsencer/ragscope-local` — **public**, branch `main`, son commit `369d934`.
- GitHub Actions "Offline project checks" son koşusu: **success** (run [36722310365](https://github.com/Umitsencer/ragscope-local/actions/runs/36722310365)).

## Açık riskler ve sonraki eylem

1. Bağımsız gold set, gerçek kullanıcı UAT'si ve red-team yok; production-ready iddiası yapılamaz.
2. Tamamen ağsız soğuk başlangıç doğrulanmadı; catalog task metadata'sı erişim gerektirebilir.
3. **Repository-level lisans seçilmedi.** Repo public konuma getirildi. Lisans eklenmezse varsayılan telif hakları geçerlidir; kod "açık kaynak" sayılmaz. Bu bilinçli bir karar ise belgelenmeli, değilse bir lisans (`MIT`, `Apache-2.0` vb.) eklenmelidir.
