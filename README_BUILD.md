# CRM Build And Release Notes

## Hedef

Bu belge `CRM` masaustu uygulamasinin Windows EXE build alma, installer hazirlama, cikti dizinlerini dogrulama ve release oncesi temel kontrollerini tek yerde toplar.

Detayli sevkiyat adimlari icin ek kontrol listesi:

```text
RELEASE_CHECKLIST.md
```

## Ortam Hazirlama

PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Build komutlarini ayni sanal ortamdan calistirin. En guvenli iki yol:

```powershell
.\venv\Scripts\Activate.ps1
python build_exe.py
```

veya dogrudan:

```powershell
.\venv\Scripts\python.exe build_exe.py
```

Not:

- `build_exe.py`, aktif Python yorumlayicisini kullanir.
- Sistem Python'i ile build almak, eksik `PyInstaller` veya farkli paket surumu nedeniyle hataya yol acabilir.

## Build On Kosullari

EXE build almadan once su maddeleri kontrol edin:

- `venv` olusmus ve `requirements.txt` kurulmus olmali
- `CRM.spec` dosyasi projede mevcut olmali
- Ikon kullanilacaksa `assets\app.ico` dosyasi yerinde olmali
- `dist\` ve `build\` ciktilarinin kapanmis bir eski EXE tarafindan kilitli olmadigindan emin olun

## EXE Uretimi

Tercih edilen komut:

```powershell
python build_exe.py
```

Alternatif dogrudan PyInstaller komutu:

```powershell
python -m PyInstaller --noconfirm --clean CRM.spec
```

`build_exe.py` ne yapar:

- `CRM.spec` dosyasini kullanir
- aktif Python yorumlayicisi ile `PyInstaller` calistirir
- ikon bulunursa bilgi verir
- ikon bulunmazsa build'i durdurmaz

## Ikon Davranisi

Beklenen ikon yolu:

```text
assets\app.ico
```

Bu dosya varsa:

- `CRM.spec` ikonu EXE'ye baglar
- ikon `dist\CRM\assets\app.ico` altina da dahil edilir

Bu dosya yoksa:

- build devam eder
- varsayilan uygulama ikonu kullanilir

## Cikti Konumu

Derleme tamamlandiginda uygulama su klasore cikartilir:

```text
dist\CRM\
```

Calistirilabilir dosya:

```text
dist\CRM\CRM.exe
```

Dagitim icin temel klasor:

```text
dist\CRM\
```

## Calisma Dizini, DB Ve Log Yollari

Kaynak koddan calisma:

- uygulama koku: proje dizini
- veritabani: `crm.sqlite`
- loglar: kullanici profili altinda olusur

Paketlenmis EXE calisma:

- uygulama EXE yolu: `dist\CRM\CRM.exe`
- veritabani: `%LOCALAPPDATA%\CRM\crm.sqlite`
- uygulama logu: `%LOCALAPPDATA%\CRM\logs\crm-app.log`
- hata logu: `%LOCALAPPDATA%\CRM\logs\crm-error.log`
- import/export varsayilan klasoru: `%USERPROFILE%\Documents\CRM\Aktarimlar`

Not:

- EXE modunda veritabani install klasorune degil, kullanici yazma izinli profile yazilir.
- Bu davranis tasarim geregi korunur; installer ile birlikte veritabani tasinmaz.

## Installer Hazirligi

Projede Inno Setup icin hazir sablon bulunur:

```text
installer.iss
```

Temel installer varsayimlari:

- uygulama adi: `CRM`
- ana exe: `dist\CRM\CRM.exe`
- kurulum dizini: `%LOCALAPPDATA%\Programs\CRM`
- yetki seviyesi: kullanici bazli kurulum
- masaustu kisayolu: opsiyonel
- baslat menusu kisayolu: opsiyonel
- installer cikti klasoru: `release\`

## Installer Uretimi

1. EXE build alin.
2. `installer.iss` icindeki `MyAppVersion` degerini gerekirse guncelleyin.
3. Inno Setup Compiler ile `installer.iss` dosyasini acin.
4. `Build` veya `Compile` ile installer paketini olusturun.

Varsayilan installer ciktilari:

```text
release\CRM-Setup.exe
```

## Build Disiplini

Her release'te ayni sirayi takip edin:

1. Sanal ortami aktif edin.
2. Bagimliliklari senkron oldugunu dogrulayin.
3. `python build_exe.py` ile temiz build alin.
4. `dist\CRM\CRM.exe` acilisini test edin.
5. DB/log yolunu dogrulayin.
6. Installer gerekiyorsa `installer.iss` ile paket alin.
7. `RELEASE_CHECKLIST.md` maddelerini tek tek isaretleyin.

## Bilinen Sinirlar Ve Manuel QA Hatirlaticilari

- Build sonrasi temel UI smoke testi manuel olarak yapilmalidir.
- Installer, mevcut kullanici verisini tasimaz; yalnizca uygulama dosyalarini kurar.
- EXE icin ayrica Win32 version resource / dosya metadata gomulu degildir.
- Uygulama loglari kullanici profilinde tutuldugu icin destek toplama sirasinda bu dizin manuel olarak istenmelidir.
- Ikon yoksa build basarili olur, ancak release gorsel kimligi eksik kalir.

## Opsiyonel Surumleme Notu

Su an guvenli ve mevcut olarak desteklenen surum alani:

- `installer.iss` icindeki `MyAppVersion`

Su alan henuz eklenmemistir ve bu geciste bilincli olarak ertelenmistir:

- EXE dosyasina ayri Windows file version / product version metadata gomulmesi
