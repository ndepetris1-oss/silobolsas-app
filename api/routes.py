from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso
from datetime import datetime
import os
from calculos import calcular_comercial
from flask import request, jsonify

api_bp = Blueprint("api", __name__)

def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# ======================
# REGISTRAR SILO
# ======================
@api_bp.route("/api/registrar_silo", methods=["POST"])
@login_required
def registrar_silo():

    if not tiene_permiso("form"):
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True)

    if not d or not d.get("numero_qr"):
        return jsonify(ok=False, error="QR faltante"), 400

    conn = get_db()

    conn.execute("""
        INSERT INTO silos (
            numero_qr,
            empresa_id,
            sucursal_id,
            cereal,
            estado_grano,
            estado_silo,
            metros,
            lat,
            lon,
            fecha_confeccion
        )
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("numero_qr"),
        current_user.empresa_id,
        current_user.sucursal_id,
        d.get("cereal"),
        d.get("estado_grano"),
        "Activo",
        d.get("metros"),
        d.get("lat"),
        d.get("lon"),
        ahora()
    ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)


# ======================
# NUEVO MUESTREO
# ======================
@api_bp.route("/api/nuevo_muestreo", methods=["POST"])
@login_required
def nuevo_muestreo():

    if not tiene_permiso("calado"):
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("qr")

    if not qr:
        return jsonify(error="QR faltante"), 400

    conn = get_db()

    silo = conn.execute("""
        SELECT estado_silo, empresa_id
        FROM silos
        WHERE numero_qr=?
    """, (qr,)).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400

    # 🔒 Aislamiento por empresa
    if not current_user.es_superadmin and silo["empresa_id"] != current_user.empresa_id:
        conn.close()
        return jsonify(ok=False, error="No autorizado"), 403

    if silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(ok=False, error="Silo extraído"), 400

    cur = conn.cursor()
    cur.execute("""
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
# ANALISIS — SECCION
# ======================
@api_bp.route("/api/analisis_seccion", methods=["POST"])
@login_required
def guardar_analisis_seccion():

    if not tiene_permiso("laboratorio"):
        return jsonify(ok=False, error="No autorizado"), 403
    
    d = request.get_json(force=True, silent=True) or {}
    
    def to_float(x):
        if x is None:
            return None
        if isinstance(x, str) and x.strip() == "":
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    for k in [
            "temperatura","humedad","ph","danados",
            "quebrados","materia_extrana",
            "olor","moho","chamico",
            "granos_carbon","panza_blanca",
            "granos_picados","punta_sombreada",
            "revolcado_tierra","punta_negra",
            "proteinas",
            "materia_grasa",
            "acidez"
        ]:
        d[k] = to_float(d.get(k))

    d["insectos"] = 1 if d.get("insectos") else 0

    conn = get_db()
    cur = conn.cursor()

    existente = cur.execute("""
        SELECT id FROM analisis
        WHERE id_muestreo=? AND seccion=? AND empresa_id=?
    """, (
        d["id_muestreo"],
        d["seccion"],
        current_user.empresa_id
    )).fetchone()

    muestreo = conn.execute("""
        SELECT s.cereal
        FROM muestreos m
        JOIN silos s 
            ON s.numero_qr = m.numero_qr
        AND s.empresa_id = m.empresa_id
        WHERE m.id=? AND m.empresa_id=?
    """, (
        d["id_muestreo"],
        current_user.empresa_id
    )).fetchone()

    if not muestreo:
        conn.close()
        return jsonify(ok=False, error="Muestreo inválido"), 403

    cereal_real = muestreo["cereal"]

    res = calcular_comercial(cereal_real, d)

    valores = (
        d["id_muestreo"],
        d["seccion"],
        d["temperatura"],
        d["humedad"],
        d["ph"],
        d["danados"],
        d["quebrados"],
        d["materia_extrana"],
        d["olor"],
        d["moho"],
        d["insectos"],
        d["chamico"],
        res["grado"],
        res["factor"],
        res["tas"]
    )

    if existente:
        cur.execute("""
            UPDATE analisis SET
                temperatura=?,
                humedad=?,
                ph=?,
                danados=?,
                quebrados=?,
                materia_extrana=?,
                olor=?,
                moho=?,
                insectos=?,
                chamico=?,
                granos_carbon=?,
                panza_blanca=?,
                granos_picados=?,
                punta_sombreada=?,
                revolcado_tierra=?,
                punta_negra=?,
                proteinas=?,
                materia_grasa=?,
                acidez=?,
                grado=?,
                factor=?,
                tas=?
            WHERE id_muestreo=? AND seccion=? AND empresa_id=?
        """, (
            d["temperatura"],
            d["humedad"],
            d["ph"],
            d["danados"],
            d["quebrados"],
            d["materia_extrana"],
            d["olor"],
            d["moho"],
            d["insectos"],
            d["chamico"],
            d.get("granos_carbon"),
            d.get("panza_blanca"),
            d.get("granos_picados"),
            d.get("punta_sombreada"),
            d.get("revolcado_tierra"),
            d.get("punta_negra"),
            d.get("proteinas"),
            d.get("materia_grasa"),
            d.get("acidez"),
            res["grado"],
            res["factor"],
            res["tas"],
            d["id_muestreo"],
            d["seccion"],
            current_user.empresa_id
        ))
    else:
        cur.execute("""
            INSERT INTO analisis (
                id_muestreo,
                empresa_id,
                seccion,
                temperatura,
                humedad,
                ph,
                danados,
                quebrados,
                materia_extrana,
                olor,
                moho,
                insectos,
                chamico,
                granos_carbon,
                panza_blanca,
                granos_picados,
                punta_sombreada,
                revolcado_tierra,
                punta_negra,
                proteinas,
                materia_grasa,
                acidez,
                grado,
                factor,
                tas
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d["id_muestreo"],
            current_user.empresa_id,
            d["seccion"],
            d["temperatura"],
            d["humedad"],
            d["ph"],
            d["danados"],
            d["quebrados"],
            d["materia_extrana"],
            d["olor"],
            d["moho"],
            d["insectos"],
            d["chamico"],
            d.get("granos_carbon"),
            d.get("panza_blanca"),
            d.get("granos_picados"),
            d.get("punta_sombreada"),
            d.get("revolcado_tierra"),
            d.get("punta_negra"),
            d.get("proteinas"),
            d.get("materia_grasa"),
            d.get("acidez"),
            res["grado"],
            res["factor"],
            res["tas"]
        ))
    conn.commit()
    conn.close()

    return jsonify(ok=True)

# ======================
# API — CONSULTA SILO
# ======================
@api_bp.route("/api/silo/<qr>")
@login_required
def api_silo(qr):

    if not tiene_permiso("form"):
        return jsonify(existe=False), 403

    conn = get_db()

    s = conn.execute("""
        SELECT
            s.cereal,
            s.fecha_confeccion,
            s.estado_silo,
            (
              SELECT MAX(fecha_muestreo)
              FROM muestreos
              WHERE numero_qr = s.numero_qr
              AND empresa_id = s.empresa_id
            ) AS ultimo_calado
        FROM silos s
        WHERE s.numero_qr=?
        AND s.empresa_id = ?
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
@api_bp.route("/api/monitoreo/pendiente/<qr>")
@login_required
def monitoreos_pendientes(qr):

    conn = get_db()

    rows = conn.execute("""
        SELECT id, tipo, fecha_evento
        FROM monitoreos
        WHERE numero_qr = ?
          AND empresa_id = ?
          AND resuelto = 0
        ORDER BY fecha_evento DESC
    """, (qr, current_user.empresa_id)).fetchall()

    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "tipo": r["tipo"],
            "fecha": r["fecha_evento"]
        } for r in rows
    ])
