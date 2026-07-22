# Öğrenci Başvuru Anketi — Kurulum Rehberi

## Mimari (önceki terfi projesiyle aynı mantık, tamamen ayrı altyapı)

```
Streamlit (form + yönetici paneli)
        │  HTTPS + secret key
        ▼
Google Apps Script (Web App)
        │
        ├──► Google Sheets  (öğrenci bilgileri, tablo halinde)
        └──► Google Drive   (her öğrenci için ayrı klasör, 3 belge)
```

## ÖNEMLİ — Varsayım Bildirimi
Yüklenecek 3 sabit belge netleştirilmediği için, formun burs/sosyal yardım
başvurusu niteliğinde olduğu varsayımıyla şu 3 belge kabul edilmiştir:

1. Öğrenci Belgesi
2. Nüfus Cüzdanı / Kimlik Fotokopisi
3. Aile Gelir Durumunu Gösterir Belge

**Bunlar farklıysa:** `app.py` dosyasının en üstündeki `REQUIRED_DOCUMENTS`
listesini güncellemeniz yeterlidir, başka hiçbir yeri değiştirmenize gerek yok.

---

## Kurulum Adımları

### 1) Google Sheets + Apps Script
1. Yeni bir Google E-Tablosu (Sheets) oluşturun (örn. "Öğrenci Başvuruları").
2. Üst menüden **Uzantılar (Extensions) > Apps Script**.
3. Açılan editördeki kodu silip `apps_script.gs` dosyasının içeriğini yapıştırın.
4. Kod içindeki `SECRET_KEY` değerini değiştirin — güçlü, tahmin edilemez bir
   değer seçin (örn. `Vakif-Basvuru-2026-x7Q`).
5. **Dağıt > Yeni dağıtım > Web uygulaması**:
   - Yürüten kişi: **Ben**
   - Erişimi olanlar: **Herkes**
6. "Dağıt"a tıklayın, Google hesabınızla izin verin.
7. Size verilen `.../exec` ile biten URL'yi kopyalayın — bu, `APPS_SCRIPT_URL` olacak.

> Not: Kodu her değiştirdiğinizde **yeni bir dağıtım** yapmanız gerekir
> (mevcut dağıtımı düzenlemek "Yönet > Dağıtımları Düzenle" ile de mümkündür).

### 2) Streamlit Cloud
1. Bu klasördeki dosyaları GitHub reposuna yükleyin (`app.py`, `data/`,
   `requirements.txt`, `.streamlit/config.toml`).
2. **`.streamlit/secrets.toml.example` dosyasını repoya YÜKLEMEYİN** — sadece
   referans amaçlıdır. Gerçek secrets'ı Streamlit Cloud panelinden gireceksiniz.
3. Streamlit Cloud'da: **Manage app > ⋮ > Settings > Secrets** açın, şunu yapıştırın:

```toml
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycb.../exec"
APPS_SCRIPT_SECRET = "Vakif-Basvuru-2026-x7Q"   # Apps Script'teki ile BİREBİR aynı

[admin_credentials]
user = "yonetici"
pass = "guclu-bir-sifre"
```

4. Kaydedin, uygulama otomatik yeniden başlar.

### 3) Test
1. Formu bir kez test verisiyle doldurup gönderin.
2. Google Drive'da "Ogrenci Basvuru Evraklari" klasörü altında öğrenciye özel
   alt klasörün oluştuğunu ve 3 belgenin yüklendiğini doğrulayın.
3. Google Sheets'te satırın eklendiğini doğrulayın.
4. Streamlit'te "Yönetici Girişi"nden panele girip verinin ve Excel indirme
   butonunun çalıştığını doğrulayın.

---

## Riskler / Dikkat Edilmesi Gerekenler

- **Dosya boyutu:** Apps Script tek istekte işlenebilecek payload büyüklüğü
  sınırlıdır. `config.toml` içinde `maxUploadSize = 15` (MB) olarak
  sınırlandırılmıştır; çok yüksek çözünürlüklü taranmış belgelerde sorun
  çıkarsa bu sınırı düşürün veya kullanıcıdan sıkıştırılmış dosya isteyin.
- **T.C. Kimlik No ve gelir bilgisi gibi hassas veriler** Sheets'te düz metin
  olarak tutulur. E-Tablonun paylaşım ayarlarını "Kısıtlı" (yalnız
  belirlediğiniz kişiler) tutmanız önerilir — KVKK kapsamında hassas veri.
- **Secret key sızıntısı:** `SECRET_KEY` değerini kimseyle paylaşmayın; sızarsa
  yeni bir anahtar belirleyip hem Apps Script hem Streamlit tarafında güncelleyin.
- **Yinelenen başvuru kontrolü** şu an yoktur (aynı T.C. no ile iki kez
  başvurulabilir). İsterseniz Apps Script'e T.C. no bazlı tekrar kontrolü
  eklenebilir.
