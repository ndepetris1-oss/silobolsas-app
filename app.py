from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io

# ======================
# IMPORTAR CÁLCULOS
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
        estado TEXT,                 -- Seco / Humedo
        metros INTEGER,
        lat REAL,
        lon REAL,
        fecha_confeccion TEXT,
        fecha_extraccion TEXT,
        tipo_extraccion TEXT         -- parcial / completa
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

    conn.commit()
    conn.close()

init_db()

# ======================
# PANEL
# ======================
@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()

    silos = conn.execute("""
        SELECT * FROM silos
        ORDER BY fecha_confeccion DESC
    """).fetchall()

    registros = []

    for s in silos:
        ultimo_muestreo = conn.execute("""
            SELECT id, fecha_muestreo
            FROM muestreos
            WHERE numero_qr=?
            ORDER BY fecha_muestreo DESC
            LIMIT 1
        """, (s["numero_qr"],)).fetchone()

        grado = None
        factor = None
        tas_min = None
        fecha_extraccion_estimada = None

        if ultimo_muestreo:
            analisis = conn.execute("""
                SELECT *
                FROM analisis
                WHERE id_muestreo=?
            """, (ultimo_muestreo["id"],)).fetchall()

            if analisis:
                grados = [a["grado"] for a in analisis if a["grado"] is not None]
                factores = [a["factor"] for a in analisis if a["factor"] is not None]
                tas_vals = [a["tas"] for a in analisis if a["tas"] is not None]

                grado = max(grados) if grados else None
                factor = round(sum(factores) / len(factores), 4) if factores else None
                tas_min = min(tas_vals) if tas_vals else None

                if tas_min:
                    fecha_extraccion_estimada = (
                        datetime.strptime(
                            ultimo_muestreo["fecha_muestreo"],
                            "%Y-%m-%d %H:%M"
                        ) + timedelta(days=tas_min)
                    ).strftime("%Y-%m-%d")

        # Estado del silo (independiente del grano)
        estado_silo = "Activo"
        if s["fecha_extraccion"]:
            if s["tipo_extraccion"] == "parcial":
                estado_silo = "Extracción parcial"
            else:
                estado_silo = "Extraído"

        registros.append({
            **dict(s),
            "estado_grano": s["estado"],
            "estado_silo": estado_silo,
            "grado": grado,
            "factor": factor,
            "tas_min": tas_min,
            "fecha_extraccion_estimada": fecha_extraccion_estimada
        })

    conn.close()
    return render_template("panel.html", registros=registros)

# ======================
# FORM (REGISTRO / EXTRACCIÓN)
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

@app.route("/api/silo/<qr>")
def api_silo(qr):
    conn = get_db()
    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()
    conn.close()
    return jsonify(dict(silo) if silo else {})

@app.route("/api/save", methods=["POST"])
def save_silo():
    d = request.get_json()
    conn = get_db()

    existe = conn.execute(
        "SELECT numero_qr FROM silos WHERE numero_qr=?",
        (d["numero_qr"],)
    ).fetchone()

    if existe:
        conn.execute("""
            UPDATE silos SET
                cereal=?, estado=?, metros=?, lat=?, lon=?
            WHERE numero_qr=?
        """, (
            d["cereal"], d["estado"], d["metros"],
            d.get("lat"), d.get("lon"), d["numero_qr"]
        ))
    else:
        conn.execute("""
            INSERT INTO silos (
                numero_qr, cereal, estado, metros,
                lat, lon, fecha_confeccion
            ) VALUES (?,?,?,?,?,?,?)
        """, (
            d["numero_qr"], d["cereal"], d["estado"], d["metros"],
            d.get("lat"), d.get("lon"),
            ahora().strftime("%Y-%m-%d %H:%M")
        ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

@app.route("/api/extraccion", methods=["POST"])
def registrar_extraccion():
    d = request.get_json()
    conn = get_db()

    conn.execute("""
        UPDATE silos SET
            fecha_extraccion=?,
            tipo_extraccion=?
        WHERE numero_qr=?
    """, (
        ahora().strftime("%Y-%m-%d %H:%M"),
        d["tipo_extraccion"],
        d["numero_qr"]
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# MUESTREOS
# ======================
@app.route("/api/nuevo_muestreo", methods=["POST"])
def nuevo_muestreo():
    qr = request.json["qr"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO muestreos (numero_qr, fecha_muestreo)
        VALUES (?,?)
    """, (qr, ahora().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return jsonify(id_muestreo=mid)

@app.route("/api/analisis_seccion", methods=["POST"])
def guardar_analisis():
    d = request.get_json()
    cereal = d["cereal"]

    # Convertidor seguro
    def f(x):
        try:
            return float(x)
        except:
            return 0.0

    datos = {
        "temperatura": f(d.get("temperatura")),
        "humedad": f(d.get("humedad")),
        "ph": f(d.get("ph")),
        "danados": f(d.get("danados")),
        "quebrados": f(d.get("quebrados")),
        "materia_extrana": f(d.get("materia_extrana")),
        "olor": f(d.get("olor")),
        "moho": f(d.get("moho")),
        "chamico": f(d.get("chamico"))
    }

    grado = None
    factor = None
    tas = None

    if cereal == "Maíz":
        grado = grado_maiz(datos)
        factor = factor_maiz(datos)
        tas = tas_maiz(datos)
    elif cereal == "Trigo":
        grado = grado_trigo(datos)
        factor = factor_trigo(datos)
        tas = tas_trigo(datos)
    elif cereal == "Soja":
        factor = factor_soja(datos)
    elif cereal == "Girasol":
        factor = factor_girasol(datos)

    conn = get_db()

    conn.execute("""
        INSERT INTO analisis (
            id_muestreo, seccion, temperatura, humedad, ph,
            danados, quebrados, materia_extrana,
            olor, moho, insectos, chamico,
            grado, factor, tas
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["id_muestreo"], d["seccion"],
        datos["temperatura"], datos["humedad"], datos["ph"],
        datos["danados"], datos["quebrados"], datos["materia_extrana"],
        datos["olor"], datos["moho"],
        int(d.get("insectos", False)), datos["chamico"],
        grado, factor, tas
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# VISTAS
# ======================
@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()
    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    muestreos = conn.execute("""
        SELECT *
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()

    conn.close()
    return render_template("silo.html", silo=silo, muestreos=muestreos)

@app.route("/muestreo/<int:id>")
def ver_muestreo(id):
    conn = get_db()
    muestreo = conn.execute("""
        SELECT m.*, s.cereal, s.numero_qr
        FROM muestreos m
        JOIN silos s ON s.numero_qr=m.numero_qr
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

# ======================
# EXPORT CSV
# ======================
@app.route("/api/export")
def exportar():
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM silos
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

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(debug=True)
