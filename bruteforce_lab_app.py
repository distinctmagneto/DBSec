"""
MSSQL Brute Force Lab
=====================
Login formu = gerçek MSSQL bağlantısı dener.
Doğru credentials → SUGGESTION tablosuna yazar.
Yanlış credentials → hata.

Brute force hedefi: MSSQL kullanıcı adı + parolası

Kali'den HTTP brute force:
  hydra -L users.txt -P /usr/share/wordlists/rockyou.txt \
    http-post-form \
    "//WINDOWS_IP:5001/:username=^USER^&password=^PASS^:Hatalı" \
    -t 8 -V

Kali'den doğrudan MSSQL brute force:
  hydra -L users.txt -P passwords.txt \
    mssql://155.223.166.100:51433 -t 4 -V
"""

import pymssql
from flask import Flask, request, session, redirect, render_template_string

app = Flask(__name__)
app.secret_key = "lab_gizli_anahtar_2024"

SERVER   = "155.223.166.100"
PORT     = 51433
DATABASE = "EGELAB"


def try_connect(username, password):
    """Verilen credentials ile MSSQL bağlantısı dener. Başarılıysa conn döner."""
    return pymssql.connect(
        server=SERVER,
        port=PORT,
        database=DATABASE,
        user=username,
        password=password,
        timeout=3
    )


# ─── Şablonlar ──────────────────────────────────────────────────────────

