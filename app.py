from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import pandas as pd
import io
from datetime import datetime

app = Flask(__name__)

# -----------------------------------
# Inicializar base de datos
# -----------------------------------
def init_db():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS silobolsas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT,
            cereal TEXT,
            metros INTEGER,
            lat REAL,
            lon REAL,
            fecha TEXT,
            extraccion TEXT,
            fecha_extraccion TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------------
# Rutas principales
# -----------------------------------
@app.route("/")
def home():
    return render_template("panel.html")

@app.route("/form")
def form():
    numero_qr = request.args.get("id", "")
    return render_template("form.html", numero_qr=numero_qr)

# -----------------------------------
# Guardar datos (crear o actualizar)
# -----------------------------------
@app.route("/api/save", methods=["POST"])
def save_data():
    data = request.get_json()
    numero_qr = data.get("numero_qr")
    cereal = data.get("cereal")
    metros = data.get("metros")
    lat = data.get("lat")
    lon = data.get("lon")
    extraccion = data.get("extraccion")
    fecha_extraccion = data.get("fecha_extraccion")

    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()

    # Verificar si ya existe el número QR
    c.execute("SELECT id FROM silobolsas WHERE numero_qr = ?", (numero_qr,))
    existing = c.fetchone()

    if existing:
        # Actualizar solo extracción y fecha_extraccion
        c.execute("""
            UPDATE silobolsas
            SET extraccion = ?, fecha_extraccion = ?
            WHERE numero_qr = ?
        """, (extraccion, fecha_extraccion, numero_qr))
    else:
        # Insertar nuevo registro
        c.execute("""
            INSERT INTO silobolsas (numero_qr, cereal, metros, lat, lon, fecha, extraccion, fecha_extraccion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero_qr,
            cereal,
            metros,
            lat,
            lon,
            datetime.now().isoformat(),
            extraccion,
            fecha_extraccion
        ))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# -----------------------------------
# Listar datos
# -----------------------------------
@app.route("/api/list", methods=["GET"])
def list_data():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("""
        SELECT id, numero_qr, cereal, metros, lat, lon, fecha, extraccion, fecha_extraccion
        FROM silobolsas
        ORDER BY id DESC
    """)
    data = c.fetchall()
    conn.close()
    return jsonify(data)

# -----------------------------------
# Marcar extracción (actualiza fila)
# -----------------------------------
@app.route("/api/extract/<int:id>", methods=["POST"])
def mark_extract(id):
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    fecha = datetime.now().isoformat()
    c.execute("""
        UPDATE silobolsas
        SET extraccion = 'SI', fecha_extraccion = ?
        WHERE id = ?
    """, (fecha, id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# -----------------------------------
# Eliminar registro
# -----------------------------------
@app.route("/api/delete/<int:id>", methods=["DELETE"])
def delete_data(id):
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("DELETE FROM silobolsas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# -----------------------------------
# Exportar a Excel
# -----------------------------------
@app.route("/export", methods=["GET"])
def export_excel():
    conn = sqlite3.connect("silobolsas.db")
    df = pd.read_sql_query("SELECT * FROM silobolsas", conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SiloBolsas")

    output.seek(0)
    return send_file(
        output,
        download_name="silobolsas.xlsx",
        as_attachment=True
    )

# -----------------------------------
# Iniciar servidor Flask
# -----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
