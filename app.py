from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
import csv, io

app = Flask(__name__)
DB_NAME = "silos.db"

# ======================
# DB
# ======================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


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
        factor REAL
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
                SELECT seccion, grado, factor
                FROM analisis
                WHERE id_muestreo = ?
            """, (s["ultimo_muestreo"],)).fetchall()

            if s["cereal"] in ("Maíz", "Trigo"):
                pesos = {"punta": 0.2, "medio": 0.6, "final": 0.2}
                total = 0
                g = 1

                for d in datos:
                    total += (d["factor"] or 0) * pesos.get(d["seccion"], 0)
                    g = max(g, d["grado"] or 1)

                grado = g
                factor = round(total, 3)

            else:
                # Soja / Girasol → solo factor ponderado
                pesos = {"punta": 0.2, "medio": 0.6, "final": 0.2}
                factor = round(
                    sum((d["factor"] or 0) * pesos.get(d["seccion"], 0) for d in datos),
                    3
                )

        resultado.append({**dict(s), "grado": grado, "factor": factor})

    conn.close()
    return render_template("panel.html", registros=resultado)


@app.route("/form")
def form():
    return render_template("form.html")


# ======================
# REGISTRAR SILO
# ======================
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
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# CÁLCULOS
# ======================
def calcular_maiz_trigo(d):
    grado = 1
    if d["danados"] > 5 or d["quebrados"] > 3 or d["materia_extrana"] > 1:
        grado = 2
    if d["danados"] > 8 or d["quebrados"] > 5 or d["materia_extrana"] > 2:
        grado = 3

    factor = 1.0
    if d["danados"] > 8:
        factor -= (d["danados"] - 8) * 0.01
    if d["quebrados"] > 5:
        factor -= (d["quebrados"] - 5) * 0.01
    if d["materia_extrana"] > 2:
        factor -= (d["materia_extrana"] - 2) * 0.01

    return grado, round(max(factor, 0), 3)


def calcular_soja_girasol(d):
    factor = 1.0

    if d.get("humedad") and float(d["humedad"]) > 14:
        factor -= (float(d["humedad"]) - 14) * 0.01

    if d.get("materia_extrana") and float(d["materia_extrana"]) > 1:
        factor -= (float(d["materia_extrana"]) - 1) * 0.01

    if d.get("danados") and float(d["danados"]) > 5:
        factor -= (float(d["danados"]) - 5) * 0.01

    return round(max(factor, 0), 3)


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
    """, (qr, datetime.now().isoformat()))
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return jsonify(id_muestreo=mid)


# ======================
# GUARDAR / EDITAR ANÁLISIS
# ======================
@app.route("/api/analisis_seccion", methods=["POST"])
def guardar_analisis_seccion():
    d = request.get_json()

    grado = None
    factor = None

    if d["cereal"] in ("Maíz", "Trigo"):
        grado, factor = calcular_maiz_trigo(d)
    else:
        factor = calcular_soja_girasol(d)

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
                grado=?, factor=?
            WHERE id=?
        """, (
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
            existe["id"]
        ))
    else:
        conn.execute("""
            INSERT INTO analisis (
                id_muestreo, seccion, temperatura, humedad, ph,
                danados, quebrados, materia_extrana,
                olor, moho, insectos, chamico, grado, factor
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d["id_muestreo"],
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
            factor
        ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# VISTA SILO
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
        SELECT id, fecha_muestreo
        FROM muestreos
        WHERE numero_qr=?
        ORDER BY fecha_muestreo DESC
    """, (qr,)).fetchall()

    conn.close()
    return render_template("silo.html", silo=silo, muestreos=muestreos)


# ======================
# VISTA MUESTREO
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

    if not muestreo:
        conn.close()
        return "Muestreo no encontrado", 404

    analisis = conn.execute("""
        SELECT * FROM analisis
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

    return send_file(mem, as_attachment=True,
                     download_name="silos.csv",
                     mimetype="text/csv")


if __name__ == "__main__":
    app.run(debug=True)
