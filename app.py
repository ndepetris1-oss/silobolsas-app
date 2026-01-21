from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io

# ======================
# APP
# ======================
app = Flask(__name__)
DB_NAME = "silobolsas.db"

print(">>> APP.PY CARGADO CORRECTAMENTE <<<")

# ======================
# UTILIDADES
# ======================
def ahora_argentina():
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
        estado_grano TEXT,           -- Seco / Humedo
        estado_silo TEXT,            -- Activo / Extracción parcial / Extraído
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
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()
    conn.close()

    if not s:
        return jsonify(existe=False)

    return jsonify(
        existe=True,
        estado_silo=s["estado_silo"]
    )

# ======================
# PANEL
# ======================
@app.route("/")
@app.route("/panel")
def panel():
    conn = get_db()

    rows = conn.execute("""
        SELECT s.*,
        (
            SELECT m.id FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
            ORDER BY m.fecha_muestreo DESC
            LIMIT 1
        ) ultimo_muestreo
        FROM silos s
        ORDER BY fecha_confeccion DESC
    """).fetchall()

    registros = []

    for s in rows:
        grado = None
        factor = None
        tas_min = None
        fecha_extraccion_estimada = None

        if s["ultimo_muestreo"]:
            analisis = conn.execute("""
                SELECT grado, factor, tas
                FROM analisis
                WHERE id_muestreo=?
            """, (s["ultimo_muestreo"],)).fetchall()

            if analisis:
                grados = [a["grado"] for a in analisis if a["grado"] is not None]
                factores = [a["factor"] for a in analisis if a["factor"] is not None]
                tass = [a["tas"] for a in analisis if a["tas"] is not None]

                grado = max(grados) if grados else None
                factor = round(sum(factores) / len(factores), 4) if factores else None
                tas_min = min(tass) if tass else None

                if tas_min:
                    fm = datetime.strptime(
                        conn.execute(
                            "SELECT fecha_muestreo FROM muestreos WHERE id=?",
                            (s["ultimo_muestreo"],)
                        ).fetchone()["fecha_muestreo"],
                        "%Y-%m-%d %H:%M"
                    )
                    fecha_extraccion_estimada = (
                        fm + timedelta(days=tas_min)
                    ).strftime("%Y-%m-%d")

        registros.append({
            **dict(s),
            "grado": grado,
            "factor": factor,
            "tas_min": tas_min,
            "fecha_extraccion_estimada": fecha_extraccion_estimada
        })

    conn.close()
    return render_template("panel.html", registros=registros)

# ======================
# FORM
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

# ======================
# REGISTRAR SILO (1RA VEZ)
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
        ahora_argentina().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# REGISTRAR EXTRACCIÓN
# ======================
@app.route("/api/extraccion", methods=["POST"])
def registrar_extraccion():
    d = request.get_json()
    conn = get_db()

    conn.execute("""
        UPDATE silos SET
            estado_silo=?,
            fecha_extraccion=?
        WHERE numero_qr=?
    """, (
        d["estado_silo"],  # Extracción parcial / Extraído
        ahora_argentina().strftime("%Y-%m-%d %H:%M"),
        d["numero_qr"]
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# NUEVO MUESTREO
# ======================
@app.route("/api/nuevo_muestreo", methods=["POST"])
def nuevo_muestreo():
    qr = request.json["qr"]
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

# ======================
# GUARDAR ANALISIS
# ======================
@app.route("/api/analisis_seccion", methods=["POST"])
def guardar_analisis_seccion():
    d = request.get_json()

    def f(x):
        try:
            return float(x)
        except:
            return None

    conn = get_db()

    existe = conn.execute("""
        SELECT id FROM analisis
        WHERE id_muestreo=? AND seccion=?
    """, (d["id_muestreo"], d["seccion"])).fetchone()

    datos = (
        d["id_muestreo"],
        d["seccion"],
        f(d.get("temperatura")),
        f(d.get("humedad")),
        f(d.get("ph")),
        f(d.get("danados")),
        f(d.get("quebrados")),
        f(d.get("materia_extrana")),
        f(d.get("olor")),
        f(d.get("moho")),
        int(d.get("insectos", 0)),
        f(d.get("chamico")),
        d.get("grado"),
        d.get("factor"),
        d.get("tas")
    )

    if existe:
        conn.execute("""
            UPDATE analisis SET
                temperatura=?, humedad=?, ph=?,
                danados=?, quebrados=?, materia_extrana=?,
                olor=?, moho=?, insectos=?, chamico=?,
                grado=?, factor=?, tas=?
            WHERE id=?
        """, datos[2:] + (existe["id"],))
    else:
        conn.execute("""
            INSERT INTO analisis (
                id_muestreo, seccion, temperatura, humedad, ph,
                danados, quebrados, materia_extrana,
                olor, moho, insectos, chamico, grado, factor, tas
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, datos)

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

    muestreos = conn.execute("""
        SELECT id, fecha_muestreo,
        CAST(
            julianday('now') - julianday(fecha_muestreo)
            AS INT
        ) dias
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()

    conn.close()
    return render_template("silo.html", silo=silo, muestreos=muestreos)

# ======================
# MUESTREO
# ======================
@app.route("/muestreo/<int:id>")
def ver_muestreo(id):
    conn = get_db()
    muestreo = conn.execute("""
        SELECT m.*, s.numero_qr, s.cereal
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
    return render_template(
        "muestreo.html",
        muestreo=muestreo,
        analisis=analisis
    )

# ======================
# EXPORT CSV
# ======================
@app.route("/api/export")
def exportar():
    conn = get_db()
    rows = conn.execute("""
        SELECT *
        FROM silos
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
