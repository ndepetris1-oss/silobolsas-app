from flask import Flask, request, render_template, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

# --- Crear base de datos si no existe ---
def init_db():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS silobolsas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_qr TEXT UNIQUE,
        cereal TEXT,
        metros INTEGER,
        lat REAL,
        lon REAL,
        fecha TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Ruta principal opcional ---
@app.route("/")
def home():
    return "<h2>Sistema de Silobolsas activo ✅</h2><p>Usá /form?id=SB0001 o /panel</p>"

# --- Formulario para registrar datos ---
@app.route("/form")
def form():
    numero_qr = request.args.get("id", "SIN_ID")
    return render_template("form.html", numero_qr=numero_qr)

# --- Guardar datos enviados ---
@app.route("/api/save", methods=["POST"])
def save():
    data = request.json
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO silobolsas (numero_qr, cereal, metros, lat, lon, fecha)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["numero_qr"],
        data["cereal"],
        data["metros"],
        data["lat"],
        data["lon"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# --- Panel con los datos ---
@app.route("/panel")
def panel():
    conn = sqlite3.connect("silobolsas.db")
    c = conn.cursor()
    c.execute("SELECT numero_qr, cereal, metros, lat, lon, fecha FROM silobolsas")
    silos = c.fetchall()
    conn.close()
    return render_template("panel.html", silos=silos)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
