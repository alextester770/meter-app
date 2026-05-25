from flask import Flask, request, send_file
import pandas as pd

app = Flask(__name__)

EXCEL_FILE = "meters.xlsx"

@app.route("/meter/<meter_id>", methods=["GET", "POST"])
def meter_page(meter_id):

    df = pd.read_excel(EXCEL_FILE)

    df["id"] = df["id"].fillna("").astype(str).str.strip()
    meter_id = str(meter_id).strip()

    row = df[df["id"] == meter_id]

    if row.empty:
        return "Счетчик не найден"

    index = row.index[0]

    if request.method == "POST":
        current_raw = request.form.get("current")
        
        if current_raw is None or current_raw.strip() == "":
            return "Ошибка: пустое значение"
        try:
            current_value = float(request.form.get("current"))
            prev_value = float(df.at[index, "prev"])

        # защита от уменьшения
            if current_value < prev_value:
                return "Ошибка: значение не может быть меньше предыдущего"

        # расчет расхода
            diff = current_value - prev_value

        # сохранение
            df.at[index, "current"] = current_value
            df.to_excel(EXCEL_FILE, index=False)

            return f"""
        <h1>Данные сохранены</h1>
        <p>Расход за месяц: {diff}</p>
        """

        except:
            return "Ошибка: введите число"

    data = row.iloc[0]

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

    <p><b>ИИН:</b> {data['iin']}</p>
    <p><b>Контрагент:</b> {data['name']}</p>
    <p><b>Расположение:</b> {data['position']}</p>
    <p><b>Предыдущие:</b> {data['prev']}</p>
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
    
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
