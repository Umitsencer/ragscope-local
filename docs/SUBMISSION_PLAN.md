# Teslim planı

Son doğrulama: 2026-09-28. Bu plan program kabul garantisi değildir.

## Tamamlanan teknik kapsam

1. Pinned MITRE ATT&CK kaynağı ve hash kontrollü türetilmiş corpus/benchmark.
2. BM25, Foundry Local dense, dev-only RRF ve SAGE ablation değerlendirmeleri.
3. Yerel extractive RAG: retrieval, span seçimi, scope guard, exact-source kontrolü ve abstention.
4. `src/ragscope` çekirdek paketi, bounded input/resource kontrolleri ve test edilebilir Foundry adapter.
5. Windows/Python 3.11 CI, sabit Action SHA'ları, Dependabot ve allowlist tabanlı teslim paketi.
6. Güvenlik politikası, mimari, değerlendirme ve teslim dokümantasyonu.

## Kullanıcının tamamlayacağı dış işlemler

1. Private GitHub deposunu oluştur/seç ve remote'u ayarla.
2. Staged dosya listesini gözden geçir; model/cache/raw/private dosya olmadığını doğrula.
3. Commit ve push yap; GitHub Actions'ın uzakta geçtiğini kontrol et.
4. [Teslim rehberindeki](DELIVERY.md) akışla videoyu kaydet ve bağlantı erişimini test et.
5. Kod/video bağlantılarını programın güncel resmî kanalından gönder.

## Kabul sınırı

Program başlığı yerel RAG uygulamasıdır; extractive source-selection tasarımının değerlendirici tarafından kabul edileceği ayrıca doğrulanmamıştır. Web arayüzü, SQLite, bağımsız uzman gold seti veya yeni bir embedding algoritması zorunluluğunu kanıtlayan bir resmî kriter elde yoktur. Bunlar yapılmış gibi sunulmamalıdır.

Bağımsız gold değerlendirmesi, gerçek kullanıcı UAT'si, red-team ve deployment ortamı güvenlik incelemesi yapılmamıştır. Bu nedenle teslim edilebilir eğitim prototipi ile production-ready ürün birbirinden ayrılır.
