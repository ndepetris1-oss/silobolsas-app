from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import io
import json

app = Flask(__name__)
DB_NAME = "silos.db"

# =========================
# UTILIDADES
# =========================
def normalizar(texto):
    if not texto:
        return ""
    return (
        texto.lower()
        .replace("á","a")
        .replace("é","e")
        .replace("í","i")
        .replace("ó","o")
        .replace("ú","u")
    )

# =========================
# DB
# =========================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Tabla principal de silos
    c.execute("""
        CREATE TABLE IF NOT EXISTS silos (
            numero_qr TEXT PRIMARY KEY,
            cereal TEXT,
            estado TEXT,
            metros INTEGER,
            lat REAL,
            lon REAL,
            extraido INTEGER DEFAULT 0,
            fecha_registro TEXT,
            fecha_extraccion TEXT,
            factor REAL,
            grado INTEGER
        )
    """)

    # Histórico de análisis comercial
    c.execute("""
        CREATE TABLE IF NOT EXISTS analisis_comercial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT,
            fecha_analisis TEXT,
            datos TEXT,
            factor REAL,
            grado INTEGER
        )
    """)

    conn.commit()
    conn.close()


init_db()

# =========================
# VISTAS
# =========================
@app.route("/")
@app.route("/form")
def form():
    return render_template("form.html")


@app.route("/panel")
def panel():
    conn = get_db()
    registros = conn.execute("""
        SELECT
            numero_qr,
            cereal,
            estado,
            metros,
            lat,
            lon,
            extraido,
            fecha_registro AS fecha_confeccion,
            fecha_extraccion,
            factor,
            grado
        FROM silos
        ORDER BY
            CASE WHEN estado = 'Humedo' THEN 0 ELSE 1 END,
            fecha_registro ASC
    """).fetchall()
    conn.close()

    return render_template("panel.html", registros=registros)

# =========================
# API – REGISTRO DE SILO
# =========================
@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()

    try:
        conn = get_db()

        # INSERTA solo la primera vez
        conn.execute("""
            INSERT INTO silos (
                numero_qr, cereal, estado, metros, lat, lon,
                extraido, fecha_registro, fecha_extraccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(numero_qr) DO UPDATE SET
                cereal=excluded.cereal,
                estado=excluded.estado,
                metros=excluded.metros,
                lat=excluded.lat,
                lon=excluded.lon,
                extraido=excluded.extraido,
                fecha_extraccion=excluded.fecha_extraccion
        """, (
            data["numero_qr"],
            data.get("cereal"),
            data.get("estado"),
            data.get("metros"),
            data.get("lat"),
            data.get("lon"),
            data.get("extraido", 0),
            datetime.now().isoformat(),   # fecha confección SOLO en insert
            data.get("fecha_extraccion")
        ))

        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =========================
# CÁLCULOS MAÍZ
# =========================
def calcular_factor_maiz(humedad):
    f = 1.0
    if humedad > 14.5 and humedad <= 16:
        f -= (humedad - 14.5) * 0.015
    elif humedad > 16 and humedad <= 18:
        f -= (1.5 * 0.015) + (humedad - 16) * 0.025
    elif humedad > 18:
        f -= (1.5 * 0.015) + (2 * 0.025) + (humedad - 18) * 0.04
    return round(max(f, 0.70), 3)


def calcular_grado_maiz(ph):
    if ph >= 75:
        return 1
    elif ph >= 72:
        return 2
    else:
        return 3

# =========================
# API – ANÁLISIS COMERCIAL
# =========================
@app.route("/api/analisis", methods=["POST"])
def analisis():
    data = request.get_json()

    numero_qr = data["numero_qr"]
    cereal = normalizar(data["cereal"])
    datos = data["datos"]

    factor = None
    grado = None

    if cereal == "maiz":
        humedad = float(datos.get("humedad", 0))
        ph = float(datos.get("ph", 0))

        factor = calcular_factor_maiz(humedad)
        grado = calcular_grado_maiz(ph)

    conn = get_db()

    # Guardar histórico
    conn.execute("""
        INSERT INTO analisis_comercial
        (numero_qr, fecha_analisis, datos, factor, grado)
        VALUES (?, ?, ?, ?, ?)
    """, (
        numero_qr,
        datetime.now().isoformat(),
        json.dumps(datos),
        factor,
        grado
    ))

    # Actualizar silo
    conn.execute("""
        UPDATE silos
        SET factor = ?, grado = ?
        WHERE numero_qr = ?
    """, (factor, grado, numero_qr))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "factor": factor,
        "grado": grado
    })

# =========================
# API – BORRADOS
# =========================
@app.route("/api/delete", methods=["POST"])
def delete():
    numero_qr = request.json.get("numero_qr")
    conn = get_db()
    conn.execute("DELETE FROM silos WHERE numero_qr = ?", (numero_qr,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/delete_all", methods=["POST"])
def delete_all():
    conn = get_db()
    conn.execute("DELETE FROM silos")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# =========================
# EXPORTAR EXCEL
# =========================
@app.route("/api/export")
def export_excel():
    conn = get_db()
    rows = conn.execute("""
        SELECT
            numero_qr      AS QR,
            cereal         AS Cereal,
            estado         AS Estado,
            metros         AS Metros,
            factor         AS Factor,
            grado          AS Grado,
            fecha_registro AS Fecha_Confeccion
        FROM silos
        ORDER BY
            CASE WHEN estado = 'Humedo' THEN 0 ELSE 1 END,
            fecha_registro ASC
    """).fetchall()
    conn.close()

    if not rows:
        return "No hay datos para exportar", 400

    df = pd.DataFrame(rows, columns=rows[0].keys())

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Silo Bolsas")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="silo_bolsas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
