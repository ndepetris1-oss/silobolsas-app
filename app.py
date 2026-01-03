from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "silos.db"


# ---------- DB ----------
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
            extraido INTEGER DEFAULT 0,
            fecha_registro TEXT,
            fecha_extraccion TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------- VISTAS ----------
@app.route("/")
@app.route("/form")
def form():
    return render_template("form.html")


@app.route("/panel")
def panel():
    conn = get_db()
    registros = conn.execute(
        "SELECT * FROM silos ORDER BY fecha_registro DESC"
    ).fetchall()
    conn.close()
    return render_template("panel.html", registros=registros)


# ---------- API ----------
@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()

    try:
        conn = get_db()
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
            datetime.now().isoformat(),
            data.get("fecha_extraccion")
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/data")
def data():
    conn = get_db()
    rows = conn.execute("SELECT * FROM silos").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/delete", methods=["POST"])
def delete():
    numero_qr = request.json.get("numero_qr")
    conn = get_db()
    conn.execute("DELETE FROM silos WHERE numero_qr = ?", (numero_qr,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ---------- MAIN ----------
if __name__ == "__main__":
    app.run(debug=True)
