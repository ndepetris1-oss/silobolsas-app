from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, json, io
from datetime import datetime
import pandas as pd

app = Flask(__name__)
DB = "silos.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def norm(t):
    return t.lower().replace("í","i").replace("á","a")

def init():
    c=db()
    c.execute("""
      CREATE TABLE IF NOT EXISTS silos(
        numero_qr TEXT PRIMARY KEY,
        cereal TEXT, estado TEXT, metros INT,
        lat REAL, lon REAL,
        fecha_confeccion TEXT,
        grado INT, factor REAL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS analisis(
        id INTEGER PRIMARY KEY,
        numero_qr TEXT,
        datos TEXT,
        grado INT, factor REAL,
        fecha TEXT
      )
    """)
    c.commit(); c.close()
init()

# ----------------- VISTAS -----------------
@app.route("/")
@app.route("/panel")
def panel():
    c=db()
    r=c.execute("SELECT * FROM silos").fetchall()
    c.close()
    return render_template("panel.html", registros=r)

@app.route("/form")
def form():
    return render_template("form.html")

# ----------------- REGISTRO -----------------
@app.route("/api/save",methods=["POST"])
def save():
    d=request.json
    c=db()
    if not c.execute("SELECT 1 FROM silos WHERE numero_qr=?",(d["numero_qr"],)).fetchone():
        c.execute("""
          INSERT INTO silos VALUES (?,?,?,?,?,?,?,NULL,NULL)
        """,(d["numero_qr"],d["cereal"],d["estado"],d["metros"],
             d["lat"],d["lon"],d["fecha_confeccion"]))
    c.commit(); c.close()
    return jsonify(ok=True)

# ----------------- GRADOS -----------------
def grado_maiz(datos):
    g=[]
    ph=float(datos["ph"])
    dan=float(datos["danados"])
    q=float(datos["quebrados"])
    me=float(datos["me"])
    g.append(1 if ph>=75 else 2 if ph>=72 else 3)
    g.append(1 if dan<=3 else 2 if dan<=8 else 3)
    g.append(1 if q<=2 else 2 if q<=5 else 3)
    g.append(1 if me<=1 else 2 if me<=2 else 3)
    return max(g)

def grado_trigo(datos):
    g=[]
    ph=float(datos["ph"])
    dan=float(datos["danados"])
    g.append(1 if ph>=79 else 2 if ph>=76 else 3)
    g.append(1 if dan<=0.5 else 2 if dan<=1.5 else 3)
    return max(g)

# ----------------- ANALISIS -----------------
@app.route("/api/analisis",methods=["POST"])
def analisis():
    d=request.json
    cereal=norm(d["cereal"])
    datos=d["datos"]

    if cereal=="maiz":
        grado=grado_maiz(datos)
    elif cereal=="trigo":
        grado=grado_trigo(datos)
    else:
        grado=None

    factor=1.0  # Soja y Girasol solo factor, Maíz/Trigo precio por grado

    c=db()
    c.execute("""
      INSERT INTO analisis VALUES (NULL,?,?,?,?,?)
    """,(d["numero_qr"],json.dumps(datos),grado,factor,datetime.now().isoformat()))
    c.execute("""
      UPDATE silos SET grado=?, factor=? WHERE numero_qr=?
    """,(grado,factor,d["numero_qr"]))
    c.commit(); c.close()

    return jsonify(grado=grado,factor=factor)

# ----------------- EXPORT -----------------
@app.route("/api/export")
def export():
    c=db()
    r=c.execute("SELECT * FROM silos").fetchall()
    df=pd.DataFrame(r,columns=r[0].keys())
    out=io.BytesIO()
    df.to_excel(out,index=False)
    out.seek(0)
    return send_file(out,download_name="silos.xlsx",as_attachment=True)

if __name__=="__main__":
    app.run(debug=True)
