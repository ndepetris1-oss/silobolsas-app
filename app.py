from flask import Flask, render_template, request, jsonify, send_file
import csv
import os
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)

DATA_FILE = "data.csv"

# Crear archivo CSV si no existe
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["numero_qr", "cereal", "metros", "lat", "lon", "fecha"])


# === 1️⃣ Formulario ===
@app.route("/form")
def form():
    numero_qr = request.args.get("id", "N/A")
    return render_template("form.html", numero_qr=numero_qr)


# === 2️⃣ Guardar datos ===
@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            data["numero_qr"],
            data["cereal"],
            data["metros"],
            data["lat"],
            data["lon"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
    return jsonify({"status": "ok"})


# === 3️⃣ Panel con mapa ===
@app.route("/panel")
def panel():
    silos = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # saltar encabezado
        for row in reader:
            try:
                silos.append([row[0], row[1], int(row[2]), float(row[3]), float(row[4]), row[5]])
            except:
                pass
    return render_template("panel.html", silos=silos)


# === 4️⃣ Eliminar registro ===
@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json()
    numero_qr = data.get("numero_qr")

    rows = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if row[0] != numero_qr:
                rows.append(row)

    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    return jsonify({"status": "deleted", "numero_qr": numero_qr})


# === 5️⃣ Exportar a Excel ===
@app.route("/exportar_excel")
def exportar_excel():
    df = pd.read_csv(DATA_FILE)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Silobolsas")
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="silobolsas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# === 6️⃣ Página raíz (redirige al panel) ===
@app.route("/")
def home():
    return "<h3>✅ App de Silobolsas activa. Ir a <a href='/panel'>Panel</a></h3>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
