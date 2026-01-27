from flask import Flask, render_template, request, jsonify, send_file, redirect
import sqlite3, os
from datetime import datetime, timedelta
import csv, io

# ======================
# IMPORTAR CALCULOS
# ======================
from calculos import calcular_comercial

# ======================
# APP
# ======================
app = Flask(__name__)

# ======================
# DB PATH (FIX RENDER)
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "silobolsas.db")

# ======================
# UTILIDADES
# ======================
def ahora():
    return datetime.now()

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
        ) ultimo_muestreo
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
grados = []
factores = []
tass = []

for a in analisis:
    if a["grado"] is not None:
        grados.append(a["grado"])

    if a["factor"] is not None:
        try:
            f = float(a["factor"])
            if f > 0:
                factores.append(f)
        except:
            pass

    if a["tas"] is not None:
        try:
            t = int(a["tas"])
            if t > 0:
                tass.append(t)
        except:
            pass

grado = max(grados) if grados else None
factor = round(sum(factores) / len(factores), 4) if factores else None
tas_min = min(tass) if tass else None
               

                # fecha estimada de extracción (robusto)
fecha_extraccion_estimada = None

if tas_min is not None:
    row = conn.execute(
        "SELECT fecha_muestreo FROM muestreos WHERE id=?",
        (s["ultimo_muestreo"],)
    ).fetchone()

    if row and row["fecha_muestreo"]:
        try:
            fm = datetime.strptime(row["fecha_muestreo"], "%Y-%m-%d %H:%M")
            dias = int(float(tas_min))
            fecha_extraccion_estimada = (
                fm + timedelta(days=dias)
            ).strftime("%Y-%m-%d")
        except Exception as e:
            print("Error fecha extracción:", e)
            fecha_extraccion_estimada = None
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
# REGISTRAR SILO (FIX JSON)
# ======================
@app.route("/api/registrar_silo", methods=["POST"])
def registrar_silo():
    d = request.get_json(force=True, silent=True)
    print("DATA FORM:", d)

    if not d or not d.get("numero_qr"):
        return jsonify(ok=False, error="Datos inválidos"), 400

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
        int(d["metros"]),
        d.get("lat"),
        d.get("lon"),
        ahora().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# API — NUEVO MUESTREO
# ======================
@app.route("/api/nuevo_muestreo", methods=["POST"])
def api_nuevo_muestreo():
    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("qr")

    if not qr:
        return jsonify(error="QR faltante"), 400

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

# ======================
# ANALISIS — SECCION
# ======================
@app.route("/api/analisis_seccion", methods=["POST"])
def guardar_analisis_seccion():
    d = request.get_json(force=True, silent=True) or {}

    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    for k in ["temperatura","humedad","ph","danados","quebrados","materia_extrana","olor","moho","chamico"]:
        d[k] = to_float(d.get(k))

    d["insectos"] = 1 if d.get("insectos") else 0

    conn = get_db()
    cur = conn.cursor()

    existente = cur.execute("""
        SELECT id FROM analisis
        WHERE id_muestreo=? AND seccion=?
    """, (d["id_muestreo"], d["seccion"])).fetchone()

    res = calcular_comercial(d["cereal"], d)

    valores = (
        d["id_muestreo"],
        d["seccion"],
        d["temperatura"],
        d["humedad"],
        d["ph"],
        d["danados"],
        d["quebrados"],
        d["materia_extrana"],
        d["olor"],
        d["moho"],
        d["insectos"],
        d["chamico"],
        res["grado"],
        res["factor"],
        res["tas"]
    )

    if existente:
        cur.execute("""
            UPDATE analisis SET
                temperatura=?, humedad=?, ph=?,
                danados=?, quebrados=?, materia_extrana=?,
                olor=?, moho=?, insectos=?, chamico=?,
                grado=?, factor=?, tas=?
            WHERE id_muestreo=? AND seccion=?
        """, valores[2:] + valores[:2])
    else:
        cur.execute("""
            INSERT INTO analisis (
                id_muestreo, seccion,
                temperatura, humedad, ph,
                danados, quebrados, materia_extrana,
                olor, moho, insectos, chamico,
                grado, factor, tas
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, valores)

    conn.commit()
    conn.close()
    return jsonify(ok=True)

# ======================
# MONITOREO
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
# EXTRACCION
# ======================
@app.route("/api/extraccion", methods=["POST"])
def registrar_extraccion():
    d = request.get_json(force=True, silent=True)

    conn = get_db()
    conn.execute("""
        UPDATE silos SET
            estado_silo=?,
            fecha_extraccion=?
        WHERE numero_qr=?
    """, (
        d["estado_silo"],
        ahora().strftime("%Y-%m-%d %H:%M"),
        d["numero_qr"]
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)
# ======================
# SILO (DETALLE)
# ======================
@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()

    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    if not silo:
        conn.close()
        return "Silo no encontrado", 404

    muestreos = conn.execute("""
        SELECT id, fecha_muestreo,
        CAST(julianday('now') - julianday(fecha_muestreo) AS INT) dias
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()

    conn.close()

    return render_template(
        "silo.html",
        silo=silo,
        muestreos=muestreos
    )
# ======================
# NUEVO MUESTREO (DESDE SILO)
# ======================
@app.route("/nuevo_muestreo/<qr>")
def nuevo_muestreo_desde_silo(qr):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO muestreos (numero_qr, fecha_muestreo)
        VALUES (?,?)
    """, (qr, ahora().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    mid = cur.lastrowid
    conn.close()

    return redirect(f"/muestreo/{mid}")
# ======================
# VER MUESTREO
# ======================
@app.route("/muestreo/<int:id>")
def ver_muestreo(id):
    conn = get_db()

    muestreo = conn.execute("""
        SELECT m.*, s.numero_qr, s.cereal
        FROM muestreos m
        JOIN silos s ON s.numero_qr = m.numero_qr
        WHERE m.id=?
    """, (id,)).fetchone()

    if not muestreo:
        conn.close()
        return "Muestreo no encontrado", 404

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
