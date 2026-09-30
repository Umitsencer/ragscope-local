# Teslim rehberi

Teslim tanımı: **Microsoft Foundry Local ile ATT&CK retrieval ve doğrulanabilir LLM destekli kaynak seçimi eğitim prototipi.** Serbest yanıt veren genel bir soru-cevap ürünü veya SOC karar sistemi olarak sunulmaz.

## Gösterim

README kurulumundan sonra, model cache dizininizi verin:

```powershell
powershell -NoProfile -File scripts/start_demo.ps1 -ModelCache 'D:\foundry-cache'
```

Enter, belgelenmiş sentetik credential-dumping sorusunu kullanır. Komut canlı yerel inference çalıştırır; kayıtlı yanıt oynatmaz ve model indirmez. CPU süresi donanıma göre değişir. Video içinde bekleme bölümü kesilirse bu açıkça belirtilmelidir.

## Yaklaşık iki dakikalık sunum

**0:00–0:20 — Problem:** “RAGScope Local, benzer MITRE ATT&CK tekniklerini kaynağıyla incelemek için geliştirdiğim yerel bir eğitim prototipi. Otomatik olay hükmü vermiyor; denetlenebilir kanıt gösteriyor.”

**0:20–0:45 — Akış:** “Foundry Local embedding modeli sorguyu yerelde vektöre dönüştürüyor. Dense retrieval ilgili tanımları getiriyor. Phi modeli serbest cevap yazmak yerine kaynak parçası kimliklerini seçiyor; kod offset ve hash'i doğruluyor.”

**0:45–1:15 — Demo:** Sentetik credential-dumping sorgusunu çalıştır. “Ekrandaki metin modelin uydurduğu bir iddia değil; ATT&CK kaynağından birebir alıntı. Yetersiz veya kapsam dışı kanıtta sistem çekimser kalıyor.”

**1:15–1:40 — Deney:** “Kontrollü testte dense retrieval BM25'i geçti. RRF dense sonucu geçemedi. Sibling-aware ablation küçük bir fark gösterdi fakat güven aralığı sıfırı içerdi; üstünlük iddia etmiyorum.”

**1:40–2:00 — Öğrenim:** “Temel katkım leakage kontrollü değerlendirme, yerel inference ve doğrulanabilir output contract oldu. Doğru kaynağı göstermekle gerçek olay doğruluğunu kanıtlamanın farklı şeyler olduğunu ölçerek gördüm.”

## Push öncesi kapı

```powershell
ruff check src scripts tests
ruff format --check src scripts tests
python -B -m compileall -q src scripts tests
python -B -m unittest discover -s tests -v
python -B scripts/check_project.py
python -m pip check
git diff --cached --check
git status --short
```

Push sonrasında GitHub Actions sonucunu ayrıca kontrol edin. Yerel test, remote CI yerine geçmez. Private depo değerlendiriciye ayrıca erişim verilmeden görüntülenemez. Video ve depo yükleme işlemleri bu projede otomatik yapılmaz.
