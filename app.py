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

    def recomendacion_por_tas(tas):
        if tas is None:
            return "Normal"
        if tas <= 7:
            return "Extraer"
        if tas <= 20:
            return "Remuestrear"
        return "Normal"

    for s in silos:
        grado = None
        factor = None
        tas_min = None
        fecha_ultimo_muestreo = None

        # días desde confección
        dias_confeccion = None
        if s["fecha_confeccion"]:
            try:
                fc = datetime.strptime(s["fecha_confeccion"], "%Y-%m-%d %H:%M")
                dias_confeccion = (ahora - fc).days
            except:
                pass

        if s["ultimo_muestreo"]:
            mu = conn.execute(
                "SELECT fecha_muestreo FROM muestreos WHERE id=?",
                (s["ultimo_muestreo"],)
            ).fetchone()

            if mu:
                try:
                    fecha_ultimo_muestreo = datetime.strptime(
                        mu["fecha_muestreo"], "%Y-%m-%d %H:%M"
                    )
                except:
                    pass

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
# SILO (FIX ERROR 500)
# ======================================================

@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()
    ahora = ahora_argentina()

    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr.strip(),)
    ).fetchone()

    if silo is None:
        conn.close()
        abort(404)

    muestreos_db = conn.execute("""
        SELECT id, fecha_muestreo
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr.strip(),)).fetchall()

    muestreos = []
    for m in muestreos_db:
        dias = None
        try:
            fm = datetime.strptime(m["fecha_muestreo"], "%Y-%m-%d %H:%M")
            dias = (ahora - fm).days
        except:
            pass

        muestreos.append({
            "id": m["id"],
            "fecha_muestreo": m["fecha_muestreo"],
            "dias_desde": dias
        })

    conn.close()
    return render_template("silo.html", silo=silo, muestreos=muestreos)

# ======================================================
# FORM / MUESTREO / EXPORT (SIN CAMBIOS)
# ======================================================

@app.route("/form")
def form():
    return render_template("form.html")

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
    return send_file(mem, as_attachment=True,
                     download_name="silos.csv",
                     mimetype="text/csv")

if __name__ == "__main__":
    app.run(debug=True)
