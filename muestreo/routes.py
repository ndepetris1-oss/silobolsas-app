from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from datetime import datetime

muestreo_bp = Blueprint("muestreo", __name__, url_prefix="/muestreo")


def ahora():
    return datetime.now()


# ======================
# API — CONSULTA SILO
# ======================
@muestreo_bp.route("/api/silo/<qr>")
@login_required
def api_silo(qr):

    if not tiene_permiso("form"):
        return acceso_denegado("form")

    conn = get_db()

    s = conn.execute("""
        SELECT
            s.cereal,
            s.fecha_confeccion,
            s.estado_silo,
            (
            SELECT MAX(fecha_muestreo)
            FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
                AND m.empresa_id = s.empresa_id
            ) AS ultimo_calado
        FROM silos s
        WHERE s.numero_qr=? AND s.empresa_id=?
    """, (qr, current_user.empresa_id)).fetchone()

    conn.close()

    if not s:
        return jsonify(existe=False)

    return jsonify(
        existe=True,
        cereal=s["cereal"],
        fecha_confeccion=s["fecha_confeccion"],
        estado_silo=s["estado_silo"],
        ultimo_calado=s["ultimo_calado"]
    )


# ======================
# API — NUEVO MUESTREO
# ======================
@muestreo_bp.route("/api/nuevo_muestreo", methods=["POST"])
@login_required
def api_nuevo_muestreo():

    if not tiene_permiso("calado"):
        return acceso_denegado("calado")

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("qr")

    if not qr:
        return jsonify(error="QR faltante"), 400

    conn = get_db()

    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchone()

    if not silo or silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(
            ok=False,
            error="El silo ya fue extraído."
        ), 400


    conn.execute("""
        INSERT INTO muestreos (numero_qr, empresa_id, fecha_muestreo)
        VALUES (?,?,?)
    """, (
        qr,
        current_user.empresa_id,
        ahora().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    mid = cur.lastrowid
    conn.close()

    return jsonify(ok=True, id_muestreo=mid)


# ======================
# VER MUESTREO
# ======================
@muestreo_bp.route("/<int:id>")
@login_required
def ver_muestreo(id):

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()

    muestreo = conn.execute("""
        SELECT m.*, s.numero_qr, s.cereal
        FROM muestreos m
        JOIN silos s
            ON s.numero_qr = m.numero_qr
        AND s.empresa_id = m.empresa_id
        WHERE m.id=? AND m.empresa_id=?
    """, (id, current_user.empresa_id)).fetchone()

    if not muestreo:
        conn.close()
        return "Muestreo no encontrado", 404

    analisis = conn.execute("""
        SELECT *
        FROM analisis
        WHERE id_muestreo=? AND empresa_id=?
        ORDER BY seccion
    """, (id, current_user.empresa_id)).fetchall()

    conn.close()

    return render_template(
        "muestreo.html",
        muestreo=muestreo,
        analisis=analisis,
        puede_laboratorio=tiene_permiso("laboratorio")
    )