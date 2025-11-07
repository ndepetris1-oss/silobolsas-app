from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import io

app = Flask(__name__)

# --- Inicializar DB ---
def init_db():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS silobolsas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT UNIQUE,
            cereal TEXT,
            metros INTEGER,
            lat REAL,
            lon REAL,
            fecha_creacion TEXT,
            extraido INTEGER DEFAULT 0,
            fecha_extraccion TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Guardar / Actualizar silo ---
@app.route("/api/save", methods=["POST"])
def save_data():
    data = request.json
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()

    # Ver si ya existe el silo
    c.execute("SELECT * FROM silobolsas WHERE numero_qr = ?", (data["numero_qr"],))
    existing = c.fetchone()

    if existing:
        # Si ya existe, actualizamos los datos
        c.execute("""
            UPDATE silobolsas
            SET cereal=?, metros=?, lat=?, lon=?, extraido=?, fecha_extraccion=?
            WHERE numero_qr=?
        """, (
            data.get("cereal"),
            data.get("metros"),
            data.get("lat"),
            data.get("lon"),
            data.get("extraido", 0),
            data.get("fecha_extraccion"),
            data["numero_qr"]
        ))
    else:
        # Si es nuevo, lo insertamos
        c.execute("""
            INSERT INTO silobolsas (numero_qr, cereal, metros, lat, lon, fecha_creacion, extraido)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["numero_qr"],
            data.get("cereal"),
            data.get("metros"),
            data.get("lat"),
            data.get("lon"),
            datetime.now().isoformat(),
            data.get("extraido", 0)
        ))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# --- Obtener todos los silos ---
@app.route("/api/list", methods=["GET"])
def list_silos():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("SELECT * FROM silobolsas")
    rows = c.fetchall()
    conn.close()

    silos = []
    for r in rows:
        silos.append({
            "id": r[0],
            "numero_qr": r[1],
            "cereal": r[2],
            "metros": r[3],
            "lat": r[4],
            "lon": r[5],
            "fecha_creacion": r[6],
            "extraido": r[7],
            "fecha_extraccion": r[8]
        })
    return jsonify(silos)

# --- Borrar silo ---
@app.route("/api/delete/<numero_qr>", methods=["DELETE"])
def delete_silo(numero_qr):
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("DELETE FROM silobolsas WHERE numero_qr=?", (numero_qr,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# --- Exportar a Excel ---
@app.route("/api/export", methods=["GET"])
def export_excel():
    conn = sqlite3.connect("silobolsas.db")
    df = pd.read_sql_query("SELECT * FROM silobolsas", conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Silos")

    output.seek(0)
    return send_file(output, download_name="silos.xlsx", as_attachment=True)

# --- Formularios y Panel ---
@app.route("/form")
def form_page():
    return render_template("form.html")

@app.route("/panel")
def panel_page():
    return render_template("panel.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
# --- NUEVAS RUTAS: borrar registro y exportar a Excel ---

from flask import send_file
import io
import pandas as pd

# Ruta para borrar un registro por número de QR
@app.route("/api/delete", methods=["POST"])
def delete_row():
    data = request.get_json()
    numero_qr = data.get("numero_qr")
    if not numero_qr:
        return jsonify({"status": "error", "message": "QR faltante"}), 400

    # Leer datos existentes
    if not os.path.exists("data.csv"):
        return jsonify({"status": "error", "message": "No hay datos"}), 404

    df = pd.read_csv("data.csv", dtype=str)
    antes = len(df)
    df = df[df["numero_qr"] != numero_qr]
    despues = len(df)

    if antes == despues:
        return jsonify({"status": "error", "message": "Registro no encontrado"}), 404

    df.to_csv("data.csv", index=False)
    return jsonify({"status": "ok"})

# Ruta para exportar todo el CSV a un archivo Excel
@app.route("/api/export")
def export_excel():
    if not os.path.exists("data.csv"):
        return jsonify({"status": "error", "message": "No hay datos"}), 404

    df = pd.read_csv("data.csv")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SiloBolsas")

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="silo_bolsas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

