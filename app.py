from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io

from calculos import (
    grado_maiz, factor_maiz, tas_maiz,
    grado_trigo, factor_trigo, tas_trigo,
    factor_soja, factor_girasol
)

app = Flask(__name__)
DB_NAME = "silobolsas.db"

def ahora_argentina():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

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
        tas_min = None
        fecha_extraccion = None

        if s["ultimo_muestreo"]:
            datos = conn.execute("""
                SELECT grado, factor, tas
                FROM analisis
                WHERE id_muestreo=?
            """, (s["ultimo_muestreo"],)).fetchall()

            if datos:
                grados = [d["grado"] for d in datos if d["grado"] is not None]
                grado = max(grados) if grados else None

                factores = [d["factor"] for d in datos if d["factor"] is not None]
                factor = round(sum(factores) / len(factores), 4) if factores else None

                tas_vals = [d["tas"] for d in datos if d["tas"] is not None]
                tas_min = min(tas_vals) if tas_vals else None

                if tas_min:
                    fecha_m = conn.execute(
                        "SELECT fecha_muestreo FROM muestreos WHERE id=?",
                        (s["ultimo_muestreo"],)
                    ).fetchone()["fecha_muestreo"]

                    fecha_m = datetime.strptime(fecha_m, "%Y-%m-%d %H:%M")
                    fecha_extraccion = (fecha_m + timedelta(days=tas_min)).strftime("%Y-%m-%d")

        resultado.append({
            **dict(s),
            "grado": grado,
            "factor": factor,
            "tas_min": tas_min,
            "fecha_extraccion": fecha_extraccion
        })

    conn.close()
    return render_template("panel.html", registros=resultado)

# ======================
# FORM
# ======================
@app.route("/form")
def form():
    return render_template("form.html")

# ======================
# GUARDAR SILO
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
            UPDATE silos SET cereal=?, estado=?, metros=?, lat=?, lon=?
            WHERE numero_qr=?
        """, (
            d["cereal"], d["estado"], d["metros"],
            d.get("lat"), d.get("lon"), d["numero_qr"]
        ))
    else:
        conn.execute("""
            INSERT INTO silos VALUES (?,?,?,?,?,?,?)
        """, (
            d["numero_qr"], d["cereal"], d["estado"], d["metros"],
            d.get("lat"), d.get("lon"),
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
    conn.close()
    return jsonify(ok=True)

# ======================
# SILO
# ======================
@app.route("/silo/<qr>")
def ver_silo(qr):
    conn = get_db()

    silo = conn.execute(
        "SELECT * FROM silos WHERE numero_qr=?", (qr,)
    ).fetchone()

    muestreos = conn.execute("""
        SELECT id, fecha_muestreo,
        CAST((julianday('now') - julianday(fecha_muestreo)) AS INTEGER) AS dias_desde
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
    return render_template("muestreo.html", muestreo=muestreo, analisis=analisis)

if __name__ == "__main__":
    app.run(debug=True)
