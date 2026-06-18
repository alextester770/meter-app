from flask import Flask, request, send_file, jsonify, redirect, session
import sqlite3
import os
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = "meterapp_secret_key_2026"

def get_db():
    conn = sqlite3.connect("meters.db", timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else None

def fmt_prev(val):
    try:
        return f"{float(val):08.1f}"
    except:
        return "0000000.0"

@app.route("/meter/<meter_id>", methods=["GET", "POST"])
def meter_page(meter_id):
    conn = get_db()
    cur = conn.cursor()
    meter_id = str(meter_id).strip()

    # Определяем тип счётчика
    meter_type = None
    row = None

    cur.execute("SELECT rowid, * FROM meters WHERE id = ? ORDER BY period DESC LIMIT 1", (meter_id,))
    row = cur.fetchone()
    if row:
        meter_type = "electricity"

    if not row:
        cur.execute("SELECT rowid, * FROM meters WHERE idg = ? ORDER BY period DESC LIMIT 1", (meter_id,))
        row = cur.fetchone()
        if row:
            meter_type = "gas"

    if not row:
        cur.execute("SELECT rowid, * FROM meters WHERE idw = ? ORDER BY period DESC LIMIT 1", (meter_id,))
        row = cur.fetchone()
        if row:
            meter_type = "water"

    if row is None:
        return "Счетчик не найден"

    # Настройки в зависимости от типа
    if meter_type == "electricity":
        field_current = "current"
        field_edit    = "edit_count"
        prev_val      = row["prev"]
        cur_val       = row["current"]
        price         = row["ePrice"] or 0
        unit          = "кВт"
        icon          = "⚡"
    elif meter_type == "gas":
        field_current = "currentg"
        field_edit    = "edit_countg"
        prev_val      = row["prevg"]
        cur_val       = row["currentg"]
        price         = row["gPrice"] or 0
        unit          = "м³"
        icon          = "🔥"
    else:  # water
        field_current = "currentw"
        field_edit    = "edit_countw"
        prev_val      = row["prevw"]
        cur_val       = row["currentw"]
        price         = row["wPrice"] or 0
        unit           = "м³"
        icon          = "💧"

    message = ""

    if request.method == "POST":
        if get_setting("input_allowed") != "1":
            message = "❌ Приём показаний закрыт. Обратитесь к администратору."
        else:
            current_raw = request.form.get("current", "").strip()
            try:
                current_value = float(current_raw)
                prev_value    = float(prev_val) if prev_val else 0

                if current_value < prev_value:
                    message = "Ошибка: значение не может быть меньше предыдущего"
                else:
                    edit_count = row[field_edit] or 0
                    cur.execute(f"""
                        UPDATE meters
                        SET {field_current} = ?, {field_edit} = ?
                        WHERE rowid = ?
                    """, (current_value, edit_count + 1, row["rowid"]))
                    conn.commit()

                    # перечитываем строку
                    cur.execute("SELECT rowid, * FROM meters WHERE rowid = ?", (row["rowid"],))
                    row     = cur.fetchone()
                    cur_val = row[field_current]
                    message = "✅ Данные сохранены"

            except Exception as e:
                message = f"Ошибка: {e}"

    # Расчёты
    try:
        rashod = float(cur_val) - float(prev_val) if cur_val and prev_val else 0
    except:
        rashod = 0

    dolg   = row["dolg"] or 0
    rent   = row["rent"] or 0
    itogo  = dolg + rent + (rashod * price)

    prev_fmt  = fmt_prev(prev_val)
    cur_fmt   = cur_val if cur_val else "—"

    kaspi_url = (
        "https://kaspi.kz/pay/cotaltynalma"
        f"?10446={quote(str(row['name']))}"
        f"&10447={quote(str(row['iin']))}"
        f"&10448={quote(str(row['position']))}"
        f"&amount={int(itogo)}"
    )

    return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>{icon} Счётчик {meter_id}</title>
</head>
<body class="bg-light">
<div class="container mt-3">
  <div class="card shadow-sm p-3">
    <h5 class="mb-3">{icon} Счётчик № {meter_id}</h5>

    <table class="table table-bordered table-sm">
      <tr><td><b>ИИН</b></td><td>{row['iin']}</td></tr>
      <tr><td><b>Контрагент</b></td><td>{row['name']}</td></tr>
      <tr><td><b>Расположение</b></td><td>{row['position']}</td></tr>
      <tr><td><b>Предыдущие показания</b></td><td>{prev_fmt}</td></tr>
      <tr><td><b>Введённые показания</b></td><td>{cur_fmt}</td></tr>
      <tr><td><b>{unit} израсходовано</b></td><td>{rashod:.2f}</td></tr>
      <tr><td><b>Цена за {unit}</b></td><td>{price} ₸</td></tr>
    </table>

    {"<div class='alert alert-success'>" + message + "</div>" if "✅" in message else ""}
    {"<div class='alert alert-danger'>" + message + "</div>" if "Ошибка" in message else ""}

    <form method="POST">
      <input class="form-control mb-2" type="number" step="0.01"
             name="current" placeholder="Текущие показания ({unit})" required>
      <button class="btn btn-primary w-100">Сохранить</button>   
    <a href="/login/{row['iin']}" class="btn btn-outline-secondary w-100 mt-2">
      👤 Личный кабинет
    </a>  
    </form>

  </div>
</div>
</body>
</html>
"""


@app.route("/api/missing")
def api_missing():
    conn = get_db()
    cur = conn.cursor()

    period = request.args.get("period")
    org    = request.args.get("org")

    query = "SELECT * FROM meters WHERE 1=1"
    params = []

    if period:
        query += " AND period = ?"
        params.append(period[:7])

    if org:
        query += " AND org = ?"
        params.append(org)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        missing = []

        # Есть счётчик света но нет показаний
        if r["id"] and (not r["current"] or float(r["current"]) == 0):
            missing.append("Электро")

        # Есть счётчик газа но нет показаний
        if r["idg"] and (not r["currentg"] or float(r["currentg"]) == 0):
            missing.append("Газ")

        # Есть счётчик воды но нет показаний
        if r["idw"] and (not r["currentw"] or float(r["currentw"]) == 0):
            missing.append("Вода")

        # Выгружаем только если есть хоть одно незаполненное
        if missing:
            result.append({
                "iin":        r["iin"],
                "name":       r["name"],
                "position":   r["position"],
                "period":     r["period"],
                "org":        r["org"],
                "kod_dogovora": r["kod_dogovora"],
                "id":         r["id"],
                "idg":        r["idg"],
                "idw":        r["idw"],
                "prev":         r["prev"],      
                "prevg":        r["prevg"],     
                "prevw":        r["prevw"],
                "current":    r["current"],
                "currentg":   r["currentg"],
                "currentw":   r["currentw"],
                "missing":    ", ".join(missing)
            })

    return jsonify({"count": len(result), "meters": result})

@app.route("/api/import", methods=["POST"])
def api_import():
    conn = get_db()
    cur = conn.cursor()
    data = request.get_json()

    if not data:
        return jsonify({"error": "no data"}), 400

    period = data.get("period")
    meters = data.get("meters", [])

    if not period:
        return jsonify({"error": "period is required"}), 400

    period_clean = period[:7]
    added = 0
    skipped = 0

    for m in meters:
        meter_id = m.get("id")

        # Проверяем есть ли уже запись по id + period
        cur.execute("""
            SELECT rowid FROM meters
            WHERE id = ? AND period = ?
        """, (meter_id, period_clean))
        existing = cur.fetchone()

        if existing:
            # Запись уже есть — пропускаем
            skipped += 1
            continue

        # Проверяем есть ли пин для этого ИИН
        cur.execute("""
            SELECT pin FROM meters
            WHERE iin = ? AND pin IS NOT NULL
            LIMIT 1
        """, (m.get("iin"),))
        pin_row = cur.fetchone()
        pin = pin_row["pin"] if pin_row else m.get("pin")

        # Записи нет — добавляем
        cur.execute("""
            INSERT INTO meters
            (id, idg, idw,
             iin, name, position,
             prev, prevg, prevw,
             current, currentg, currentw,
             period, org, date, kod_dogovora,
             edit_count, edit_countg, edit_countw,
             dolg, rent,
             ePrice, gPrice, wPrice, pin)
            VALUES (?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?)
        """, (
            m.get("id"),
            m.get("idg"),
            m.get("idw"),
            m.get("iin"),
            m.get("name"),
            m.get("position"),
            m.get("prev"),
            m.get("prevg"),
            m.get("prevw"),
            None,  # current
            None,  # currentg
            None,  # currentw
            period_clean,
            m.get("org"),
            m.get("date", "").replace("T", " "),
            m.get("kod_dogovora"),
            0, 0, 0,
            m.get("dolg", 0),
            m.get("rent", 0),
            m.get("ePrice", 0),
            m.get("gPrice", 0),
            m.get("wPrice", 0),
            pin
        ))
        added += 1

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "period": period_clean,
        "added": added,
        "skipped": skipped
    })

@app.route("/api/export", methods=["GET"])
def api_export():
    conn = get_db()
    cur = conn.cursor()

    period = request.args.get("period")
    org = request.args.get("org")
    meter_id = request.args.get("id")

    query = "SELECT * FROM meters"
    params = []
    filters = []

    if period:
        filters.append("period = ?")
        params.append(period)
    if org:
        filters.append("org = ?")
        params.append(org)
    if meter_id:
        filters.append("id = ?")
        params.append(meter_id)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return jsonify({"count": len(rows), "meters": [dict(r) for r in rows]})
    
@app.route("/", methods=["GET", "POST"])
def index():
    error = ""
    if request.method == "POST":
        iin = request.form.get("iin", "").strip()
        if iin:
            return redirect(f"/login/{iin}")
        error = "Введите ИИН"

    return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>Личный кабинет</title>
</head>
<body class="bg-light">
<div class="container mt-5">
  <div class="card shadow-sm p-4" style="max-width:400px; margin:auto">
    <h5 class="mb-3 text-center">Личный кабинет арендатора</h5>
    {"<div class='alert alert-danger'>" + error + "</div>" if error else ""}
    <form method="POST">
      <input class="form-control mb-3" type="text" name="iin"
             placeholder="Введите ваш ИИН" maxlength="12" required>
      <button class="btn btn-primary w-100">Далее</button>
    </form>
  </div>
</div>
</body>
</html>
"""

# Кабинет по ИИН
@app.route("/cabinet/<iin>", methods=["GET"])
def cabinet(iin):
    if not session.get(f"auth_{iin}"):
        return redirect(f"/login/{iin}")
    
    conn = get_db()
    cur = conn.cursor()

    # Получаем все периоды для выбора
    cur.execute("""
        SELECT DISTINCT period FROM meters
        WHERE iin = ?
        ORDER BY period DESC
    """, (iin,))
    periods = [r["period"] for r in cur.fetchall()]

    if not periods:
        return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container mt-5">
  <div class="card shadow-sm p-4" style="max-width:500px; margin:auto">
    <h5>ИИН не найден</h5>
    <a href="/" class="btn btn-secondary mt-3">← Назад</a>
  </div>
</div>
</body>
</html>
"""

    # Берём период из параметра или последний
    period = request.args.get("period", periods[0])

    # Получаем все счётчики по ИИН и периоду
    cur.execute("""
        SELECT * FROM meters
        WHERE iin = ? AND period = ?
    """, (iin, period))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "Данные за этот период не найдены"

    # Имя контрагента берём из первой строки
    name = rows[0]["name"]

    # Строим таблицу по каждой точке
    total_itogo = 0
    rows_html = ""

    for r in rows:
        try:
            kwt = float(r["current"]) - float(r["prev"]) if r["current"] else 0
        except:
            kwt = 0

        try:
            kwtg = float(r["currentg"]) - float(r["prevg"]) if r["currentg"] and r["prevg"] else 0
        except:
            kwtg = 0

        try:
            kwtw = float(r["currentw"]) - float(r["prevw"]) if r["currentw"] and r["prevw"] else 0
        except:
            kwtw = 0

        dolg   = r["dolg"] or 0
        rent   = r["rent"] or 0
        eprice = r["ePrice"] or 0
        gprice = r["gPrice"] or 0
        wprice = r["wPrice"] or 0

        itogo = rent + (kwt * eprice) + (kwtg * gprice) + (kwtw * wprice)
        total_itogo += itogo

        # Собираем строки таблицы заранее
        elektro_html = ""
        if r['id']:
            elektro_html = f"""
            <tr><td>⚡ Электро пред/тек</td><td>{fmt_prev(r['prev'])} / {r['current'] or '—'}</td></tr>
            <tr><td>⚡ кВт расход</td><td>{kwt:.1f}</td></tr>
            <tr><td>⚡ Цена за кВт</td><td>{eprice} ₸</td></tr>
            """

        voda_html = ""
        if r['idw']:
            voda_html = f"""
            <tr><td>💧 Вода пред/тек</td><td>{fmt_prev(r['prevw'])} / {r['currentw'] or '—'}</td></tr>
            <tr><td>💧 м³ расход</td><td>{kwtw:.1f}</td></tr>
            <tr><td>💧 Цена за м³</td><td>{wprice} ₸</td></tr>
            """

        gaz_html = ""
        if r['idg']:
            gaz_html = f"""
            <tr><td>🔥 Газ пред/тек</td><td>{fmt_prev(r['prevg'])} / {r['currentg'] or '—'}</td></tr>
            <tr><td>🔥 м³ расход</td><td>{kwtg:.1f}</td></tr>
            <tr><td>🔥 Цена за м³</td><td>{gprice} ₸</td></tr>
            """

        rows_html += f"""
        <div class="card mb-3 shadow-sm">
          <div class="card-header"><b>{r['position']}</b></div>
          <div class="card-body p-2">
            <table class="table table-sm table-bordered mb-0">
              <tr><td>Договор</td><td>{r['kod_dogovora']}</td></tr>
              {elektro_html}
              {voda_html}
              {gaz_html}
              <tr><td>Аренда</td><td>{rent} ₸</td></tr>
              <tr class="table-warning"><td><b>Итого по точке</b></td><td><b>{itogo:.2f} ₸</b></td></tr>
            </table>
          </div>
        </div>
        """
    dolg_total = rows[0]["dolg"] or 0
    total_itogo += dolg_total        
    kaspi_url_total = (
        "https://kaspi.kz/pay/cotaltynalma"
        f"?10446={quote(str(name))}"
        f"&10447={quote(str(iin))}"
        f"&10448={quote('Аренда')}"
        f"&amount={int(total_itogo)}"
    )
    # Селектор периодов
    options_html = "".join([
        f"<option value='{p}' {'selected' if p == period else ''}>{p}</option>"
        for p in periods
    ])

    return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>Кабинет — {name}</title>
</head>
<body class="bg-light">
<div class="container mt-3">

  <div class="card shadow-sm p-3 mb-3">
    <h5>{name}</h5>
    <p class="mb-1 text-muted">ИИН: {iin}</p>
    <select class="form-select" onchange="location.href='/cabinet/{iin}?period='+this.value">
      {options_html}
    </select>
  </div>

  {rows_html}

  <div class="card shadow p-3 mb-4">
    <h5 class="text-center">Итого за {period}</h5>
    <table class="table table-sm mb-2">
      <tr><td>Сумма долга на текущий период</td><td class="text-end">{dolg_total} ₸</td></tr>
      <tr><td>Стоимость аренды и комп. платежей</td><td class="text-end">{total_itogo - dolg_total:.2f} ₸</td></tr>
    </table>
    <h3 class="text-center text-primary">{total_itogo:.2f} ₸</h3>
    <a href="{kaspi_url_total}" class="btn btn-warning w-100 mt-2" target="_blank">
      💳 Оплатить через Kaspi
    </a>
  </div>

  <a href="/" class="btn btn-secondary w-100 mb-4">← На главную</a>

</div>
</body>
</html>
"""

@app.route("/login/<iin>", methods=["GET", "POST"])
def login(iin):
    error = ""
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT pin FROM meters 
            WHERE iin = ? 
            AND pin IS NOT NULL
            AND period = (
                SELECT MAX(period) FROM meters WHERE iin = ?
            )
        """, (iin, iin))
        rows_pin = cur.fetchall()
        conn.close()

        # Проверяем все пины последнего периода
        valid = any(r["pin"] == pin for r in rows_pin)

        if valid:
            session[f"auth_{iin}"] = True
            return redirect(f"/cabinet/{iin}")
        else:
            error = "Неверный пин-код"

    return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>Вход</title>
</head>
<body class="bg-light">
<div class="container mt-5">
  <div class="card shadow-sm p-4" style="max-width:400px; margin:auto">
    <h5 class="mb-3 text-center">Введите пин-код</h5>
    <p class="text-center text-muted">ИИН: {iin}</p>
    {"<div class='alert alert-danger'>" + error + "</div>" if error else ""}
    <form method="POST">
      <input class="form-control mb-3 text-center fs-4" type="password"
             name="pin" placeholder="• • • •" maxlength="4" required>
      <button class="btn btn-primary w-100">Войти</button>
    </form>
    <a href="/" class="btn btn-secondary w-100 mt-2">← Назад</a>
  </div>
</div>
</body>
</html>
"""

@app.route("/api/update_readings", methods=["POST"])
def update_readings():
    conn = get_db()
    cur = conn.cursor()
    data = request.get_json()

    if not data:
        return jsonify({"error": "no data"}), 400

    meters = data.get("meters", [])
    updated = 0
    errors = []

    for m in meters:
        period = m.get("period", "")[:7]

        # Обновляем только те поля которые переданы и не пустые
        fields = []
        params = []

        if m.get("current") not in (None, ""):
            fields.append("current = ?, edit_count = edit_count + 1")
            params.append(float(m.get("current")))

        if m.get("currentg") not in (None, ""):
            fields.append("currentg = ?, edit_countg = edit_countg + 1")
            params.append(float(m.get("currentg")))

        if m.get("currentw") not in (None, ""):
            fields.append("currentw = ?, edit_countw = edit_countw + 1")
            params.append(float(m.get("currentw")))

        if not fields:
            continue

        params.append(m.get("id"))
        params.append(period)

        cur.execute(f"""
            UPDATE meters
            SET {', '.join(fields)}
            WHERE id = ? AND period = ?
        """, params)

        if cur.rowcount > 0:
            updated += 1
        else:
            errors.append(m.get("id"))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "updated": updated,
        "errors": errors
    })

@app.route("/api/clear_period", methods=["POST"])
def clear_period():
    conn = get_db()
    cur = conn.cursor()
    data = request.get_json()

    period = data.get("period")
    if not period:
        return jsonify({"error": "period required"}), 400

    cur.execute("DELETE FROM meters WHERE period = ?", (period[:7],))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    return jsonify({"status": "ok", "deleted": deleted, "period": period[:7]})


@app.route("/api/clear_all", methods=["POST"])
def clear_all():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM meters")
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    return jsonify({"status": "ok", "deleted": deleted})

@app.route("/api/open_period", methods=["POST"])
def open_period():
    conn = get_db()
    conn.execute("UPDATE settings SET value = '1' WHERE key = 'input_allowed'")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "input_allowed": True})

@app.route("/api/close_period", methods=["POST"])
def close_period():
    conn = get_db()
    conn.execute("UPDATE settings SET value = '0' WHERE key = 'input_allowed'")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "input_allowed": False})

@app.route("/api/input_status", methods=["GET"])
def input_status():
    allowed = get_setting("input_allowed")
    return jsonify({"input_allowed": allowed == "1"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    