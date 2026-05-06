# MSSQL Brute Force — Sınıf Demo Rehberi

**Süre:** ~30 dakika  
**Araçlar:** Windows (Flask App + SSMS), Kali (Burp Suite)  
**Senaryo:** Zafiyetli uygulama → Saldırı → Tespit edilememe → Koruma

---

## Hazırlık (Önceden)

- Windows'ta `python bruteforce_lab_app.py` çalışıyor olmalı
- Kali'de Burp Suite açık, tarayıcı proxy `127.0.0.1:8080`
- SSMS açık, `155.223.166.100` bağlantısı hazır

---

## BÖLÜM 1 — Uygulama Tanıtımı (2 dk)

**Ekran: Windows tarayıcı → `http://localhost:5001`**

> "Bu uygulama gerçek bir MSSQL veritabanına bağlı basit bir öneri sistemi.
> Giriş yapmak için MSSQL kullanıcı adı ve parolası gerekiyor."

- Yanlış credentials gir → hata mesajını göster
- Doğru credentials gir (`egeogr030` / `egeogr030`) → paneli göster
- Öneri gönder → tabloya düştüğünü göster
- Çıkış yap

---

## BÖLÜM 2 — Saldırı (5 dk)

**Ekran: Kali → Burp Suite**

> "Şimdi bu uygulamaya brute force saldırısı yapacağız.
> Saldırgan parolayı bilmiyor ama otomatik olarak binlerce deneme yapabilir."

**Adımlar:**

1. Kali tarayıcısında `http://WINDOWS_IP:5001` aç
2. Burp Proxy → **Intercept On**
3. Forma yanlış credentials gir, gönder
4. Burp'te isteği yakala → **Send to Intruder**
5. **Intercept Off**
6. Intruder → Positions → sadece `password=§§` işaretle
7. Payloads → Simple list → `rockyou.txt` yükle
8. **Start Attack**

> "Saniyede onlarca deneme gidiyor. Uygulama hiç yavaşlamadı, hiç uyarmadı."

9. Status sütununa göre sırala → **302 olan satırı göster**

> "302 = başarılı giriş. Parola bulundu."

---

## BÖLÜM 3 — Görünürlük Yetersiz (3 dk)

**Ekran: Windows → Event Viewer**

> "Peki bu saldırı bir iz bıraktı mı? Bakalım."

1. `Win + R` → `eventvwr` → Enter
2. **Windows Logs → Application**

> "Burada Login Failed hataları görünüyor — MSSQL default olarak buraya yazar.
> Ama dikkat: sadece hata mesajı var."

- Kayıtlardan birine tıkla, detayını göster

> "Kim denedi? Hangi IP'den geldi? Kaç kez denedi? Bu bilgiler yok.
> Saldırganı tespit etmek, engellemek veya delil toplamak için bu yeterli değil."

**Ekran: SSMS**

```sql
EXEC xp_readerrorlog 0, 1, N'Login failed';
```

> "Error log'da da aynı — sadece hata var, detay yok.
> MSSQL Audit açılırsa IP adresi, kullanıcı adı, zaman damgası hepsi kayıt altına alınır."

---

## BÖLÜM 4 — Çözüm: MSSQL Audit (5 dk)

**Ekran: SSMS — Object Explorer**

> "Şimdi MSSQL'in kendi audit mekanizmasını açıyoruz.
> Başarısız her giriş denemesi artık kayıt altına alınacak."

### Arayüzden Audit Oluşturma

**1. Audit nesnesi:**
```
Object Explorer →
  Güvenlik (Security) →
    Denetimler (Audits) → sağ tık → Yeni Denetim (New Audit...)
```
- Denetim adı: `BruteForceAudit`
- Denetim hedefi: `Dosya (File)`
- Dosya yolu: `C:\AuditLogs\`
- Tamam → sağ tık → **Etkinleştir (Enable)**

**2. Server Audit Specification:**
```
Object Explorer →
  Güvenlik →
    Sunucu Denetim Belirtimleri (Server Audit Specifications) →
      sağ tık → Yeni Sunucu Denetim Belirtimi...
```
- Ad: `LoginFailSpec`
- Denetim: `BruteForceAudit` seç
- Alt tabloda boş satıra tıkla → Denetim Eylem Türü: `FAILED_LOGIN_GROUP`
- Tamam → sağ tık → **Etkinleştir (Enable)**

---

> "Audit açıldı. Şimdi tekrar saldıralım."

**Ekran: Kali → Burp Intruder → Start Attack** (kısa süre çalıştır)

**Ekran: SSMS**

```sql
SELECT
    event_time,
    server_principal_name,
    client_ip
