from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
import io
import csv

app = Flask(__name__)
DB_NAME = "silos.db"


# =========================
# DB
# =========================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # SILOS
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

    # ANALISIS
    c.execute("""
        CREATE TABLE IF NOT EXISTS analisis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT,
            seccion TEXT,
            temperatura REAL,
            humedad REAL,
            ph REAL,
            danados REAL,
            quebrados REAL,
            materia_extrana REAL,
            olor REAL,
            moho REAL,
            insectos INTEGER,
            chamico INTEGER,
            grado INTEGER,
            factor REAL,
            fecha TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# VISTAS
# =========================
@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()
    silos = conn.execute("""
        SELECT s.*, 
               MAX(a.factor) as factor,
               MAX(a.grado) as grado
        FROM silos s
        LEFT JOIN analisis a ON a.numero_qr = s.numero_qr
        GROUP BY s.numero_qr
        ORDER BY fecha_confeccion DESC
    """).fetchall()
    conn.close()
    return render_template("panel.html", registros=silos)


@app.route("/form")
def form():
    return render_template("form.html")


# =========================
# API – REGISTRO SILO
# =========================
@app.route("/api/save", methods=["POST"])
def save_silo():
    data = request.get_json()

    conn = get_db()
    conn.execute("""
        INSERT INTO silos (
            numero_qr, cereal, estado, metros, lat, lon, fecha_confeccion
        ) VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(numero_qr) DO UPDATE SET
            cereal=excluded.cereal,
            estado=excluded.estado,
            metros=excluded.metros,
            lat=excluded.lat,
            lon=excluded.lon
    """, (
        data["numero_qr"],
        data["cereal"],
        data["estado"],
        data["metros"],
        data.get("lat"),
        data.get("lon"),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    return jsonify(ok=True)


# =========================
# CALCULO MAÍZ
# =========================
def calcular_maiz(d):
    grado = 1

    if d["danados"] > 5 or d["quebrados"] > 3 or d["materia_extrana"] > 1:
        grado = 2
    if d["danados"] > 8 or d["quebrados"] > 5 or d["materia_extrana"] > 2:
        grado = 3

    factor = 1.0

    # castigos SOLO si supera grado 3
    if d["danados"] > 8:
        factor -= (d["danados"] - 8) * 0.01
    if d["quebrados"] > 5:
        factor -= (d["quebrados"] - 5) * 0.01
    if d["materia_extrana"] > 2:
        factor -= (d["materia_extrana"] - 2) * 0.01

    factor = max(factor, 0.7)

    return grado, round(factor, 3)


# =========================
# API – GUARDAR ANALISIS
# =========================
@app.route("/api/analisis", methods=["POST"])
def guardar_analisis():
    d = request.get_json()

    cereal = d["cereal"]

    grado = None
    factor = 1.0

    if cereal == "Maíz":
        grado, factor = calcular_maiz(d)

    conn = get_db()
    conn.execute("""
        INSERT INTO analisis (
            numero_qr, seccion, temperatura, humedad, ph,
            danados, quebrados, materia_extrana,
            olor, moho, insectos, chamico,
            grado, factor, fecha
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["qr"],
        d["seccion"],
        d.get("temperatura"),
        d.get("humedad"),
        d.get("ph"),
        d.get("danados"),
        d.get("quebrados"),
        d.get("materia_extrana"),
        d.get("olor"),
        d.get("moho"),
        int(d.get("insectos", False)),
        int(d.get("chamico", False)),
        grado,
        factor,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return jsonify(ok=True, grado=grado, factor=factor)


# =========================
# EXPORTAR EXCEL
# =========================
@app.route("/api/export")
def export_excel():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.numero_qr, s.cereal, s.estado, s.fecha_confeccion,
               a.seccion, a.grado, a.factor, a.fecha
        FROM silos s
        LEFT JOIN analisis a ON a.numero_qr = s.numero_qr
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(rows[0].keys() if rows else [])

    for r in rows:
        writer.writerow(list(r))

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(mem, mimetype="text/csv",
                     as_attachment=True,
                     download_name="silos.csv")


# =========================
# BORRAR SILO
# =========================
@app.route("/api/delete", methods=["POST"])
def delete_silo():
    qr = request.json["numero_qr"]
    conn = get_db()
    conn.execute("DELETE FROM analisis WHERE numero_qr = ?", (qr,))
    conn.execute("DELETE FROM silos WHERE numero_qr = ?", (qr,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
