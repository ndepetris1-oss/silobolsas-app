from flask import Flask, render_template, request, jsonify, send_file, redirect
import sqlite3, os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io

from calculos import calcular_comercial

app = Flask(__name__)

# ======================
# DB PATH
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "silobolsas.db")

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS mercado (
        cereal TEXT PRIMARY KEY,
        pizarra_auto REAL,
        pizarra_manual REAL,
        usar_manual INTEGER DEFAULT 0,
        obs_precio TEXT,
        dolar REAL,
        fecha TEXT
)
""")

    # Datos iniciales mercado
    cereales_base = ["Soja", "Maíz", "Trigo", "Girasol"]

    for cereal in cereales_base:
        c.execute("""
            INSERT OR IGNORE INTO mercado (
                cereal,
                pizarra_auto,
                pizarra_manual,
                usar_manual,
                dolar,
                fecha
            )
        VALUES (?,?,?,?,?,?)
    """, (
        cereal,
        0,      # pizarra_auto
        0,      # pizarra_manual
        0,      # usar_manual
        0,      # dolar
        ahora().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()

init_db()

# ======================
# API — CONSULTA SILO
# ======================
@app.route("/api/silo/<qr>")
def api_silo(qr):
    conn = get_db()
    s = conn.execute(
        "SELECT cereal, fecha_confeccion, estado_silo FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()
    conn.close()

    if not s:
        return jsonify(existe=False)

    return jsonify(
        existe=True,
        cereal=s["cereal"],
        fecha_confeccion=s["fecha_confeccion"],
        estado_silo=s["estado_silo"]
    )

# ======================
# PANEL (ULTRA ROBUSTO)
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
        ORDER BY m.id DESC
        LIMIT 1
    ) ultimo_muestreo
    FROM silos s
    ORDER BY datetime(fecha_confeccion) DESC
""").fetchall()

    registros = []
    
    for s in silos:
        # Conteo de eventos pendientes
        eventos_pendientes = conn.execute("""
            SELECT COUNT(*) AS cant
            FROM monitoreos
            WHERE numero_qr = ?
              AND resuelto = 0
        """, (s["numero_qr"],)).fetchone()["cant"]
        
        grado = None
        factor = None
        tas_min = None
        fecha_extraccion_estimada = None

        try:
            if s["ultimo_muestreo"]:
                analisis = conn.execute("""
                    SELECT grado, factor, tas
                    FROM analisis
                    WHERE id_muestreo=?
                """, (s["ultimo_muestreo"],)).fetchall()

                grados = []
                factores = []
                tass = []

                for a in analisis:
                    # grado: solo si es numérico
                    try:
                        g = int(a["grado"])
                        grados.append(g)
                    except:
                        pass

                    # factor: solo positivos
                    try:
                        f = float(a["factor"])
                        if f > 0:
                            factores.append(f)
                    except:
                        pass

                    # tas: solo positivos
                    try:
                        t = int(a["tas"])
                        if t > 0:
                            tass.append(t)
                    except:
                        pass

                grado = max(grados) if grados else None
                factor = round(sum(factores) / len(factores), 4) if factores else None
                tas_min = min(tass) if tass else None

                if tas_min:
                    row = conn.execute(
                        "SELECT fecha_muestreo FROM muestreos WHERE id=?",
                        (s["ultimo_muestreo"],)
                    ).fetchone()

                    fm = None
                    if row and row["fecha_muestreo"]:
                        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                            try:
                                fm = datetime.strptime(row["fecha_muestreo"], fmt)
                                break
                            except ValueError:
                                pass

                    if fm:
                        fecha_extraccion_estimada = (
                            fm + timedelta(days=int(tas_min))
                        ).strftime("%Y-%m-%d")

        except Exception as e:
            print("ERROR PANEL SILO:", s["numero_qr"], e)


        registros.append({
            **dict(s),
            "grado": grado,
            "factor": factor,
            "tas_min": tas_min,
            "fecha_extraccion_estimada": fecha_extraccion_estimada,
            "eventos": eventos_pendientes
        })

    conn.close()
    return render_template("panel.html", registros=registros)
    
