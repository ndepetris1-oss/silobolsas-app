from flask import Blueprint, request, jsonify, render_template
from utils.auditoria import registrar_auditoria
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from datetime import datetime
from flask import redirect, url_for
from bs4 import BeautifulSoup

calado_bp = Blueprint("calado", __name__, url_prefix="/calado")


def ahora():
    return datetime.now()

# ======================
# INFORMAR CALADO
# ======================
@calado_bp.route("/api/informar_calado", methods=["POST"])
@login_required
def informar_calado():

    if not tiene_permiso("calado"):
        return acceso_denegado("calado")

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
        return jsonify(ok=False, error="QR faltante"), 400

    empresa_id = current_user.empresa_id
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()

    # 🔒 validar silo
    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, empresa_id)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400

    if silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(
            ok=False,
            error="El silo ya fue extraído."
        ), 400

    # ✅ crear muestreo
    conn.execute("""
        INSERT INTO muestreos (
            numero_qr,
            empresa_id,
            fecha_muestreo
        )
        VALUES (?,?,?)
    """, (qr, empresa_id, fecha))

    # Obtener el id recien insertado (compatible SQLite y PostgreSQL)
    id_row = conn.execute("""
        SELECT id FROM muestreos
        WHERE numero_qr=? AND empresa_id=?
        ORDER BY id DESC LIMIT 1
    """, (qr, empresa_id)).fetchone()
    id_muestreo = id_row["id"]

    # 🧪 Temperaturas
    if d.get("informar_temperatura"):

        for seccion, campo in [
            ("punta", "temp_punta"),
            ("medio", "temp_medio"),
            ("final", "temp_final")
        ]:

            temp = d.get(campo)

            if temp not in (None, ""):
                try:
                    temp = float(temp)
                except:
                    temp = None

            conn.execute("""
                INSERT INTO analisis (
                    id_muestreo,
                    empresa_id,
                    seccion,
                    temperatura
                )
                VALUES (?,?,?,?)
            """, (
                id_muestreo,
                empresa_id,
                seccion,
                temp
            ))

    registrar_auditoria(conn, current_user.id, empresa_id,
        "calado", f"Muestreo ID: {id_muestreo}", qr)
    conn.commit()
    conn.close()

    return jsonify(ok=True, id_muestreo=id_muestreo)

@calado_bp.route("/")
@login_required
def calado():

    if not tiene_permiso("calado"):
        return acceso_denegado("calado")

    return render_template("form.html")

@calado_bp.route("/nuevo_muestreo/<qr>")
@login_required
def nuevo_muestreo(qr):

    if not tiene_permiso("calado"):
        return acceso_denegado("calado")

    # si tiene permiso, redirige a la lógica real
    return redirect(url_for("panel.form", id=qr))
