from flask import Flask, request, jsonify, render_template
from datetime import datetime
import requests
import os

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "silobolsas"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

@app.route("/silo")
def silo_form():
    numero_qr = request.args.get("id")
    return render_template("form.html", numero_qr=numero_qr)

@app.route("/api/save", methods=["POST"])
def save_data():
    data = request.json
    data["fecha"] = datetime.now().isoformat()
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    r = requests.post(url, headers=headers, json=data)
    return jsonify({"status": "ok", "supabase_response": r.json()})

@app.route("/panel")
def panel():
    return render_template("panel.html")

@app.route("/api/list")
def list_data():
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*"
    r = requests.get(url, headers=headers)
    return jsonify(r.json())

if __name__ == "__main__":
    app.run(debug=True)