# ======================
# COMERCIAL – PANTALLA
# ======================
@app.route("/comercial")
def comercial():
    conn = get_db()
    rows = conn.execute("""
        SELECT cereal,
               pizarra_auto,
               pizarra_manual,
               usar_manual,
               obs_precio,
               dolar,
               fecha
        FROM mercado
        ORDER BY cereal
    """).fetchall()
    conn.close()

    return render_template("comercial.html", mercado=rows)

# ======================
# COMPARADOR COMERCIAL
# ======================
@app.route("/comercial/<cereal>")
def comparador(cereal):
    conn = get_db()

    rows = conn.execute("""
        SELECT
            s.numero_qr,

            -- FACTOR PROMEDIO
            (
              SELECT ROUND(AVG(a.factor),4)
              FROM analisis a
              JOIN muestreos m ON m.id = a.id_muestreo
              WHERE m.numero_qr = s.numero_qr
                AND a.factor IS NOT NULL
            ) AS factor_prom,

            -- HUMEDAD PROMEDIO
            (
              SELECT ROUND(AVG(a.humedad),2)
              FROM analisis a
              JOIN muestreos m ON m.id = a.id_muestreo
              WHERE m.numero_qr = s.numero_qr
                AND a.humedad IS NOT NULL
            ) AS humedad_prom,

            -- INSECTOS: si hay al menos uno en cualquier sección
            (
              SELECT COUNT(*)
              FROM analisis a
              JOIN muestreos m ON m.id = a.id_muestreo
              WHERE m.numero_qr = s.numero_qr
                AND a.insectos = 1
            ) AS tiene_insectos

        FROM silos s
        WHERE s.estado_silo = 'Activo'
          AND s.cereal = ?
        ORDER BY s.numero_qr
    """, (cereal,)).fetchall()

    conn.close()

    silos = [
        {
            **dict(r),
            "tiene_insectos": True if r["tiene_insectos"] > 0 else False
        }
        for r in rows
    ]

    return render_template(
        "comparador.html",
        cereal=cereal,
        silos=silos
    )

# ======================
# COMERCIAL – API
# ======================
@app.route("/api/mercado/manual", methods=["POST"])
def mercado_manual():
    d = request.get_json()

    if not d or not d.get("cereal"):
        return jsonify(ok=False, error="Cereal faltante"), 400

    conn = get_db()
    conn.execute("""
        UPDATE mercado
        SET
            pizarra_manual=?,
            usar_manual=?,
            obs_precio=?,
            dolar=?,
            fecha=CURRENT_TIMESTAMP
        WHERE cereal=?
    """, (
        d.get("pizarra_manual"),
        1 if d.get("usar_manual") else 0,
        d.get("obs_precio"),
        d.get("dolar"),
        d["cereal"]
    ))
    conn.commit()
    conn.close()

    return jsonify(ok=True)

# ======================
# FORM
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

# ======================
# RESTO DEL ARCHIVO
# ======================
# ⚠️ DESDE ACÁ NO SE TOCA NADA
# (tu código original sigue igual)