FROM sys.fn_get_audit_file('C:\AuditLogs\*.sqlaudit', DEFAULT, DEFAULT)
WHERE action_id = 'LGIF'
ORDER BY event_time DESC;
```

> "Şimdi her deneme kayıt altında. Kim, nereden, ne zaman — hepsi görünür."

---

## BÖLÜM 4b — Parola Politikası Arayüzden (2 dk)

**Ekran: SSMS — Object Explorer**

> "MSSQL'de her login için Windows parola politikası zorlanabilir.
> Bu sayede zayıf parola ve sonsuz deneme engellenir."

```
Object Explorer →
  Güvenlik (Security) →
    Oturumlar (Logins) →
      egeogr030 → sağ tık → Özellikler (Properties)
```

**Genel (General) sekmesi:**
- Parola: güçlü parola gir

**Durum (Status) sekmesi:**
- Oturum Açmaya İzin Ver: `Etkin`

**Genel sekmesine geri dön, altta:**
- ✅ Parola ilkesi zorla (Enforce password policy)
- ✅ Parola süre sonunu zorla (Enforce password expiration)
- ✅ Kullanıcının parolayı değiştirmesi gerekiyor (User must change password)
- Tamam

> "Artık bu hesap için zayıf parola kullanılamaz,
> belirli süre sonunda parola değiştirilmek zorunda."

---

## BÖLÜM 5 — Çözüm: Otomatik Kilitleme (5 dk)

**Ekran: SSMS**

> "Loglama görmemizi sağlar ama saldırıyı durdurmaz.
> İki farklı yöntemle otomatik kilitleme yapabiliriz."

---

### Yöntem A — CHECK_POLICY (Windows Parola Politikası)

> "MSSQL, Windows'un hesap kilitleme politikasını kullanabilir.
> Belirli sayıda hatalı denemede hesap otomatik kilitlenir."

**Önce Windows'ta politikayı ayarla:**
```
gpedit.msc →
  Bilgisayar Yapılandırması →
    Windows Ayarları →
      Güvenlik Ayarları →
        Hesap İlkeleri →
          Hesap Kilitleme İlkesi →
            Hesap kilitleme eşiği: 5
            Kilitleme süresi: 15 dakika
```

**SSMS'te login'e uygula:**
```sql
ALTER LOGIN [egeogr030] WITH CHECK_POLICY = ON;
```

veya arayüzden:
```
Login Properties → General →
  ✅ Enforce password policy
```

**Test:** Burp ile 5+ hatalı deneme yap → hesap kilitlenir.

```sql
-- Kilitlendi mi?
SELECT name, is_disabled FROM sys.server_principals
WHERE name = 'egeogr030';
```

---

### Yöntem B — LOGON Trigger ile IP Whitelist

> "Parola ele geçirilse bile yetkisiz IP'den giriş yapılamaz.
> Trigger başarılı login'de tetiklenir, izin verilmeyen bağlantıyı keser."

**Seçenek 1 — Subnet bazlı (155.223.166.x):**
```sql
USE master;
GO

CREATE TRIGGER trg_ip_whitelist
ON ALL SERVER
FOR LOGON
AS
BEGIN
    DECLARE @ip NVARCHAR(50) = EVENTDATA().value(
                    '(/EVENT_INSTANCE/ClientHost)[1]', 'NVARCHAR(50)');

    -- Sadece 155.223.166.x ağına izin ver
    IF @ip NOT LIKE '155.223.166.%' AND @ip <> '127.0.0.1'
    BEGIN
        ROLLBACK;
    END
END;
GO
```

**Seçenek 2 — IP aralığı bazlı (155.223.166.100-200):**
```sql
USE master;
GO

CREATE TRIGGER trg_ip_whitelist
ON ALL SERVER
FOR LOGON
AS
BEGIN
    DECLARE @ip  NVARCHAR(50) = EVENTDATA().value(
                     '(/EVENT_INSTANCE/ClientHost)[1]', 'NVARCHAR(50)');
    DECLARE @son INT = TRY_CAST(PARSENAME(@ip, 1) AS INT);

    -- Sadece 155.223.166.100 - 155.223.166.200 arası izin ver
    IF NOT (
        @ip LIKE '155.223.166.%'
        AND @son BETWEEN 100 AND 200
    )
    AND @ip <> '127.0.0.1'
    BEGIN
        ROLLBACK;
    END
END;
GO
```

> "PARSENAME(@ip, 1) son okteti alır → sayısal karşılaştırma yapılır."

**Trigger'ın nerede göründüğünü göster:**
```
Object Explorer →
  Server adı →
    Sunucu Nesneleri →
      Tetikleyiciler →
        trg_ip_whitelist
