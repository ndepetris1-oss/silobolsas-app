from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, json, io
from datetime import datetime
import pandas as pd

app = Flask(__name__)
DB = "silos.db"

# ---------------- DB ----------------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()

    c.execute("""
    CREATE TABLE IF NOT EXISTS silos (
        numero_qr TEXT PRIMARY KEY,
        cereal TEXT,
        estado TEXT,
        metros INTEGER,
        lat REAL,
        lon REAL,
        fecha_confeccion TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS muestreos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT,
        seccion TEXT,
        fecha TEXT,
        temperatura REAL,
        humedad REAL,
        datos TEXT,
        grado INTEGER,
        factor REAL,
        olor INTEGER,
        moho INTEGER,
        insectos INTEGER,
        chamico INTEGER
    )
    """)

    c.commit()
    c.close()

init_db()

# ---------------- CÁLCULOS ----------------
def grado_maiz(d):
    return max(
        1 if d["ph"] >= 75 else 2 if d["ph"] >= 72 else 3,
        1 if d["danados"] <= 3 else 2 if d["danados"] <= 8 else 3,
        1 if d["quebrados"] <= 2 else 2 if d["quebrados"] <= 5 else 3,
        1 if d["me"] <= 1 else 2 if d["me"] <= 2 else 3
    )

def factor_maiz(d):
    f = 100.0
    if d["danados"] > 8:
        f -= (d["danados"] - 8) * 1.0
    if d["quebrados"] > 5:
        f -= (d["quebrados"] - 5) * 0.25
    if d["me"] > 2:
        f -= (d["me"] - 2)
    if d["ph"] < 69:
        f -= (69 - d["ph"])
    return round(max(f, 0), 2)

# ---------------- VISTAS ----------------
@app.route("/")
@app.route("/api/export")
def export_excel():
    conn = db()
    rows = conn.execute("""
        SELECT s.numero_qr, s.cereal, s.estado, s.metros,
               s.fecha_confeccion,
               m.seccion, m.humedad, m.temperatura, m.grado, m.factor
        FROM silos s
        LEFT JOIN muestreos m ON s.numero_qr = m.numero_qr
    """).fetchall()
    conn.close()

    import pandas as pd
    df = pd.DataFrame([dict(r) for r in rows])

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="silo_bolsas.xlsx",
        as_attachment=True
    )
@app.route("/panel")
def panel():
    c = db()
    silos = c.execute("SELECT * FROM silos").fetchall()
    c.close()
    return render_template("panel.html", registros=silos)

@app.route("/form")
def form():
    return render_template("form.html")

# ---------------- API ----------------
@app.route("/api/save", methods=["POST"])
def save_silo():
    try:
        d = request.json
        c = db()
        c.execute("""
        INSERT OR REPLACE INTO silos
        (numero_qr, cereal, estado, metros, lat, lon, fecha_confeccion)
        VALUES (?,?,?,?,?,?,?)
        """, (
            d["numero_qr"],
            d["cereal"],
            d["estado"],
            d["metros"],
            d.get("lat"),
            d.get("lon"),
            d.get("fecha_confeccion", datetime.now().isoformat())
        ))
        c.commit()
        c.close()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.route("/api/muestreo", methods=["POST"])
def muestreo():
    d = request.json
    datos = d["datos"]

    grado = factor = None
    if d["cereal"].lower() == "maíz":
        grado = grado_maiz(datos)
        factor = factor_maiz(datos)
    else:
        factor = 100.0

    c = db()
    c.execute("""
    INSERT INTO muestreos
    (numero_qr, seccion, fecha, temperatura, humedad,
     datos, grado, factor, olor, moho, insectos, chamico)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["numero_qr"], d["seccion"], datetime.now().isoformat(),
        d["temperatura"], d["humedad"],
        json.dumps(datos), grado, factor,
        d["olor"], d["moho"], d["insectos"], d["chamico"]
    ))
    c.commit()
    c.close()

    return jsonify(grado=grado, factor=factor)

if __name__ == "__main__":
    app.run(debug=True)