@api_bp.route("/api/monitoreo/resueltos/<qr>")
@login_required
def monitoreos_resueltos(qr):

    conn = get_db()

    rows = conn.execute("""
        SELECT tipo, fecha_resolucion
        FROM monitoreos
        WHERE numero_qr = ?
        AND empresa_id = ?
        AND resuelto = 1
        ORDER BY fecha_resolucion DESC
    """, (qr, current_user.empresa_id)).fetchall()

    conn.close()

    return jsonify([
        {
            "tipo": r["tipo"],
            "fecha": r["fecha_resolucion"]
        } for r in rows
    ])
@api_bp.route("/api/monitoreo", methods=["POST"])
@login_required
def nuevo_monitoreo():

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    qr = request.form.get("numero_qr")
    tipo = request.form.get("tipo")
    detalle = request.form.get("detalle")
    foto = request.files.get("foto")

    conn = get_db()

    silo = conn.execute(
        "SELECT estado_silo FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)).fetchone()
    
    if not silo or silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(ok=False, error="Silo extraído"), 400

    path = None
    if foto:
        os.makedirs("static/monitoreos", exist_ok=True)
        path = f"static/monitoreos/{datetime.now().timestamp()}_{foto.filename}"
        foto.save(path)

    conn.execute("""
        INSERT INTO monitoreos (
            empresa_id,
            numero_qr,
            fecha_evento,
            tipo,
            detalle,
            foto_evento
        )
        VALUES (?,?,?,?,?,?)
    """, (
            current_user.empresa_id,
            qr,
            ahora(),
            tipo,
            detalle,
            path
        ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)
@api_bp.route("/api/monitoreo/resolver", methods=["POST"])
@login_required
def resolver_monitoreo():

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    id_monitoreo = request.form.get("id_monitoreo")
    foto = request.files.get("foto")

    if not id_monitoreo:
        return jsonify(ok=False, error="ID faltante"), 400

    conn = get_db()

    path = None
    if foto:
        os.makedirs("static/monitoreos", exist_ok=True)
        path = f"static/monitoreos/resuelto_{datetime.now().timestamp()}_{foto.filename}"
        foto.save(path)

    conn.execute("""
        UPDATE monitoreos
        SET resuelto = 1,
            fecha_resolucion = ?,
            foto_resolucion = ?
        WHERE id = ? AND empresa_id = ?
    """, (
        ahora(),
        path,
        id_monitoreo,
        current_user.empresa_id
    ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)
# ======================
# EXTRACCIÓN
# ======================
@api_bp.route("/api/extraccion", methods=["POST"])
@login_required
def registrar_extraccion():

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    d = request.get_json(silent=True) or {}

    qr = d.get("numero_qr")
    estado = d.get("estado_silo")

    if not qr or not estado:
        return jsonify(ok=False, error="Datos incompletos"), 400

    conn = get_db()

    silo = conn.execute("""
        SELECT estado_silo
        FROM silos
        WHERE numero_qr=?
        AND empresa_id = ?
    """, (qr, current_user.empresa_id)).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400

    if silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(ok=False, error="El silo ya está extraído"), 400

    conn.execute("""
        UPDATE silos
        SET estado_silo = ?,
            fecha_extraccion = ?
        WHERE numero_qr = ?
        AND empresa_id = ?
    """, (
        estado,
        ahora(),
        qr,
        current_user.empresa_id
    ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)
