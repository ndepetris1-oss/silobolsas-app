from flask import Flask, render_template, request, jsonify, send_file, abort
import sqlite3, csv, io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from calculos import (
    grado_maiz, factor_maiz, tas_maiz,
    grado_trigo, factor_trigo, tas_trigo,
    factor_soja, factor_girasol
)

app = Flask(__name__)
DB_NAME = "silos.db"

# ======================================================
# UTILIDADES
# ======================================================

def ahora_argentina():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ======================================================
# DB INIT
# ======================================================

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
        fecha_confeccion TEXT
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
        chamico INTEGER,
        grado INTEGER,
        factor REAL,
        tas INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ======================================================
# PANEL
# ======================================================

@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()
    ahora = ahora_argentina()

    silos = conn.execute("""
        SELECT s.*,
        (
            SELECT m.id
            FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
            ORDER BY m.fecha_muestreo DESC
            LIMIT 1
        ) ultimo_muestreo
        FROM silos s
        ORDER BY fecha_confeccion DESC
    """).fetchall()

    pesos = {"punta": 0.2, "medio": 0.6, "final": 0.2}
    resultado = []

    def recomendacion_por_tas(tas_min):
        if tas_min is None:
            return "normal"
        if tas_min <= 7:
            return "extraer"
        if tas_min <= 20:
            return "remuestrear"
        return "normal"

    for s in silos:
        grado = None
        factor = None
        tas_min = None

        # días desde confección
        dias_confeccion = None
        if s["fecha_confeccion"]:
            try:
                fc = datetime.strptime(s["fecha_confeccion"], "%Y-%m-%d %H:%M")
                dias_confeccion = (ahora - fc).days
            except:
                dias_confeccion = None

        fecha_ultimo_muestreo = None

        if s["ultimo_muestreo"]:
            mu = conn.execute("""
                SELECT fecha_muestreo
                FROM muestreos
                WHERE id=?
            """, (s["ultimo_muestreo"],)).fetchone()

            if mu and mu["fecha_muestreo"]:
                try:
                    fecha_ultimo_muestreo = datetime.strptime(
                        mu["fecha_muestreo"], "%Y-%m-%d %H:%M"
                    )
                except:
                    fecha_ultimo_muestreo = None

            datos = conn.execute("""
                SELECT seccion, grado, factor, tas
                FROM analisis
                WHERE id_muestreo=?
            """, (s["ultimo_muestreo"],)).fetchall()

            if datos:
                total = 0
                grados = []
                tas_vals = []

                for d in datos:
                    peso = pesos.get(d["seccion"], 0)
                    if d["factor"] is not None:
                        total += d["factor"] * peso
                    if d["grado"] is not None:
                        grados.append(d["grado"])
                    if d["tas"] is not None:
                        tas_vals.append(d["tas"])

                if total > 0:
                    factor = round(total * 100, 1)
                if grados:
                    grado = max(grados)
                if tas_vals:
                    tas_min = min(tas_vals)

        # fecha estimada de extracción
        fecha_extraccion_estimada = None
        if tas_min is not None and fecha_ultimo_muestreo:
            fecha_extraccion_estimada = (
                fecha_ultimo_muestreo + timedelta(days=tas_min)
            ).strftime("%Y-%m-%d")

        resultado.append({
            **dict(s),
            "grado": grado,
            "factor": factor,
            "tas_min": tas_min,
            "recomendacion": recomendacion_por_tas(tas_min),
            "dias_confeccion": dias_confeccion,
            "fecha_extraccion_estimada": fecha_extraccion_estimada
        })

    conn.close()
    return render_template("panel.html", registros=resultado)

# ======================================================
# FORM
# ======================================================

@app.route("/form")
def form():
    return render_template("form.html")

# ======================================================
# REGISTRAR SILO
# ======================================================

@app.route("/api/save", methods=["POST"])
def save_silo():
    d = request.get_json()
    conn = get_db()

    conn.execute("""
        INSERT INTO silos VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(numero_qr) DO UPDATE SET
            cereal=excluded.cereal,
            estado=excluded.estado,
            metros=excluded.metros,
            lat=excluded.lat,
            lon=excluded.lon
    """, (
        d["numero_qr"],
        d["cereal"],
        d["estado"],
        d["metros"],
        d.get("lat"),
        d.get("lon"),
        ahora_argentina().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================================================
# NUEVO MUESTREO
# ======================================================

@app.route("/api/nuevo_muestreo", methods=["POST"])
def nuevo_muestreo():
    qr = request.json["qr"].strip()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO muestreos (numero_qr, fecha_muestreo)
        VALUES (?,?)
    """, (qr, ahora_argentina().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return jsonify(id_muestreo=mid)

# ======================================================
# SILO
# ======================================================

@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()
    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?", (qr.strip(),)
    ).fetchone()

    if silo is None:
        conn.close()
        abort(404)

    muestreos = conn.execute("""
        SELECT id, fecha_muestreo
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr.strip(),)).fetchall()

    conn.close()
    return render_template("silo.html", silo=silo, muestreos=muestreos)

# ======================================================
# MUESTREO
# ======================================================

@app.route("/muestreo/<int:id>")
def ver_muestreo(id):
    conn = get_db()

    muestreo = conn.execute("""
        SELECT m.*, s.numero_qr, s.cereal
        FROM muestreos m
        JOIN silos s ON s.numero_qr = m.numero_qr
        WHERE m.id=?
    """, (id,)).fetchone()

    analisis = conn.execute("""
        SELECT *
        FROM analisis
        WHERE id_muestreo=?
        ORDER BY seccion
    """, (id,)).fetchall()

    conn.close()
    return render_template("muestreo.html", muestreo=muestreo, analisis=analisis)

# ======================================================
# EXPORTAR CSV
# ======================================================

@app.route("/api/export")
def exportar():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.numero_qr, s.cereal, s.estado,
               m.fecha_muestreo, a.seccion,
               a.grado, a.factor, a.tas
        FROM silos s
        LEFT JOIN muestreos m ON s.numero_qr=m.numero_qr
        LEFT JOIN analisis a ON a.id_muestreo=m.id
    """).fetchall()
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

if __name__ == "__main__":
    app.run(debug=True)
