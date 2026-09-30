# Mimari

## Amaç

RAGScope Local, MITRE ATT&CK tanım corpus'unda yerel retrieval ve kanıta bağlı extractive yanıt üretimini gösterir. Model serbest cevap yazmaz; aday kanıt span'larını seçer. Kullanıcıya gösterilen alıntı kaynak metinden deterministik olarak çıkarılır.

## Modüller

```text
src/ragscope/
  security.py   Girdi, mesaj, batch ve kaynak sınırları
  foundry.py    Foundry Local SDK 2.x uyumluluk katmanı
scripts/
  demo_local_retrieval.py   Dense retrieval
  demo_local_extractive.py  Span seçimi, scope guard, abstention
  demo_local_rag.py         Yerel CLI orkestrasyonu
  run_*.py / build_*.py     Tekrarlanabilir deney ve veri üretimi
tests/                      Unit ve contract testleri
data/derived/               Aktif, doğrulanmış corpus/benchmark
data/evaluation/            Kontrollü değerlendirme çıktıları
data/acceptance/            Sabit altı-case yerel acceptance kanıtı
```

## İstek akışı

1. `security.validate_query` sorguyu boyut ve karakter sınırlarında doğrular.
2. Dense retriever, sabit hash'li ATT&CK corpus'undan aday evidence card'ları seçer.
3. Extractive katman kaynak cümlelerini immutable span kimliklerine dönüştürür.
4. Foundry Local chat modeli yalnızca `{"selected": [...]}` şemasında span kimliği önerir.
5. Scope guard, açık teknik kimliği/adı ile uyuşmayan kanıtı eler; ikinci model geçişi seçimi daraltabilir fakat yeni span ekleyemez.
6. Uygulama offset ve SHA-256 bütünlüğünü doğrular; doğrulanmış kaynak metnini gösterir veya `insufficient_evidence`/`rejected_output` üretir.

## Güven sınırları

- Kullanıcı girdisi, corpus metni, retrieval sıralaması ve model çıktısı güvenilmeyen girdidir.
- Yalnızca repository içindeki doğrulanmış corpus ve şema/offset/hash kontrolünden geçen alıntı kullanıcıya gösterilir.
- Runtime adapter yanlış task, eksik/misindexed embedding ve dimension drift durumunda fail-closed davranır.
- Ağ, kimlik doğrulama, multi-tenant erişim kontrolü ve web sunucusu bu yerel CLI tesliminin kapsamında değildir.

Detaylı kontroller [SECURITY.md](../SECURITY.md) içindedir.
