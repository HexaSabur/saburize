# Otonom Ajan Kontrol Paneli — Mimari Plan

## Teknoloji Yığını
- **Backend:** FastAPI (Python) — mevcut `app.py` genişletilecek
- **Gerçek Zamanlı İletişim:** Server-Sent Events (SSE) — WebSocket yerine, tarayıcıyla daha basit entegrasyon
- **AI Entegrasyonu:** Google Gemini API (google-generativeai Python paketi)
- **Deployment:** Surge.sh (mevcut kurulum)
- **Frontend:** Tek dosya (dashboard/index.html) — Vanilla HTML/CSS/JS

## Yeni Dosya Yapısı
```
agent/
├── app.py              ← Genişletilmiş FastAPI backend
├── dashboard/
│   └── index.html      ← Kontrol paneli arayüzü (Vanilla JS + SSE)
├── Musteri_Projesi/    ← Üretilen projenin çıktısı
└── MasterPrompt.md     ← Ajan şablonu referansı
```

## Backend Endpoint'leri (app.py)
1. `GET /`               → Dashboard'u serve eder
2. `POST /calistir`      → Tüm pipeline'ı başlatır (müşteri isteği + kurallar alır)
3. `GET /durum/{job_id}` → SSE stream: her adımın durumunu gerçek zamanlı iletir
4. `POST /dosyalari-olustur` → Mevcut endpoint (korunacak)

## Pipeline Adımları (SSE ile yayınlanacak)
1. 🧠 İstek analiz ediliyor...
2. ✍️  Gemini'ye gönderiliyor, kodlar üretiliyor...
3. 📂 Dosyalar ayrıştırılıp Musteri_Projesi/ klasörüne kaydediliyor...
4. 🌐 Surge ile canlıya alınıyor...
5. ✅ Tamamlandı! Canlı link: https://....surge.sh

## Dashboard Özellikleri
- Müşteri isteği ve kurallar için metin alanları
- Büyük "Projeyi Oluştur" butonu
- Gerçek zamanlı adım durumu (ilerledikçe güncellenir)
- Canlı log konsolu (terminal benzeri)
- Oluşturulan dosyaların listesi
- Kopyalanabilir canlı URL
- Dark mode, modern tasarım
