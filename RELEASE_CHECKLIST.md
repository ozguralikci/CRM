# CRM Release Checklist

## Build Oncesi

- `venv` hazir ve aktif
- `pip install -r requirements.txt` tamamlandi
- `assets\app.ico` kontrol edildi
- `installer.iss` icindeki `MyAppVersion` guncel
- Eski acik `CRM.exe` sureci yok

## EXE Build

- `python build_exe.py` basarili
- Cikti klasoru olustu: `dist\CRM\`
- Ana dosya mevcut: `dist\CRM\CRM.exe`
- Ikon beklendigi gibi baglandi veya ikon yoksa bu durum not edildi

## Temel Smoke Test

- `CRM.exe` aciliyor
- Ana pencere aciliyor
- Sayfa gecisleri calisiyor
- Bir liste ekrani aciliyor
- Sirket operasyon ekrani aciliyor
- Bir form aciliyor ve kapanabiliyor

## Yol Ve Log Dogrulamasi

- EXE modunda DB yolu: `%LOCALAPPDATA%\CRM\crm.sqlite`
- Uygulama logu olusuyor: `%LOCALAPPDATA%\CRM\logs\crm-app.log`
- Hata logu yolu dogru: `%LOCALAPPDATA%\CRM\logs\crm-error.log`
- Import/export varsayilan klasoru erisilebilir: `%USERPROFILE%\Documents\CRM\Aktarimlar`

## Installer

- `installer.iss` compile edildi
- Cikti olustu: `release\CRM-Setup.exe`
- Temiz bir test makinede veya test kullanicisinda kurulum denendi
- Uygulama kurulumdan sonra acildi
- Masaustu / Baslat menusu kisayollari beklendigi gibi calisti

## Manuel QA Hatirlaticilari

- En az bir CRUD akisi elle kontrol edildi
- Log dosyalari yazilabilir durumda
- Ikon, pencere basligi ve urun adi `CRM` olarak gorunuyor
- Yatay / dikey scroll davranisinda kritik bozulma yok
- Bos durumlar ve temel butonlar gorunur

## Sevkiyat Onayi

- Gonderilecek dosya net: `release\CRM-Setup.exe` veya gerekli ise `dist\CRM\`
- Surum notu / teslim notu hazir
- Bilinen sinirlar ekip icinde not edildi