# ======================
# REGISTRAR SILO (FIX JSON)
# ======================
@app.route("/api/registrar_silo", methods=["POST"])
def registrar_silo():
    d = request.get_json(force=True, silent=True)

    # ❌ VALIDACIÓN DURA: evitar silo vacío
    campos_obligatorios = [
        "numero_qr",
        "cereal",
        "estado_grano",
        "metros",
        "lat",
        "lon"
    ]

    if not d or not all(d.get(c) not in (None, "", []) for c in campos_obligatorios):
        return jsonify(
            ok=False,
            error="Datos incompletos para registrar el silo"
        ), 400
        
    existe = conn.execute(
        "SELECT 1 FROM silos WHERE numero_qr=?",
        (d["numero_qr"],)
    ).fetchone()

    if existe:
        conn.close()
        return jsonify(
            ok=False,
            error="El silo ya está registrado"
        ), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO silos (
            numero_qr,
            cereal,
            estado_grano,
            estado_silo,
            metros,
            lat,
            lon,
            fecha_confeccion
        ) VALUES (?,?,?,?,?,?,?,?)
    """, (
        d.get("numero_qr"),
        d.get("cereal"),
        d.get("estado_grano"),
        "Activo",
        d.get("metros"),
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

    # 🔒 BLOQUEO SI ESTÁ EXTRAÍDO
    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    if not silo or silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(
            ok=False,
            error="El silo ya fue extraído. No se pueden cargar nuevos muestreos."
        ), 400

    # ✅ SI ESTÁ ACTIVO, CREA EL MUESTREO
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO muestreos (numero_qr, fecha_muestreo)
        VALUES (?,?)
    """, (qr, ahora().strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    mid = cur.lastrowid
    conn.close()

    return jsonify(ok=True, id_muestreo=mid)
# ======================
# INFORMAR CALADO (DESDE FORM)
# ======================
@app.route("/api/informar_calado", methods=["POST"])
def informar_calado():
    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
        return jsonify(ok=False, error="QR faltante"), 400

    conn = get_db()

    # 🔒 validar silo
    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400

    if silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(
            ok=False,
            error="El silo ya fue extraído. No se puede registrar calado."
        ), 400

    # ✅ crear muestreo
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO muestreos (numero_qr, fecha_muestreo)
        VALUES (?,?)
    """, (qr, ahora().strftime("%Y-%m-%d %H:%M")))

    id_muestreo = cur.lastrowid

    # 🧪 ¿informó temperatura?
    if d.get("informar_temperatura"):
        for seccion, campo in [
            ("punta", "temp_punta"),
            ("medio", "temp_medio"),
            ("final", "temp_final")
        ]:
            temp = d.get(campo)

            if temp not in (None, "", ""):
                try:
                    temp = float(temp)
                except ValueError:
                    temp = None

            cur.execute("""
                INSERT INTO analisis (
                    id_muestreo, seccion, temperatura
                ) VALUES (?,?,?)
            """, (
                id_muestreo,
                seccion,
                temp
            ))

    conn.commit()
    conn.close()

    return jsonify(ok=True, id_muestreo=id_muestreo)

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

    conn = get_db()

    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=?",
        (qr,)
    ).fetchone()

    if not silo or silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(
            ok=False,
            error="El silo está extraído. No se pueden cargar eventos."
        ), 400

    path_evento = None
    if foto_evento:
        os.makedirs("static/monitoreos", exist_ok=True)
        path_evento = f"static/monitoreos/{datetime.now().timestamp()}_{foto_evento.filename}"
        foto_evento.save(path_evento)

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
# MONITOREO PENDIENTE
# ======================
@app.route("/api/monitoreo/pendiente/<qr>")
def monitoreos_pendientes(qr):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, tipo, fecha_evento
        FROM monitoreos
        WHERE numero_qr = ?
          AND resuelto = 0
        ORDER BY fecha_evento DESC
    """, (qr,)).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "tipo": r["tipo"],
            "fecha": r["fecha_evento"]
        } for r in rows
    
    ])
    
# ======================
# RESOLVER MONITOREO
# ======================
@app.route("/api/monitoreo/resolver", methods=["POST"])
def resolver_monitoreo():
    id_monitoreo = request.form.get("id_monitoreo")
    foto = request.files.get("foto")

    if not id_monitoreo:
        return jsonify(ok=False, error="ID faltante"), 400

    path_resolucion = None
    if foto:
        os.makedirs("static/monitoreos", exist_ok=True)
        path_resolucion = f"static/monitoreos/resuelto_{datetime.now().timestamp()}_{foto.filename}"
        foto.save(path_resolucion)

    conn = get_db()
    conn.execute("""
        UPDATE monitoreos SET
            resuelto = 1,
            fecha_resolucion = ?,
            foto_resolucion = ?
        WHERE id = ?
    """, (
        ahora().strftime("%Y-%m-%d %H:%M"),
        path_resolucion,
        id_monitoreo
    ))
    conn.commit()
    conn.close()

    return jsonify(ok=True)
    
