from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, io

# ======================
# IMPORTAR CALCULOS
# ======================
from calculos import (
    grado_maiz, factor_maiz,
    grado_trigo, factor_trigo,
    factor_soja, factor_girasol,
    tas_maiz, tas_trigo
)

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

    resultado = []

    for s in silos:
        grado = None
        factor = None

        if s["ultimo_muestreo"]:
            datos = conn.execute("""
                SELECT grado, factor
                FROM analisis
                WHERE id_muestreo=?
            """, (s["ultimo_muestreo"],)).fetchall()

            if datos:
                grados = [d["grado"] for d in datos if d["grado"] is not None]
                grado = max(grados) if grados else None
                factor = round(
                    sum(d["factor"] for d in datos if d["factor"] is not None) / len(datos),
                    4
                )

        resultado.append({**dict(s), "grado": grado, "factor": factor})

    conn.close()
    return render_template("panel.html", registros=resultado)

# ======================
# FORM
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

# ======================
# REGISTRAR / EDITAR SILO
# ======================
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
                cereal=?,
                estado=?,
                metros=?,
                lat=?,
                lon=?
            WHERE numero_qr=?
        """, (
            d["cereal"],
            d["estado"],
            d["metros"],
            d.get("lat"),
            d.get("lon"),
            d["numero_qr"]
        ))
    else:
        conn.execute("""
            INSERT INTO silos (
                numero_qr, cereal, estado, metros, lat, lon, fecha_confeccion
            ) VALUES (?,?,?,?,?,?,?)
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
# GUARDAR ANALISIS (CLAVE)
# ======================
@app.route("/api/analisis_seccion", methods=["POST"])
def guardar_analisis_seccion():
    d = request.get_json()

    def f(x):
        try:
            return float(x)
        except:
            return 0.0

    datos = {
        "temperatura": f(d.get("temperatura")),
        "humedad": f(d.get("humedad")),
        "ph": f(d.get("ph")) if d.get("ph") not in ("", None) else None,
        "danados": f(d.get("danados")),
        "quebrados": f(d.get("quebrados")),
        "materia_extrana": f(d.get("materia_extrana")),
        "olor": f(d.get("olor")),
        "moho": f(d.get("moho")),
        "chamico": f(d.get("chamico")),
    }

    cereal = d["cereal"]

    if cereal == "Maíz":
        grado = grado_maiz(datos)
        factor = factor_maiz(datos)
        tas = tas_maiz(datos)

    elif cereal == "Trigo":
        grado = grado_trigo(datos)
        factor = factor_trigo(datos)
        tas = tas_trigo(datos)

    elif cereal == "Soja":
        grado = None
        factor = factor_soja(datos)
        tas = None

    elif cereal == "Girasol":
        grado = None
        factor = factor_girasol(datos)
        tas = None

    conn = get_db()
    existe = conn.execute("""
        SELECT id FROM analisis
        WHERE id_muestreo=? AND seccion=?
    """, (d["id_muestreo"], d["seccion"])).fetchone()

    valores = (
        datos["temperatura"],
        datos["humedad"],
        datos["ph"],
        datos["danados"],
        datos["quebrados"],
        datos["materia_extrana"],
        datos["olor"],
        datos["moho"],
        int(d.get("insectos", False)),
        datos["chamico"],
        grado,
        factor,
        tas
    )

    if existe:
        conn.execute("""
            UPDATE analisis SET
                temperatura=?, humedad=?, ph=?,
                danados=?, quebrados=?, materia_extrana=?,
                olor=?, moho=?, insectos=?, chamico=?,
                grado=?, factor=?, tas=?
            WHERE id=?
        """, (*valores, existe["id"]))
    else:
        conn.execute("""
            INSERT INTO analisis (
                id_muestreo, seccion, temperatura, humedad, ph,
                danados, quebrados, materia_extrana,
                olor, moho, insectos, chamico,
                grado, factor, tas
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (d["id_muestreo"], d["seccion"], *valores))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# VISTAS
# ======================
@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()
    silo = conn.execute("SELECT * FROM silos WHERE numero_qr=?", (qr,)).fetchone()
    muestreos = conn.execute("""
        SELECT id, fecha_muestreo
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()
    conn.close()
    return render_template("silo.html", silo=dict(silo), muestreos=muestreos)

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
    return render_template("muestreo.html", muestreo=muestreo, analisis=analisis)

# ======================
# EXPORTAR CSV
# ======================
@app.route("/api/export")
def exportar():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.numero_qr, s.cereal, s.estado,
               m.fecha_muestreo, a.seccion, a.grado, a.factor
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

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(debug=True)
