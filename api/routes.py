from flask import Blueprint, request, jsonify
from utils.auditoria import registrar_auditoria
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso
from datetime import datetime
import os
import cloudinary
import cloudinary.uploader
from calculos import calcular_comercial
from flask import request, jsonify
from utils.fechas import ahora

# Configurar Cloudinary
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

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
    
    registrar_auditoria(
        conn,
        current_user.id,
        current_user.empresa_id,
        "registro_silo",
        f"Cereal: {d.get('cereal')}, {d.get('metros')}m, Estado: {d.get('estado_grano')}",
        d.get("numero_qr")
)
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

    conn.execute("""
        INSERT INTO muestreos (numero_qr, empresa_id, fecha_muestreo)
        VALUES (?,?,?)
    """, (
        qr,
        current_user.empresa_id,
        ahora().strftime("%Y-%m-%d %H:%M")
    ))
    conn.commit()

    id_row = conn.execute("""
        SELECT id FROM muestreos
        WHERE numero_qr=? AND empresa_id=?
        ORDER BY id DESC LIMIT 1
    """, (qr, current_user.empresa_id)).fetchone()
    mid = id_row["id"] if id_row else None
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

    existente = conn.execute("""
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
    grado = res["grado"] if res["grado"] else "F/E"

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
        grado,
        res["factor"],
        res["tas"]
    )

    if existente:
        conn.execute("""
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
            grado,
            res["factor"],
            res["tas"],
            d["id_muestreo"],
            d["seccion"],
            current_user.empresa_id
        ))
    else:
        conn.execute("""
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
            grado,
            res["factor"],
            res["tas"]
        ))
    registrar_auditoria(conn, current_user.id, current_user.empresa_id,
        "analisis", f"Sección: {d.get('seccion')}, Grado: {grado}", d.get("id_muestreo") and str(d.get("id_muestreo")))
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
        try:
            resultado = cloudinary.uploader.upload(
                foto,
                folder="silobolsas/monitoreos",
                resource_type="image"
            )
            path = resultado["secure_url"]
        except Exception as e:
            path = None

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

    registrar_auditoria(conn, current_user.id, current_user.empresa_id,
        "evento_monitoreo", f"Tipo: {tipo}", qr)
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
        try:
            resultado = cloudinary.uploader.upload(
                foto,
                folder="silobolsas/resueltos",
                resource_type="image"
            )
            path = resultado["secure_url"]
        except Exception as e:
            path = None

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
# LLENADO — NUEVA CARGA
# ======================
@api_bp.route("/api/llenado", methods=["POST"])
@login_required
def nueva_carga_llenado():

    if not tiene_permiso("form"):
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
        return jsonify(ok=False, error="QR faltante"), 400

    conn = get_db()

    silo = conn.execute(
        "SELECT estado_silo, cereal FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchone()

    if not silo or silo["estado_silo"] == "Extraído":
        conn.close()
        return jsonify(ok=False, error="Silo no válido"), 400

    def to_float(x):
        try:
            return float(x) if x not in (None, "", "null") else None
        except:
            return None

    datos = {
        "temperatura": to_float(d.get("temperatura")),
        "humedad":     to_float(d.get("humedad")),
        "danados":     to_float(d.get("danados")),
        "quebrados":   to_float(d.get("quebrados")),
        "materia_extrana": to_float(d.get("materia_extrana")),
        "materia_grasa": to_float(d.get("materia_grasa")),
        "acidez": to_float(d.get("acidez")),
        "olor":        to_float(d.get("olor")) or 0,
        "moho":        to_float(d.get("moho")) or 0,
        "chamico":     to_float(d.get("chamico")),
        "insectos":    1 if d.get("insectos") else 0,
    }
    kg = to_float(d.get("kg")) or 0

    from calculos import calcular_comercial
    res = calcular_comercial(silo["cereal"], datos)

    conn.execute("""
        INSERT INTO llenado (
            numero_qr, empresa_id, fecha, kg,
            temperatura, humedad, danados, quebrados,
            materia_extrana, olor, moho, insectos, chamico,
            grado, factor, tas
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        qr, current_user.empresa_id, ahora(), kg,
        datos["temperatura"], datos["humedad"], datos["danados"], datos["quebrados"],
        datos["materia_extrana"], datos["olor"], datos["moho"], datos["insectos"], datos["chamico"],
        str(res.get("grado") or "F/E"), res.get("factor"), res.get("tas")
    ))

    registrar_auditoria(conn, current_user.id, current_user.empresa_id,
        "llenado", f"{kg} kg", qr)
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