```

**Test:** Brute force ile doğru parolayı bul → izin verilmeyen IP'den giriş dene → bağlantı kesilir.

**Temizlik:**
```sql
DROP TRIGGER trg_ip_whitelist ON ALL SERVER;
ALTER LOGIN [egeogr030] WITH CHECK_POLICY = OFF;
```

---

## BÖLÜM 6 — OSI Katmanları ve Görünürlük (5 dk)

**Ekran: Tahta / Sunum**

> "Az önce yaptığımız saldırıda MSSQL audit'te saldırganın IP'si olarak Kali'yi değil,
> web sunucusunu (Flask) gördük. Neden?"

### Saldırı Vektörlerine Göre Hangi Katmanda Ne Görünür

```
OSI       Bileşen            Burp→Flask→MSSQL    Hydra→MSSQL direkt    Meterpreter (shell)
────────  ─────────────────  ──────────────────  ───────────────────   ───────────────────
L7 App    MSSQL Audit        Web sunucu IP (112) Saldırgan IP (101)    Localhost / yerel IP
L7 App    Flask Log          Saldırgan IP (101)  —                     —
L4 Trans  Firewall/IDS       Her iki bağlantı    Tek bağlantı          Yerel trafik
L3 Net    Network Log        Her iki IP görünür  Saldırgan IP görünür  Görünmez
```

---

### Senaryo 1 — Burp ile Web Uygulaması Üzerinden (Az önce yaptığımız)

```
Kali (101) ──HTTP──► Flask/Windows (112) ──TDS──► MSSQL (100)
```

- **MSSQL Audit görür:** `client_ip = 155.223.166.112` (Windows/Flask)
- **Flask logu görür:** `ip = 155.223.166.101` (Kali)
- **Sonuç:** DB tek başına yetersiz. Saldırgan web sunucusunun arkasına gizlendi.

---

### Senaryo 2 — Hydra ile Doğrudan MSSQL'e

```
Kali (101) ──TDS──► MSSQL (100)
```

```bash
hydra -l egeogr030 -P rockyou.txt mssql://155.223.166.100:51433 -t 4 -V
```

- **MSSQL Audit görür:** `client_ip = 155.223.166.101` (Kali — gerçek IP)
- **Flask logu:** — (web uygulaması devre dışı bırakıldı)
- **Sonuç:** DB audit yeterli, ama web uygulaması firewall'u bypass edildi.

> "Rate limiting, CAPTCHA gibi uygulama katmanı korumaları tamamen atlandı."

---

### Senaryo 3 — Meterpreter / Post-Exploitation (Shell Ele Geçirilmiş)

```
Kali ──exploit──► Windows shell (112) ──TDS──► MSSQL (100)
```

Saldırgan Windows makinesinde shell aldıktan sonra MSSQL'e bağlanır:

- **MSSQL Audit görür:** `client_ip = 127.0.0.1` veya `155.223.166.112` (Windows)
- **Görünüm:** Normal bir uygulama bağlantısından farkı yok
- **Sonuç:** DB audit bu saldırıyı **tespit edemez**

> "Bu noktada tespit için EDR, Windows Event Log (process monitoring),
> SIEM korelasyonu gerekir. DB tek başına kör."

---

### Özet — Hangi Araç Hangi Katmanı Korur

| Katman | Araç | Gördüğü |
|--------|------|---------|
| L7 DB | MSSQL Audit | DB'ye bağlanan IP, hesap, zaman |
| L7 App | Flask / Web log | Tarayıcının/aracın gerçek IP'si |
| L7 OS | Windows Event Log | Process, kullanıcı, dosya erişimi |
| L4/L3 | Firewall / IDS | IP, port, bağlantı sayısı |
| Tümü | SIEM (korelasyon) | Katmanlar arası örüntü tespiti |

> "Katmanlı loglama = tam görünürlük. Tek katman her zaman kör nokta bırakır."

---

## BÖLÜM 7 — Özet (2 dk)

| Adım | Yapılan | Sonuç |
|------|---------|-------|
| Başlangıç | Koruma yok | Saldırı görünmez, parola bulundu |
| Audit açıldı | Server Audit + Specification | Her deneme kayıt altına alındı |
| Trigger eklendi | Login Trigger | 10 denemede hesap otomatik kilitlendi |

> "Tek başına yeterli değil — katmanlı savunma gerekir:
> Firewall + Audit + Lockout + Güçlü Parola Politikası."

---

## Temizlik (Demo Sonrası)

```sql
-- Trigger kaldır
DROP TRIGGER trg_bruteforce_guard ON ALL SERVER;

-- Audit kapat
ALTER SERVER AUDIT SPECIFICATION LoginFailSpec WITH (STATE = OFF);
DROP SERVER AUDIT SPECIFICATION LoginFailSpec;
ALTER SERVER AUDIT BruteForceAudit WITH (STATE = OFF);
DROP SERVER AUDIT BruteForceAudit;

-- Log tablosunu temizle
DROP TABLE IF EXISTS master.dbo.BF_FailedLogins;
```

```powershell
# Firewall kuralını kaldır
Remove-NetFirewallRule -DisplayName "Flask Lab 5001"
```
