from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, json, io
from datetime import datetime
import pandas as pd

app = Flask(__name__)
DB = "silos.db"

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS silos (
        numero_qr TEXT PRIMARY KEY,
        cereal TEXT,
        estado TEXT,
        metros INTEGER,
        lat REAL,
        lon REAL,
        fecha_confeccion TEXT,
        grado INTEGER,
        factor REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS analisis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT,
        cereal TEXT,
        datos TEXT,
        grado INTEGER,
        factor REAL,
        fecha TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= VISTAS =================
@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()
    registros = conn.execute(
        "SELECT * FROM silos ORDER BY fecha_confeccion DESC"
    ).fetchall()
    conn.close()
    return render_template("panel.html", registros=registros)

@app.route("/form")
def form():
    return render_template("form.html")

# ================= REGISTRO SILO =================
@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()
    conn = get_db()

    existe = conn.execute(
        "SELECT 1 FROM silos WHERE numero_qr = ?",
        (data["numero_qr"],)
    ).fetchone()

    if not existe:
        conn.execute("""
        INSERT INTO silos (
            numero_qr, cereal, estado, metros,
            lat, lon, fecha_confeccion
        ) VALUES (?,?,?,?,?,?,?)
        """, (
            data["numero_qr"],
            data["cereal"],
            data["estado"],
            data["metros"],
            data["lat"],
            data["lon"],
            data["fecha_confeccion"]
        ))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ================= GRADOS =================
def grado_maiz(datos):
    g = []

    ph = float(datos["ph"])
    dan = float(datos["danados"])
    q = float(datos["quebrados"])
    me = float(datos["me"])

    # PH
    g.append(1 if ph >= 75 else 2 if ph >= 72 else 3)
    # Dañados
    g.append(1 if dan <= 3 else 2 if dan <= 8 else 3)
    # Quebrados
    g.append(1 if q <= 2 else 2 if q <= 5 else 3)
    # Materia extraña
    g.append(1 if me <= 1 else 2 if me <= 2 else 3)

    return max(g)

def grado_trigo(datos):
    g = []

    ph = float(datos["ph"])
    dan = float(datos["danados"])

    g.append(1 if ph >= 79 else 2 if ph >= 76 else 3)
    g.append(1 if dan <= 0.5 else 2 if dan <= 1.5 else 3)

    return max(g)

# ================= FACTOR MAÍZ (NORMA XII REAL) =================
def factor_maiz(datos):
    """
    Factor comercial real:
    - Arranca en 100 %
    - SOLO castiga fuera del grado 3
    """
    factor = 100.0

    dan = float(datos["danados"])
    if dan > 8:
        factor -= (dan - 8) * 1.0   # 1% por cada 1% excedente

    q = float(datos["quebrados"])
    if q > 5:
        factor -= (q - 5) * 0.25    # 0,25% por cada 1% excedente

    me = float(datos["me"])
    if me > 2:
        factor -= (me - 2) * 1.0

    ph = float(datos["ph"])
    if ph < 69:
        factor -= (69 - ph) * 1.0   # 1% por kg/hl faltante

    return round(max(factor, 0), 2)

# ================= ANALISIS =================
@app.route("/api/analisis", methods=["POST"])
def analisis():
    data = request.get_json()
    cereal = data["cereal"].lower()
    datos = data["datos"]

    grado = None
    factor = None

    if cereal == "maíz" or cereal == "maiz":
        grado = grado_maiz(datos)
        factor = factor_maiz(datos)

    elif cereal == "trigo":
        grado = grado_trigo(datos)
        factor = 100.0

    elif cereal in ["soja", "girasol"]:
        grado = None
        factor = None  # se implementa después

    conn = get_db()

    conn.execute("""
    INSERT INTO analisis (
        numero_qr, cereal, datos, grado, factor, fecha
    ) VALUES (?,?,?,?,?,?)
    """, (
        data["numero_qr"],
        cereal,
        json.dumps(datos),
        grado,
        factor,
        datetime.now().isoformat()
    ))

    conn.execute("""
    UPDATE silos
    SET grado = ?, factor = ?
    WHERE numero_qr = ?
    """, (
        grado,
        factor,
        data["numero_qr"]
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "grado": grado,
        "factor": factor
    })

# ================= EXPORT =================
@app.route("/api/export")
def export():
    conn = get_db()
    rows = conn.execute("SELECT * FROM silos").fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=rows[0].keys())
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="silos.xlsx",
        as_attachment=True
    )

# ================= MAIN =================
if __name__ == "__main__":
    app.run(debug=True)
