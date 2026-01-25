from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io

# ======================
# IMPORTAR CALCULOS
# ======================
from calculos import (
    grado_maiz, factor_maiz, tas_maiz,
    grado_trigo, factor_trigo, tas_trigo,
    factor_soja, factor_girasol
)

# ======================
# APP
# ======================
app = Flask(__name__)
DB_NAME = "silobolsas.db"

# ======================
# UTILIDADES
# ======================
def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ======================
# DB INIT
# ======================
def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS silos (
        numero_qr TEXT PRIMARY KEY,
        cereal TEXT,
        estado_grano TEXT,
        estado_silo TEXT,
        metros INTEGER,
        lat REAL,
        lon REAL,
        fecha_confeccion TEXT,
        fecha_extraccion TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS muestreos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT,
        fecha_muestreo TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS analisis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_muestreo INTEGER,
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
        chamico REAL,
        grado INTEGER,
        factor REAL,
        tas INTEGER
    )
    """)

    # 👇 TABLA FINAL DE MONITOREOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS monitoreos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT,
        fecha_evento TEXT,
        tipo TEXT,
        detalle TEXT,
        foto_evento TEXT,
        resuelto INTEGER DEFAULT 0,
        fecha_resolucion TEXT,
        foto_resolucion TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ======================
# API — CONSULTA SILO (FORM)
# ======================
@app.route("/api/silo/<qr>")
def api_silo(qr):
    conn = get_db()
    s = conn.execute(
        "SELECT cereal, fecha_confeccion FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()
    conn.close()

    if not s:
        return jsonify(existe=False)

    return jsonify(
        existe=True,
        cereal=s["cereal"],
        fecha_confeccion=s["fecha_confeccion"]
    )

# ======================
# PANEL
# ======================
@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()

    silos = conn.execute("""
        SELECT s.*,
        (
            SELECT m.id
            FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
            ORDER BY m.fecha_muestreo DESC
            LIMIT 1
        ) ultimo_muestreo,
        (
            SELECT mo.tipo
            FROM monitoreos mo
            WHERE mo.numero_qr = s.numero_qr
            ORDER BY mo.fecha DESC
            LIMIT 1
        ) ultimo_evento
        FROM silos s
        ORDER BY fecha_confeccion DESC
    """).fetchall()

    registros = []

    for s in silos:
        registros.append(dict(s))

    conn.close()
    return render_template("panel.html", registros=registros)

# ======================
# FORM
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

# ======================
# REGISTRAR SILO
# ======================
@app.route("/api/registrar_silo", methods=["POST"])
def registrar_silo():
    d = request.get_json()
    conn = get_db()

    conn.execute("""
        INSERT INTO silos (
            numero_qr, cereal, estado_grano, estado_silo,
            metros, lat, lon, fecha_confeccion
        ) VALUES (?,?,?,?,?,?,?,?)
    """, (
        d["numero_qr"],
        d["cereal"],
        d["estado_grano"],
        "Activo",
        d["metros"],
        d.get("lat"),
        d.get("lon"),
        ahora().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# MONITOREO — NUEVO EVENTO
# ======================
@app.route("/api/monitoreo", methods=["POST"])
def nuevo_monitoreo():
    qr = request.form.get("numero_qr")
    tipo = request.form.get("tipo")
    detalle = request.form.get("detalle")

    foto_evento = request.files.get("foto")
    path_evento = None

    if foto_evento:
        os.makedirs("static/monitoreos", exist_ok=True)
        path_evento = f"static/monitoreos/{datetime.now().timestamp()}_{foto_evento.filename}"
        foto_evento.save(path_evento)

    conn = get_db()
    conn.execute("""
        INSERT INTO monitoreos (
            numero_qr, fecha_evento, tipo, detalle, foto_evento
        ) VALUES (?,?,?,?,?)
    """, (
        qr,
        ahora().strftime("%Y-%m-%d %H:%M"),
        tipo,
        detalle,
        path_evento
    ))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# MONITOREO — RESOLVER EVENTO
# ======================
@app.route("/api/monitoreo_resolver", methods=["POST"])
def resolver_monitoreo():
    mid = request.form.get("id")
    foto_sol = request.files.get("foto_solucion")
    path_sol = None

    if foto_sol:
        os.makedirs("static/monitoreos", exist_ok=True)
        path_sol = f"static/monitoreos/{datetime.now().timestamp()}_{foto_sol.filename}"
        foto_sol.save(path_sol)

    conn = get_db()
    conn.execute("""
        UPDATE monitoreos SET
            resuelto=1,
            fecha_resolucion=?,
            foto_resolucion=?
        WHERE id=?
    """, (
        ahora().strftime("%Y-%m-%d %H:%M"),
        path_sol,
        mid
    ))
    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# SILO
# ======================
@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()

    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    monitoreos = conn.execute("""
        SELECT * FROM monitoreos
        WHERE numero_qr=?
        ORDER BY fecha_evento DESC
    """, (qr,)).fetchall()

    conn.close()
    return render_template("silo.html", silo=silo, monitoreos=monitoreos)

# ======================
# EXPORT CSV
# ======================
@app.route("/api/export")
def exportar():
    conn = get_db()
    rows = conn.execute("SELECT * FROM silos").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow(list(r))

    mem = io.BytesIO(output.getvalue().encode())
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name="silos.csv",
        mimetype="text/csv"
    )

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(debug=True)
