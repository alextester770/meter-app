from flask import Flask, request, send_file, jsonify
import sqlite3
import os

app = Flask(__name__)
def get_db():
    conn = sqlite3.connect(
        "meters.db",
        timeout=30
        
        
    )

    conn.row_factory = sqlite3.Row
    return conn



@app.route("/meter/<meter_id>", methods=["GET", "POST"])
def meter_page(meter_id):

    conn = get_db()
    cur = conn.cursor()

    meter_id = str(meter_id).strip()

    cur.execute("""
    SELECT * FROM meters
    WHERE id = ?
    ORDER BY period DESC
    LIMIT 1
    """, (meter_id,))
    row = cur.fetchone()

    if row is None:
        return "Счетчик не найден"

    if request.method == "POST":
        current_raw = request.form.get("current")
        
        if current_raw is None or current_raw.strip() == "":
            return "Ошибка: пустое значение"
        try:
            
            
            current_value = float(request.form.get("current"))
            prev_value = float(row["prev"])

        # защита от уменьшения
            if current_value < prev_value:
                return "Ошибка: значение не может быть меньше предыдущего"

        # расчет расхода
            diff = current_value - prev_value

        # сохранение
            edit_count = row["edit_count"] or 0
            current_period = row["period"]
            print("ID =", meter_id)
            print("PERIOD =", current_period)
            cur.execute("""
                UPDATE meters
                SET current = ?,
                edit_count = ?
                WHERE id = ?
                AND period = ?
            """, (
    current_value,
    edit_count + 1,
    meter_id,
    current_period
            ))


            print("UPDATED =", cur.rowcount)
            
            conn.commit()

            return f"""
        <h1>Данные сохранены</h1>
        <p>Расход за месяц: {diff}</p>
        """

        except:
            return "Ошибка: введите число"

    data = row

    return f"""
  <!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>

<body class="bg-light">

<div class="container mt-3">

  <div class="card shadow-sm p-3">
    <h4 class="mb-3">Счетчик № {data['id']}</h4>

    <p><b>ИИН:</b> {data['iin']}<b> Контрагент: </b>{data['name']}</p>
    <p><b>Расположение:</b> {data['position']}</p>
    <p><b>Предыдущие:</b> {data['prev']}<b> Введенные в этом месяце: </b>{data['current']}</p>
    <p><b>Текущий долг: </b> {data['dolg']}<b> на месяц: </b>{data['date']}</p>
    <form method="POST">
      <input class="form-control mb-2" type="number" name="current" placeholder="Текущие показания" required>
      <button class="btn btn-primary w-100">Сохранить</button>
    </form>

  </div>

</div>

</body>
</html>
    """
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files["file"]
        file.save("meters.xlsx")
        return "Файл загружен успешно"

    return """
    <h2>Загрузка Excel</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="file">
        <button type="submit">Загрузить</button>
    </form>
    """
@app.route("/download")
def download():
    return send_file("meters.xlsx", as_attachment=True)
    


@app.route("/api/meters", methods=["GET"])
def api_get_meters():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM meters
    WHERE id = ?
    ORDER BY period DESC
    LIMIT 1
    """, (meter_id,))
    row = cur.fetchone()

    conn.close()

    return jsonify([dict(row) for row in rows])
    
@app.route("/api/missing")
def api_missing():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM meters
        WHERE current IS NULL OR current = prev
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])    

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

    # 1. удаляем только текущий период
    cur.execute("DELETE FROM meters WHERE period = ?", (period,))

    # 2. вставляем новые данные
    period_clean = period[:7]
    for m in meters:
        cur.execute("""
            INSERT INTO meters
            (id, iin, name, position, prev, current, period, edit_count, org, date, kod_dogovora)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m.get("id"),
            m.get("iin"),
            m.get("name"),
            m.get("position"),
            m.get("prev"),
            None,
            period_clean,
            0,
            m.get("org"),
            m.get("date", "").replace("T", " "),
            m.get("kod_dogovora")
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "period": period,
        "count": len(meters)
    })
    
@app.route("/api/export", methods=["GET"])
def api_export():
    conn = get_db()
    cur = conn.cursor()

    period = request.args.get("period")
    meter_id = request.args.get("id")
    
    query = "SELECT id, iin, name, position, prev, current, period, edit_count, org,kod_dogovora, date FROM meters"
    params = []

    filters = []

    if period:
        filters.append("period = ?")
        params.append(period)

    if meter_id:
        filters.append("id = ?")
        params.append(meter_id)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    cur.execute(query, params)
    rows = cur.fetchall()

    conn.close()

    result = [dict(r) for r in rows]

    return jsonify({
        "count": len(result),
        "meters": result
    })

if __name__ == "__main__":    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
