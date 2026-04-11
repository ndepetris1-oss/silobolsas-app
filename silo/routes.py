from flask import Blueprint, render_template, request
from db import get_db
from calculos import calcular_comercial

silo_bp = Blueprint("silo", __name__)

@silo_bp.route("/llenado/<silo_codigo>", methods=["GET", "POST"])
def llenado_silo(silo_codigo):

    conn = get_db()

    # 🔹 Traer silo (para saber el cereal)
    silo = conn.execute("""
        SELECT *
        FROM silos
        WHERE numero_qr=?
    """, (silo_codigo,)).fetchone()

    resultado = None

    if request.method == "POST":

        # 👇 armamos dict como espera calculos.py
        d = {
            "temperatura": float(request.form.get("temp") or 0),
            "humedad": float(request.form.get("humedad") or 0),
            "danados": float(request.form.get("danados") or 0),
            "quebrados": float(request.form.get("quebrados") or 0),
            "materia_extrana": float(request.form.get("mext") or 0),
            "olor": float(request.form.get("olor") or 0),
            "moho": float(request.form.get("moho") or 0),
            "chamico": float(request.form.get("chamico") or 0),
        }
        d["kg"] = float(request.form.get("kg") or 0)
        # 👇 USAMOS TU MOTOR REAL
        resultado = calcular_comercial(silo["cereal"], d)
        # 🔥 para mostrar en pantalla
        resultado["kg"] = d["kg"]

        # agregamos datos para mostrar
        resultado["temp"] = d["temperatura"]
        resultado["humedad"] = d["humedad"]
        resultado["danados"] = d["danados"]
        resultado["quebrados"] = d["quebrados"]
        resultado["mext"] = d["materia_extrana"]
        resultado["olor"] = d["olor"]
        resultado["moho"] = d["moho"]
        resultado["chamico"] = d["chamico"]

    conn.close()

    return render_template(
        "llenado.html",
        silo=silo,
        resultado=resultado
    )
