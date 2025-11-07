from flask import Flask, render_template, request, redirect, url_for, send_file
import csv
import os
from datetime import datetime
import io
import pandas as pd

app = Flask(__name__)

CSV_FILE = 'silobolsas.csv'


def ensure_csv_exists():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["numero_qr", "cereal", "metros", "lat", "lon", "fecha_creacion", "fecha_extraccion"])


def read_csv():
    ensure_csv_exists()
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(data):
    ensure_csv_exists()
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(data)


def update_extraccion(numero_qr):
    rows = read_csv()
    for row in rows:
        if row["numero_qr"] == numero_qr and row["fecha_extraccion"] == "":
            row["fecha_extraccion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


@app.route('/')
def index():
    return render_template('form.html')


@app.route('/form', methods=['GET', 'POST'])
def form():
    ensure_csv_exists()

    if request.method == 'POST':
        numero_qr = request.form['numero_qr']
        rows = read_csv()

        # Si ya existe el QR → preguntar por extracción
        for row in rows:
            if row["numero_qr"] == numero_qr:
                extraccion = request.form.get('extraccion')
                if extraccion == "SI":
                    update_extraccion(numero_qr)
                    return redirect(url_for('panel'))
                else:
                    return redirect(url_for('panel'))

        # Si es un QR nuevo → crear registro
        cereal = request.form['cereal']
        metros = request.form['metros']
        lat = request.form['lat']
        lon = request.form['lon']
        fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        write_csv([numero_qr, cereal, metros, lat, lon, fecha_creacion, ""])
        return redirect(url_for('panel'))

    numero_qr = request.args.get('numero_qr')
    return render_template('form.html', numero_qr=numero_qr)


@app.route('/panel')
def panel():
    rows = read_csv()
    return render_template('panel.html', rows=rows)


@app.route('/exportar')
def exportar():
    rows = read_csv()
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='silobolsas.xlsx')


@app.route('/marcar_extraccion/<numero_qr>')
def marcar_extraccion(numero_qr):
    update_extraccion(numero_qr)
    return redirect(url_for('panel'))


if __name__ == '__main__':
    ensure_csv_exists()
    app.run(host='0.0.0.0', port=10000)
