from flask import Flask, request
import pandas as pd

app = Flask(__name__)

EXCEL_FILE = "meters.xlsx"

@app.route("/meter/<int:meter_id>", methods=["GET", "POST"])
def meter_page(meter_id):

    df = pd.read_excel(EXCEL_FILE)

    row = df[df["id"] == meter_id]

    if row.empty:
        return "Счетчик не найден"

    index = row.index[0]

    if request.method == "POST":
        try:
            current_value = float(request.form.get("current"))
        except:
            return "Ошибка: введите число"


        df.at[index, "current"] = current_value

        df.to_excel(EXCEL_FILE, index=False)

        diff = float(current_value) - float(df.at[index, "prev"])

        return f"""
        <h1>Данные сохранены</h1>
        <p>Расход за месяц: {diff}</p>
        """

    data = row.iloc[0]

    return f"""
    <h1>Счетчик {data['meter']}</h1>

    <p>ИИН: {data['iin']}</p>
    <p>Контрагент: {data['name']}</p>
    <p>Предыдущие показания: {data['prev']}</p>

    <form method="POST">
        <input type="number" name="current" placeholder="Введите текущие показания" required>
        <button type="submit">Сохранить</button>
    </form>
    """

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)