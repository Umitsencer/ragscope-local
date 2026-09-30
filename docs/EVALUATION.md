# Değerlendirme

Bu dosya yalnızca depodaki kanonik JSON çıktılarından doğrulanabilen sonuçları özetler. Metrikler farklı protokoller arasında karşılaştırılmaz.

## Kontrollü retrieval test split'i

| Yöntem | Sorgu | MRR | Hit@1 | Hit@10 | Kanıt |
|---|---:|---:|---:|---:|---|
| BM25 | 2.626 | 0,292483 | 0,177075 | 0,520944 | `data/evaluation/bm25_definition_only_test.json` |
| Foundry dense | 2.626 | 0,537134 | 0,408225 | 0,793983 | `data/evaluation/foundry_dense_definition_only_test.json` |
| RRF, dev'de seçilen k=10 | 2.626 | 0,519792 | 0,383092 | 0,782559 | `data/evaluation/rrf_bm25_foundry_dense_test_k10.json` |

RRF, aynı testte dense baseline'ı geçmemiştir. Bu nedenle fusion için başarı iddiası yapılmaz. `k=10` yalnızca dev split'inde seçilmiş, test split'inde tekrar ayarlanmamıştır.

SAGE kontrollü alt kümesinde exact-child Hit@1 `0,385372`, dense baseline `0,377382` değerindedir (`n=1.627`). Bootstrap fark aralığı `[0, 0,015980]` sıfırı içerir; sonuç kanıtlanmış üstünlük değildir. Multi-positive retrieval için aday risk bound'u kurulamadığından M3 hipotezi doğrulanmamıştır.

## Yerel cevap kabulü

Altı sentetik işlevsel case bağımsız gold set değildir. Acceptance; process exit, corpus/query hash, kaynak offset'i, exact quote ve uygulama manifest bütünlüğünü denetler. Semantik kalite iddiası ayrıca insan incelemesi gerektirir. Güncel kanonik dizin ve gerçek süreler acceptance yeniden çalıştırıldıktan sonra `PROJECT_STATE.md` içinde kaydedilir.

## Sınırlılıklar

- Corpus İngilizce ATT&CK tanımlarıdır; Türkçe retrieval kalitesi ölçülmemiştir.
- Değerlendirme soruları corpus'tan türetilmiştir; gerçek SOC dağılımını temsil etmez.
- Sonuçlar CPU ve belirtilen yerel model/cache ortamına özgüdür.
- Bağımsız uzman gold seti, en az sekiz kullanıcıyla UAT ve red-team yapılmamıştır.
