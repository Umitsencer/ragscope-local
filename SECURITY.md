# Güvenlik Politikası

RAGScope Local eğitim ve araştırma amaçlı, yerel çalışan bir prototiptir. Bir SOC karar sistemi, olay doğrulama aracı veya güvenlik kontrolü değildir.

## Tehdit modeli ve uygulanan kontroller

| Sınır | Risk | Uygulanan kontrol |
|---|---|---|
| Kullanıcı sorgusu | Prompt injection, kaynak tüketimi | Uzunluk ve kontrol karakteri doğrulaması; sorgu talimat değil, güvenilmeyen veri olarak ele alınır. |
| Retrieval çıktısı | İlgisiz veya yanıltıcı bağlam | Sabit corpus hash'i, kaynak kimliği, scope guard ve yetersiz kanıtta abstention. |
| Model çıktısı | Uydurma metin veya sahte atıf | Model yalnızca span kimliği seçer; gösterilen metin deterministik olarak kaynaktan kesilir ve offset/hash doğrulanır. |
| Yerel runtime | Sınırsız kaynak kullanımı, yanlış model görevi | Mesaj, bağlam, batch ve output-token sınırları; model task ve embedding boyutu doğrulaması. |
| Tedarik zinciri | Değişen bağımlılık veya CI action'ı | Sürümler sabitlenmiştir; GitHub Actions tam commit SHA ile çağrılır; Dependabot yalnızca inceleme için PR açar. |
| Kayıtlar | Prompt veya hassas veri sızıntısı | Acceptance çıktısı sorgu metni yerine SHA-256 taşır; tanı günlükleri prompt/completion ve native hata metnini saklamaz. |

Sistem herhangi bir aracı çalıştırmaz, harici eylem gerçekleştirmez ve model çıktısını komut olarak yorumlamaz. Corpus içeriği de güvenilmeyen veri kabul edilir. Yerel prototipte Azure AI Content Safety veya Prompt Shields entegrasyonu yoktur; böyle bir kontrol varmış gibi güvenlik iddiasında bulunulmaz.

## Desteklenen sürüm

Güvenlik düzeltmeleri yalnızca `main` dalının güncel hali için hazırlanır. Depo özel tutulurken güvenlik bulguları depo sahibine özel kanaldan iletilmelidir. Depo ileride herkese açılırsa istismar ayrıntılarını public issue olarak paylaşmak yerine GitHub'ın private security advisory akışı kullanılmalıdır.

## Gizli bilgiler

Depoya token, parola, API anahtarı, kişisel veri, özel konuşma, model ağırlığı veya yerel cache eklemeyin. Kimlik bilgileri gerekirse environment variable ya da hedef ortamın secret store mekanizması kullanılmalıdır. Bu sürüm dış servis kimlik bilgisi gerektirmez.

## Kapsam dışı güvence

Bu kontroller prompt injection'ı bütünüyle çözdüğünü, model davranışının güvenli olduğunu veya hukuki/operasyonel kararların otomatikleştirilebileceğini kanıtlamaz. Bağımsız red-team, kullanıcı kabulü ve dağıtım ortamı güvenlik incelemesi yapılmamıştır.
