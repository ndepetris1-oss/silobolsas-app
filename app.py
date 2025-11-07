from flask import Flask, render_template, request, redirect, jsonify
import csv, os
from datetime import datetime

app = Flask(__name__)

DATA_FILE = "silos.csv"

# Crear archivo CSV si no existe
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["qr", "cereal", "metros", "lat", "lon", "fecha_registro", "extraccion", "fecha_extraccion"])


@app.route('/')
def form():
    return render_template("form.html")


@app.route('/registrar', methods=['POST'])
def registrar():
    try:
        qr = request.form.get('qr')
        cereal = request.form.get('cereal')
        metros = request.form.get('metros')
        lat = request.form.get('lat')
        lon = request.form.get('lon')
        extraccion = request.form.get('extraccion')
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if extraccion == "SI" else ""

        # Guardar en CSV
        with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([qr, cereal, metros, lat, lon, fecha_registro, extraccion, fecha_extraccion])

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


@app.route('/panel')
def panel():
    registros = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            registros = list(reader)
    return render_template("panel.html", registros=registros)


@app.route('/eliminar/<qr>', methods=['POST'])
def eliminar(qr):
    registros = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        registros = [r for r in reader if r['qr'] != qr]

    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["qr", "cereal", "metros", "lat", "lon", "fecha_registro", "extraccion", "fecha_extraccion"])
        writer.writeheader()
        writer.writerows(registros)

    return redirect("/panel")


@app.route('/exportar')
def exportar():
    if not os.path.exists(DATA_FILE):
        return "No hay datos para exportar"
    return app.send_static_file(DATA_FILE)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