# ======================
# MONITOREOS RESUELTOS
# ======================
@app.route("/api/monitoreo/resueltos/<qr>")
def monitoreos_resueltos(qr):
    conn = get_db()
    rows = conn.execute("""
        SELECT tipo, fecha_resolucion
        FROM monitoreos
        WHERE numero_qr = ?
          AND resuelto = 1
        ORDER BY fecha_resolucion DESC
    """, (qr,)).fetchall()
    conn.close()

    return jsonify([
        {
            "tipo": r["tipo"],
            "fecha": r["fecha_resolucion"]
        } for r in rows
    ])
# ======================
# EXTRACCION
# ======================
@app.route("/api/extraccion", methods=["POST"])
def registrar_extraccion():
    d = request.get_json(force=True, silent=True)

    # ❌ Validación básica
    if not d or not d.get("numero_qr") or not d.get("estado_silo"):
        return jsonify(ok=False, error="Datos incompletos"), 400

    conn = get_db()

    # 🔍 Verificar silo
    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=?",
        (d["numero_qr"],)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400

    # 🔒 Bloquear doble extracción
    if silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(ok=False, error="El silo ya está extraído"), 400

    # ✅ Actualizar estado
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

    mercado = conn.execute("""
        SELECT
            CASE
                WHEN usar_manual = 1 THEN pizarra_manual
                ELSE pizarra_auto
            END AS pizarra,
            dolar
        FROM mercado
        WHERE cereal = ?
    """, (silo["cereal"],)).fetchone()

    muestreos_raw = conn.execute("""
        SELECT m.id, m.fecha_muestreo,
               CAST(julianday('now') - julianday(m.fecha_muestreo) AS INT) dias
        FROM muestreos m
        WHERE m.numero_qr=?
        ORDER BY m.fecha_muestreo DESC
    """, (qr,)).fetchall()

    muestreos = []
    precio_estimado = None
    precio_usd = None
    factor_prom = None
    tas_usada = None
    analisis_pendiente = False

    for idx, m in enumerate(muestreos_raw):
        analisis = conn.execute("""
            SELECT seccion, grado, factor, tas, temperatura
            FROM analisis
            WHERE id_muestreo=?
        """, (m["id"],)).fetchall()

        por_seccion = {a["seccion"]: a for a in analisis}

        if idx == 0:
            if not analisis:
                analisis_pendiente = True
            else:
                factores = []
                tass = []

                for sec in ["punta", "medio", "final"]:
                    a = por_seccion.get(sec)
                    if a:
                        if a["factor"] is not None:
                            factores.append(a["factor"])
                        if a["tas"] is not None:
                            tass.append(a["tas"])

                if factores:
                    factor_prom = round(sum(factores) / len(factores), 4)

                if tass:
                    tas_usada = min(tass)

                if mercado and factor_prom and mercado["pizarra"] and mercado["dolar"]:
                    precio_estimado = round(mercado["pizarra"] * factor_prom, 2)
                    precio_usd = round(precio_estimado / mercado["dolar"], 2)

        muestreos.append({
            "id": m["id"],
            "fecha_muestreo": m["fecha_muestreo"],
            "dias": m["dias"],
            "punta": por_seccion.get("punta"),
            "medio": por_seccion.get("medio"),
            "final": por_seccion.get("final")
        })

    eventos_pendientes = conn.execute("""
        SELECT tipo, fecha_evento, foto_evento
        FROM monitoreos
        WHERE numero_qr = ?
          AND resuelto = 0
        ORDER BY fecha_evento DESC
    """, (qr,)).fetchall()

    eventos_resueltos = conn.execute("""
        SELECT tipo, fecha_resolucion, foto_resolucion
        FROM monitoreos
        WHERE numero_qr = ?
          AND resuelto = 1
        ORDER BY fecha_resolucion DESC
    """, (qr,)).fetchall()

    conn.close()

    return render_template(
        "silo.html",
        silo=silo,
        muestreos=muestreos,
        eventos_pendientes=eventos_pendientes,
        eventos_resueltos=eventos_resueltos,
        mercado=mercado,
        precio_estimado=precio_estimado,
        precio_usd=precio_usd,
        factor_prom=factor_prom,
        tas_usada=tas_usada,
        analisis_pendiente=analisis_pendiente
    )

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
