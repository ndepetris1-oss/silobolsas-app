from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

DB_PATH = "silobolsas.db"

# Función para inicializar la DB (si no existe)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS silobolsas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT UNIQUE,
            cereal TEXT,
            metros REAL,
            lat REAL,
            lon REAL,
            fecha_registro TEXT,
            extraccion TEXT,
            fecha_extraccion TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Página de registro de silo bolsa
@app.route("/form")
def form():
    numero_qr = request.args.get("id", "")
    return render_template("form.html", numero_qr=numero_qr)

# Guardar datos desde form o panel
@app.route("/api/save", methods=["POST"])
def save():
    data = request.json
    numero_qr = data.get("numero_qr")
    cereal = data.get("cereal")
    metros = data.get("metros")
    lat = data.get("lat")
    lon = data.get("lon")
    extraccion = data.get("extraccion")
    fecha_extraccion = data.get("fecha_extraccion")
    fecha_registro = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Verifica si ya existe el QR
        c.execute("SELECT id FROM silobolsas WHERE numero_qr = ?", (numero_qr,))
        existing = c.fetchone()
        if existing:
            # Actualiza si ya existe
            c.execute('''
                UPDATE silobolsas SET
                cereal=?,
                metros=?,
                lat=?,
                lon=?,
                extraccion=?,
                fecha_extraccion=?
                WHERE numero_qr=?
            ''', (cereal, metros, lat, lon, extraccion, fecha_extraccion, numero_qr))
        else:
            # Inserta nuevo registro
            c.execute('''
                INSERT INTO silobolsas
                (numero_qr, cereal, metros, lat, lon, fecha_registro, extraccion, fecha_extraccion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (numero_qr, cereal, metros, lat, lon, fecha_registro, extraccion, fecha_extraccion))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# Panel para ver todos los registros
@app.route("/panel")
def panel():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM silobolsas ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("panel.html", registros=rows)

# Exportar a Excel
@app.route("/export")
def export_excel():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM silobolsas", conn)
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SiloBolsas")
    output.seek(0)
    return send_file(output, download_name="silobolsas.xlsx", as_attachment=True)

# Borrar un registro por ID
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM silobolsas WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
