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

    c.execute("""
    CREATE TABLE IF NOT EXISTS monitoreos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT,
        fecha TEXT,
        tipo TEXT,
        detalle TEXT,
        foto TEXT
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
        estado_silo=s["estado_silo"],
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
            "fecha_extraccion_estimada": fecha_extraccion_estimada,
            "ultimo_evento": s["ultimo_evento"]
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
        ahora_argentina().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# EXTRACCION
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
        d["estado_silo"],
        ahora_argentina().strftime("%Y-%m-%d %H:%M"),
        d["numero_qr"]
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# MONITOREO EN CAMPO
# ======================
@app.route("/api/monitoreo", methods=["POST"])
def guardar_monitoreo():
    numero_qr = request.form.get("numero_qr")
    tipo = request.form.get("tipo")
    detalle = request.form.get("detalle")

    foto = request.files.get("foto")
    nombre_foto = None

    if foto:
        os.makedirs("static/monitoreos", exist_ok=True)
        nombre_foto = f"static/monitoreos/{datetime.now().timestamp()}_{foto.filename}"
        foto.save(nombre_foto)

    conn = get_db()
    conn.execute("""
        INSERT INTO monitoreos (numero_qr, fecha, tipo, detalle, foto)
        VALUES (?,?,?,?,?)
    """, (
        numero_qr,
        ahora_argentina().strftime("%Y-%m-%d %H:%M"),
        tipo,
        detalle,
        nombre_foto
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
            return 0.0

    datos = {
        "temperatura": f(d.get("temperatura")),
        "humedad": f(d.get("humedad")),
        "ph": f(d.get("ph")) if d.get("ph") not in (None, "") else None,
        "danados": f(d.get("danados")),
        "quebrados": f(d.get("quebrados")),
        "materia_extrana": f(d.get("materia_extrana")),
        "olor": f(d.get("olor")),
        "moho": f(d.get("moho")),
        "insectos": int(d.get("insectos", False)),
        "chamico": f(d.get("chamico"))
    }

    cereal = d.get("cereal")
    grado = None
    factor = 1.0
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
    existe = conn.execute("""
        SELECT id FROM analisis
        WHERE id_muestreo=? AND seccion=?
    """, (d["id_muestreo"], d["seccion"])).fetchone()

    if existe:
        conn.execute("""
            UPDATE analisis SET
                temperatura=?, humedad=?, ph=?,
                danados=?, quebrados=?, materia_extrana=?,
                olor=?, moho=?, insectos=?, chamico=?,
                grado=?, factor=?, tas=?
            WHERE id=?
        """, (
            datos["temperatura"], datos["humedad"], datos["ph"],
            datos["danados"], datos["quebrados"], datos["materia_extrana"],
            datos["olor"], datos["moho"], datos["insectos"], datos["chamico"],
            grado, factor, tas, existe["id"]
        ))
    else:
        conn.execute("""
            INSERT INTO analisis (
                id_muestreo, seccion,
                temperatura, humedad, ph,
                danados, quebrados, materia_extrana,
                olor, moho, insectos, chamico,
                grado, factor, tas
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d["id_muestreo"], d["seccion"],
            datos["temperatura"], datos["humedad"], datos["ph"],
            datos["danados"], datos["quebrados"], datos["materia_extrana"],
            datos["olor"], datos["moho"], datos["insectos"], datos["chamico"],
            grado, factor, tas
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

    muestreos = conn.execute("""
        SELECT id, fecha_muestreo,
        CAST(julianday('now') - julianday(fecha_muestreo) AS INT) dias
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()

    monitoreos = conn.execute("""
        SELECT *
        FROM monitoreos
        WHERE numero_qr=?
        ORDER BY fecha DESC
    """, (qr,)).fetchall()

    conn.close()
    return render_template(
        "silo.html",
        silo=silo,
        muestreos=muestreos,
        monitoreos=monitoreos
    )

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
    return render_template("muestreo.html", muestreo=muestreo, analisis=analisis)

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