LOGIN_TMPL = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Öneri Sistemi — Giriş</title>
<style>
  body { font-family: Arial, sans-serif; background: #f0f2f5;
         display: flex; justify-content: center; margin-top: 80px; }
  .box { background: white; padding: 32px 40px; border-radius: 8px;
         box-shadow: 0 2px 12px rgba(0,0,0,.12); width: 360px; }
  h2   { margin: 0 0 6px; color: #333; text-align: center; }
  .sub { text-align:center; color:#888; font-size:12px; margin-bottom:24px; }
  label { display: block; margin-bottom: 4px; color: #555; font-size: 14px; }
  input { width: 100%; padding: 9px 12px; margin-bottom: 16px;
          border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
  button { width: 100%; padding: 10px; background: #1a73e8; color: white;
           border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }
  button:hover { background: #1558b0; }
  .err { background: #fce8e6; color: #c62828; padding: 10px 14px;
         border-radius: 4px; margin-bottom: 16px; font-size: 13px; }
  .info { background: #e8f0fe; color: #1a56bb; padding: 10px 14px;
          border-radius: 4px; margin-top: 16px; font-size: 12px; }
</style>
</head>
<body>
<div class="box">
  <h2>Öneri Sistemi</h2>
  <div class="sub">MSSQL · {{ server }}</div>
  {% if hata %}<div class="err">{{ hata }}</div>{% endif %}
  <form method="POST">
    <label>Kullanıcı Adı (MSSQL)</label>
    <input name="username" autocomplete="off" value="{{ username }}">
    <label>Parola</label>
    <input type="password" name="password">
    <button type="submit">Giriş Yap</button>
  </form>
  <div class="info">
    Giriş denendiğinde <b>gerçek MSSQL bağlantısı</b> kurulur.<br>
    Rate limit yok · Lockout yok · Log yok
  </div>
</div>
</body>
</html>"""

SUGGESTION_TMPL = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Öneri Paneli</title>
<style>
  body { font-family: Arial, sans-serif; background: #f0f2f5; margin: 0; }
  .nav { background: #1a73e8; color: white; padding: 14px 24px;
         display: flex; justify-content: space-between; align-items: center; }
  .nav a { color: white; text-decoration: none; font-size: 14px;
           background: rgba(255,255,255,.2); padding: 6px 14px; border-radius: 4px; }
  .badge { background: #34a853; color: white; font-size: 11px;
           padding: 2px 8px; border-radius: 10px; margin-left: 10px; }
  .container { max-width: 620px; margin: 40px auto; padding: 0 16px; }
  .card { background: white; padding: 28px; border-radius: 8px;
          box-shadow: 0 2px 12px rgba(0,0,0,.1); margin-bottom: 20px; }
  h3 { margin: 0 0 16px; color: #333; }
  label { display: block; margin-bottom: 4px; color: #555; font-size: 14px; }
  textarea { width: 100%; padding: 10px 12px; border: 1px solid #ddd;
             border-radius: 4px; font-size: 14px; resize: vertical;
             box-sizing: border-box; min-height: 90px; }
  button { margin-top: 10px; padding: 9px 22px; background: #1a73e8;
           color: white; border: none; border-radius: 4px; cursor: pointer; }
  .ok  { background: #e6f4ea; color: #2e7d32; padding: 9px 14px;
         border-radius: 4px; margin-bottom: 14px; font-size: 14px; }
  .err { background: #fce8e6; color: #c62828; padding: 9px 14px;
         border-radius: 4px; margin-bottom: 14px; font-size: 13px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { background:#f1f3f4; padding:8px 10px; text-align:left; color:#555; }
  td { padding:8px 10px; border-bottom:1px solid #eee; color:#444; }
  tr:last-child td { border-bottom:none; }
  .empty { color:#999; font-size:14px; text-align:center; padding:20px 0; }
</style>
</head>
<body>
<div class="nav">
  <span>
    Öneri Paneli
    <span class="badge">{{ username }} @ MSSQL</span>
  </span>
  <a href="/cikis">Çıkış</a>
</div>
<div class="container">
  <div class="card">
    <h3>Yeni Öneri</h3>
    {% if mesaj %}<div class="{{ mesaj_tip }}">{{ mesaj }}</div>{% endif %}
    <form method="POST">
      <label>Öneri Metni</label>
      <textarea name="oneri" placeholder="Önerinizi yazın..."></textarea>
      <button type="submit">Gönder</button>
    </form>
  </div>
  <div class="card">
    <h3>Son Öneriler (SUGGESTION tablosu)</h3>
    {% if oneriler %}
    <table>
      <tr><th>ID</th><th>Ad Soyad</th><th>Tarih</th><th>Öneri</th></tr>
      {% for row in oneriler %}
      <tr>
        <td>{{ row[0] }}</td>
        <td>{{ row[1] }}</td>
        <td>{{ row[2] }}</td>
        <td>{{ row[3] }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <div class="empty">Henüz öneri yok veya SELECT yetkisi yok.</div>
    {% endif %}
  </div>
</div>
</body>
</html>"""


# ─── Route'lar ──────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def giris():
    hata     = None
    username = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # ================================================================
        # ZAFİYETLİ ALAN:
        # - Her denemede gerçek MSSQL bağlantısı kurulur
        # - Rate limit yok → hydra/medusa serbestçe çalışır
        # - Lockout yok    → sonsuz deneme yapılabilir
        # - Log yok        → saldırı görünmez
        # ================================================================
        try:
            conn = try_connect(username, password)
            conn.close()
            session["username"] = username
            session["password"] = password
            return redirect("/panel")
        except pymssql.OperationalError:
            hata = f"Hatalı kullanıcı adı veya parola."
        except Exception as e:
            hata = f"Bağlantı hatası: {e}"

    return render_template_string(
        LOGIN_TMPL, hata=hata, username=username,
        server=f"{SERVER}:{PORT}"
    )


@app.route("/panel", methods=["GET", "POST"])
def panel():
    if "username" not in session:
        return redirect("/")

    mesaj     = None
    mesaj_tip = "ok"
    oneriler  = []

    if request.method == "POST":
        oneri = request.form.get("oneri", "").strip()
        if oneri:
            try:
                conn   = try_connect(session["username"], session["password"])
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO SUGGESTION (NAMESURNAME, DATE_, SUGGESTIONTEXT) "
                    "VALUES (%s, GETDATE(), %s)",
                    (session["username"], oneri)
                )
                conn.commit()
                conn.close()
                mesaj = "Öneri SUGGESTION tablosuna eklendi."
            except Exception as e:
                mesaj     = f"INSERT hatası: {e}"
                mesaj_tip = "err"

    try:
        conn   = try_connect(session["username"], session["password"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TOP 15 ID, NAMESURNAME, "
            "CONVERT(varchar, DATE_, 120), SUGGESTIONTEXT "
            "FROM SUGGESTION ORDER BY ID DESC"
        )
        oneriler = cursor.fetchall()
        conn.close()
    except Exception:
        pass

    return render_template_string(
        SUGGESTION_TMPL,
        username=session["username"],
        mesaj=mesaj,
        mesaj_tip=mesaj_tip,
        oneriler=oneriler
    )


@app.route("/cikis")
def cikis():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    print("=" * 55)
    print(f"  MSSQL Brute Force Lab")
    print(f"  Hedef DB : {SERVER}:{PORT} / {DATABASE}")
    print(f"  Web      : http://localhost:5001")
    print(f"  Kali     : http://WINDOWS_IP:5001")
    print("=" * 55)
    print("  ZAFİYET  : Rate limit yok, lockout yok, log yok")
    print("  Her giriş denemesi = gerçek MSSQL auth isteği")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5001, debug=False)
