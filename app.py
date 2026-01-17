from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, json, io
from datetime import datetime
import pandas as pd

app = Flask(__name__)
DB = "silos.db"

# ================= DB =================
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
        seccion TEXT,               -- punta / medio / final
        fecha TEXT,
        temperatura REAL,
        humedad REAL,
        datos TEXT,                 -- rubros comerciales
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

# ================= UTILIDADES =================
def grado_maiz(d):
    g = []
    g.append(1 if d["ph"] >= 75 else 2 if d["ph"] >= 72 else 3)
    g.append(1 if d["danados"] <= 3 else 2 if d["danados"] <= 8 else 3)
    g.append(1 if d["quebrados"] <= 2 else 2 if d["quebrados"] <= 5 else 3)
    g.append(1 if d["me"] <= 1 else 2 if d["me"] <= 2 else 3)
    return max(g)

def factor_maiz(d, olor, moho):
    f = 100.0
    if d["danados"] > 8:
        f -= (d["danados"] - 8)
    if d["quebrados"] > 5:
        f -= (d["quebrados"] - 5) * 0.25
    if d["me"] > 2:
        f -= (d["me"] - 2)
    if d["ph"] < 69:
        f -= (69 - d["ph"])
    if olor:
        f -= 1.0
    if moho:
        f -= 2.0
    return round(max(f, 0), 2)

def calcular_factor_silo(qr):
    c = db()
    secciones = {"punta": 0.25, "medio": 0.5, "final": 0.25}
    total = 0
    peso = 0

    for sec, w in secciones.items():
        m = c.execute("""
        SELECT factor FROM muestreos
        WHERE numero_qr=? AND seccion=?
        ORDER BY fecha DESC LIMIT 1
        """, (qr, sec)).fetchone()
        if m:
            total += m["factor"] * w
            peso += w

    c.close()
    return round(total / peso, 2) if peso else None

# ================= VISTAS =================
@app.route("/")
@app.route("/panel")
def panel():
    c = db()
    silos = c.execute("SELECT * FROM silos").fetchall()

    data = []
    for s in silos:
        factor = calcular_factor_silo(s["numero_qr"])
        data.append({**dict(s), "factor": factor})

    c.close()
    return render_template("panel.html", registros=data)

@app.route("/form")
def form():
    return render_template("form.html")

# ================= API =================
@app.route("/api/save", methods=["POST"])
def save_silo():
    d = request.json
    c = db()
    c.execute("""
    INSERT OR IGNORE INTO silos VALUES (?,?,?,?,?,?,?)
    """, (
        d["numero_qr"], d["cereal"], d["estado"], d["metros"],
        d["lat"], d["lon"], d["fecha_confeccion"]
    ))
    c.commit()
    c.close()
    return jsonify(ok=True)

@app.route("/api/muestreo", methods=["POST"])
def nuevo_muestreo():
    d = request.json
    cereal = d["cereal"].lower()
    datos = d["datos"]

    grado = None
    factor = None

    if cereal == "maiz":
        grado = grado_maiz(datos)
        factor = factor_maiz(datos, d["olor"], d["moho"])
    elif cereal == "trigo":
        grado = None
        factor = 100.0 - (2 if d["moho"] else 0)
    elif cereal in ["soja", "girasol"]:
        grado = None
        factor = 100.0 - (2 if d["moho"] else 0)

    c = db()
    c.execute("""
    INSERT INTO muestreos (
        numero_qr, seccion, fecha, temperatura, humedad,
        datos, grado, factor, olor, moho, insectos, chamico
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["numero_qr"], d["seccion"], datetime.now().isoformat(),
        d["temperatura"], d["humedad"],
        json.dumps(datos), grado, factor,
        d["olor"], d["moho"], d["insectos"], d["chamico"]
    ))
    c.commit()
    c.close()

    return jsonify(grado=grado, factor=factor)

@app.route("/api/export")
def export():
    c = db()
    df = pd.read_sql_query("SELECT * FROM muestreos", c)
    c.close()

    out = io.BytesIO()
    df.to_excel(out, index=False)
    out.seek(0)
    return send_file(out, download_name="muestreos.xlsx", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
