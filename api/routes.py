from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso
from datetime import datetime
import os
import cloudinary
import cloudinary.uploader
from calculos import calcular_comercial
from flask import request, jsonify
from utils.auditoria import registrar_auditoria

# Configurar Cloudinary
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

api_bp = Blueprint("api", __name__)

def ahora():
    from utils.fechas import ahora as _ahora
    return _ahora()

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

    # Si está en extracción o extraído, traer kg extraídos
    kg_extraidos = 0
    fecha_extraccion = None
    if s and s["estado_silo"] in ("En extracción", "Extraído"):
        try:
            row_kg = conn.execute(
                "SELECT COALESCE(SUM(kg), 0) AS total FROM vaciado WHERE numero_qr=? AND empresa_id=?",
                (qr, current_user.empresa_id)
            ).fetchone()
            kg_extraidos = float(row_kg["total"] or 0)
        except Exception:
            try:
                conn.rollback()
            except:
                pass

    # Traer fecha_extraccion para silos Extraídos
    if s and s["estado_silo"] == "Extraído":
        try:
            row_fe = conn.execute(
                "SELECT fecha_extraccion FROM silos WHERE numero_qr=? AND empresa_id=?",
                (qr, current_user.empresa_id)
            ).fetchone()
            fecha_extraccion = row_fe["fecha_extraccion"] if row_fe else None
        except Exception:
            try:
                conn.rollback()
            except:
                pass

    conn.close()

    if not s:
        return jsonify(existe=False)

    return jsonify(
        existe=True,
        cereal=s["cereal"],
        fecha_confeccion=s["fecha_confeccion"],
        estado_silo=s["estado_silo"],
        ultimo_calado=s["ultimo_calado"],
        kg_extraidos=kg_extraidos,
        fecha_extraccion=fecha_extraccion,
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

    conn.commit()
    conn.close()

    return jsonify(ok=True)

# ======================

# ======================
# EXTRACCIÓN — iniciar vaciado
# ======================
@api_bp.route("/api/extraccion", methods=["POST"])
@login_required
def registrar_extraccion():

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    d = request.get_json(silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
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

    if silo["estado_silo"] == "En extracción":
        conn.close()
        return jsonify(ok=False, error="El silo ya está en extracción"), 400

    conn.execute("""
        UPDATE silos
        SET estado_silo = 'En extracción'
        WHERE numero_qr = ?
        AND empresa_id = ?
    """, (qr, current_user.empresa_id))

    registrar_auditoria(
        conn, current_user.id, current_user.empresa_id,
        accion="inicio_extraccion",
        detalle=f"Silo {qr} marcado como En extracción",
        numero_qr=qr
    )

    conn.commit()
    conn.close()

    return jsonify(ok=True)


# ======================
# EXTRACCIÓN — cerrar (marcar como Extraído)
# ======================
@api_bp.route("/api/cerrar_extraccion", methods=["POST"])
@login_required
def cerrar_extraccion():

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    d = request.get_json(silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
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

    # ── Comparativo llenado vs vaciado ──────────────────────────────
    # KG llenado
    llenado_rows = conn.execute(
        "SELECT kg, factor FROM llenado WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchall()
    kg_llenado = sum(float(r["kg"] or 0) for r in llenado_rows)
    # factor ponderado llenado
    kg_sum_ll = sum(float(r["kg"] or 0) for r in llenado_rows if r["factor"] is not None)
    factor_ll = round(
        sum(float(r["factor"]) * float(r["kg"] or 0) for r in llenado_rows if r["factor"] is not None)
        / kg_sum_ll, 4
    ) if kg_sum_ll > 0 else None

    # KG vaciado (solo camionadas completas con kg cargado)
    vaciado_rows = conn.execute(
        "SELECT kg, factor FROM vaciado WHERE numero_qr=? AND empresa_id=? AND kg IS NOT NULL",
        (qr, current_user.empresa_id)
    ).fetchall()
    kg_vaciado = sum(float(r["kg"] or 0) for r in vaciado_rows)
    # factor ponderado vaciado
    kg_sum_vac = sum(float(r["kg"] or 0) for r in vaciado_rows if r["factor"] is not None)
    factor_vac = round(
        sum(float(r["factor"]) * float(r["kg"] or 0) for r in vaciado_rows if r["factor"] is not None)
        / kg_sum_vac, 4
    ) if kg_sum_vac > 0 else None

    dif_kg = round(kg_vaciado - kg_llenado, 0) if kg_llenado > 0 else None
    dif_factor = round((factor_vac - factor_ll) * 100, 3) if (factor_vac and factor_ll) else None

    conn.execute("""
        UPDATE silos
        SET estado_silo = 'Extraído',
            fecha_extraccion = ?
        WHERE numero_qr = ?
        AND empresa_id = ?
    """, (ahora(), qr, current_user.empresa_id))

    registrar_auditoria(
        conn, current_user.id, current_user.empresa_id,
        accion="cierre_extraccion",
        detalle=f"Silo {qr} — Extraído | Llenado: {kg_llenado:,.0f} kg / Vaciado: {kg_vaciado:,.0f} kg | Dif: {dif_kg:+,.0f} kg",
        numero_qr=qr
    )

    conn.commit()
    conn.close()

    return jsonify(
        ok=True,
        comparativo=dict(
            kg_llenado=kg_llenado,
            kg_vaciado=kg_vaciado,
            dif_kg=dif_kg,
            factor_llenado=factor_ll,
            factor_vaciado=factor_vac,
            dif_factor=dif_factor,
        )
    )


# ======================
# VACIADO — registrar camionada (desde form: solo patente)
# ======================
@api_bp.route("/api/vaciado", methods=["POST"])
@login_required
def registrar_camionada():
    if not tiene_permiso("form"):
        return jsonify(ok=False), 403
    d = request.get_json(silent=True) or {}
    qr = d.get("numero_qr")
    patente = d.get("patente", "").strip()
    if not qr or not patente:
        return jsonify(ok=False, error="Faltan datos obligatorios (QR y patente)"), 400
    conn = get_db()
    silo = conn.execute("SELECT estado_silo FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)).fetchone()
    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo inexistente"), 400
    if silo["estado_silo"] != "En extracción":
        conn.close()
        return jsonify(ok=False, error="El silo no está en extracción"), 400
    row_count = conn.execute("SELECT COUNT(*) as cant FROM vaciado WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)).fetchone()
    nro_camion = (row_count["cant"] if row_count else 0) + 1
    conn.execute("""
        INSERT INTO vaciado (numero_qr, empresa_id, fecha, nro_camion, patente,
             kg, humedad, factor, tas, insectos, destino, sub_destino, obs)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (qr, current_user.empresa_id, ahora(), str(nro_camion), patente.upper(),
          None, None, None, None, 0, None, None, None))
    registrar_auditoria(
        conn, current_user.id, current_user.empresa_id,
        accion="camionada_vaciado",
        detalle=f"Silo {qr} — camionada #{nro_camion} (patente: {patente.upper()})",
        numero_qr=qr
    )

    conn.commit()
    conn.close()
    return jsonify(ok=True, nro_camion=nro_camion)


# ======================
# VACIADO — completar/editar camionada (laboratorio)
# ======================
@api_bp.route("/api/vaciado/<int:id_camionada>", methods=["PUT"])
@login_required
def completar_camionada(id_camionada):
    if not tiene_permiso("laboratorio") and not tiene_permiso("calado"):
        return jsonify(ok=False, error="No autorizado"), 403
    d = request.get_json(force=True, silent=True) or {}
    def to_float(x):
        try:
            return float(x) if x not in (None, "", "null") else None
        except:
            return None
    kg = to_float(d.get("kg"))
    if not kg or kg <= 0:
        return jsonify(ok=False, error="Ingresa los KG"), 400
    destino = d.get("destino")
    if destino not in ("puerto", "planta"):
        return jsonify(ok=False, error="Selecciona destino"), 400
    conn = get_db()
    cam = conn.execute("SELECT id, numero_qr, nro_camion, patente FROM vaciado WHERE id=? AND empresa_id=?",
        (id_camionada, current_user.empresa_id)).fetchone()
    if not cam:
        conn.close()
        return jsonify(ok=False, error="Camionada no encontrada"), 404
    silo = conn.execute("SELECT cereal FROM silos WHERE numero_qr=? AND empresa_id=?",
        (cam["numero_qr"], current_user.empresa_id)).fetchone()
    datos = {
        "temperatura": to_float(d.get("temperatura")),
        "humedad": to_float(d.get("humedad")),
        "danados": to_float(d.get("danados")),
        "quebrados": to_float(d.get("quebrados")),
        "materia_extrana": to_float(d.get("materia_extrana")),
        "olor": to_float(d.get("olor")) or 0,
        "moho": to_float(d.get("moho")) or 0,
        "chamico": to_float(d.get("chamico")),
        "insectos": 1 if d.get("insectos") else 0,
        "ph": to_float(d.get("ph")),
        "materia_grasa": to_float(d.get("materia_grasa")),
        "acidez": to_float(d.get("acidez")),
        "proteinas": to_float(d.get("proteinas")),
        "granos_picados": to_float(d.get("granos_picados")),
    }
    datos_calc = {k: (v if v is not None else 0) for k, v in datos.items()}
    from calculos import calcular_comercial
    res = calcular_comercial(silo["cereal"], datos_calc)
    conn.execute("""
        UPDATE vaciado SET
            kg=?, temperatura=?, humedad=?, materia_extrana=?,
            danados=?, quebrados=?, ph=?, chamico=?,
            materia_grasa=?, acidez=?, proteinas=?, granos_picados=?,
            olor=?, moho=?, insectos=?, factor=?, tas=?, destino=?, obs=?
        WHERE id=? AND empresa_id=?
    """, (kg, datos["temperatura"], datos["humedad"], datos["materia_extrana"],
          datos["danados"], datos["quebrados"], datos["ph"], datos["chamico"],
          datos["materia_grasa"], datos["acidez"], datos["proteinas"], datos["granos_picados"],
          datos["olor"], datos["moho"], datos["insectos"],
          res.get("factor"), res.get("tas"), destino, d.get("obs"),
          id_camionada, current_user.empresa_id))

    registrar_auditoria(
        conn, current_user.id, current_user.empresa_id,
        accion="completar_camionada",
        detalle=f"Silo {cam['numero_qr']} — camionada #{cam['nro_camion']} (patente: {cam['patente'] or 'S/D'}) completada — {destino.upper()} | {kg} kg | factor {res.get('factor','?')}",
        numero_qr=cam["numero_qr"]
    )

    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# VACIADO — listar camionadas (para form.html)
# ======================
@api_bp.route("/api/camionadas/<qr>")
@login_required
def listar_camionadas(qr):
    if not tiene_permiso("form"):
        return jsonify([])
    conn = get_db()
    rows = conn.execute("""
        SELECT id, nro_camion, patente, fecha, kg
        FROM vaciado WHERE numero_qr=? AND empresa_id=?
        ORDER BY nro_camion ASC
    """, (qr, current_user.empresa_id)).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"nro_camion":r["nro_camion"],
        "patente":r["patente"],"fecha":r["fecha"],"kg":r["kg"]} for r in rows])


# ======================
# VACIADO — eliminar camionada
# ======================
@api_bp.route("/api/vaciado/<int:id_camionada>", methods=["DELETE"])
@login_required
def eliminar_camionada(id_camionada):

    if not tiene_permiso("form"):
        return jsonify(ok=False), 403

    conn = get_db()

    row = conn.execute("""
        SELECT id, numero_qr FROM vaciado
        WHERE id=? AND empresa_id=?
    """, (id_camionada, current_user.empresa_id)).fetchone()

    if not row:
        conn.close()
        return jsonify(ok=False, error="Camionada no encontrada"), 404

    conn.execute("DELETE FROM vaciado WHERE id=?", (id_camionada,))

    registrar_auditoria(
        conn, current_user.id, current_user.empresa_id,
        accion="eliminar_camionada",
        detalle=f"Camionada #{id_camionada} eliminada (silo {row['numero_qr']})",
        numero_qr=row["numero_qr"]
    )

    conn.commit()
    conn.close()

    return jsonify(ok=True)

# ======================
# EDITAR SILO (admin)
# ======================
@api_bp.route("/api/editar_silo", methods=["POST"])
@login_required
def editar_silo():

    if current_user.rol not in ("admin_empresa",) and not current_user.es_superadmin:
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
        return jsonify(ok=False, error="QR faltante"), 400

    conn = get_db()

    silo = conn.execute(
        "SELECT numero_qr FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo no encontrado"), 404

    conn.execute("""
        UPDATE silos SET
            cereal = ?,
            estado_grano = ?,
            fecha_confeccion = ?,
            metros = ?
        WHERE numero_qr = ? AND empresa_id = ?
    """, (
        d.get("cereal"),
        d.get("estado_grano"),
        d.get("fecha_confeccion"),
        d.get("metros"),
        qr,
        current_user.empresa_id
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# BORRAR SILO (admin)
# ======================
@api_bp.route("/api/borrar_silo", methods=["POST"])
@login_required
def borrar_silo():

    if current_user.rol not in ("admin_empresa",) and not current_user.es_superadmin:
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    qr = d.get("numero_qr")

    if not qr:
        return jsonify(ok=False, error="QR faltante"), 400

    conn = get_db()

    silo = conn.execute(
        "SELECT numero_qr FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo no encontrado"), 404

    # Borrar datos relacionados primero
    conn.execute("DELETE FROM muestreos WHERE numero_qr=? AND empresa_id=?", (qr, current_user.empresa_id))
    conn.execute("DELETE FROM monitoreos WHERE numero_qr=? AND empresa_id=?", (qr, current_user.empresa_id))
    conn.execute("DELETE FROM llenado WHERE numero_qr=? AND empresa_id=?", (qr, current_user.empresa_id))
    conn.execute("DELETE FROM silos WHERE numero_qr=? AND empresa_id=?", (qr, current_user.empresa_id))

    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# ACTUALIZAR GPS (admin)
# ======================
@api_bp.route("/api/actualizar_gps", methods=["POST"])
@login_required
def actualizar_gps():

    if current_user.rol not in ("admin_empresa",) and not current_user.es_superadmin:
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    qr  = d.get("numero_qr")
    lat = d.get("lat")
    lon = d.get("lon")

    if not qr or lat is None or lon is None:
        return jsonify(ok=False, error="Datos incompletos"), 400

    conn = get_db()

    silo = conn.execute(
        "SELECT numero_qr FROM silos WHERE numero_qr=? AND empresa_id=?",
        (qr, current_user.empresa_id)
    ).fetchone()

    if not silo:
        conn.close()
        return jsonify(ok=False, error="Silo no encontrado"), 404

    conn.execute(
        "UPDATE silos SET lat=?, lon=? WHERE numero_qr=? AND empresa_id=?",
        (lat, lon, qr, current_user.empresa_id)
    )
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# LLENADO — EDITAR
# ======================
@api_bp.route("/api/llenado/<int:id>", methods=["PUT"])
@login_required
def editar_carga_llenado(id):

    if not tiene_permiso("form"):
        return jsonify(ok=False, error="No autorizado"), 403

    d = request.get_json(force=True, silent=True) or {}
    conn = get_db()

    carga = conn.execute(
        "SELECT numero_qr FROM llenado WHERE id=? AND empresa_id=?",
        (id, current_user.empresa_id)
    ).fetchone()

    if not carga:
        conn.close()
        return jsonify(ok=False, error="Carga no encontrada"), 404

    silo = conn.execute(
        "SELECT cereal FROM silos WHERE numero_qr=? AND empresa_id=?",
        (carga["numero_qr"], current_user.empresa_id)
    ).fetchone()

    def to_float(x):
        try:
            return float(x) if x not in (None, "", "null") else None
        except:
            return None

    datos = {
        "temperatura":     to_float(d.get("temperatura")),
        "humedad":         to_float(d.get("humedad")),
        "danados":         to_float(d.get("danados")),
        "quebrados":       to_float(d.get("quebrados")),
        "materia_extrana": to_float(d.get("materia_extrana")),
        "olor":            to_float(d.get("olor")) or 0,
        "moho":            to_float(d.get("moho")) or 0,
        "chamico":         to_float(d.get("chamico")),
        "insectos":        1 if d.get("insectos") else 0,
        "materia_grasa":   to_float(d.get("materia_grasa")),
        "acidez":          to_float(d.get("acidez")),
        "proteinas":       to_float(d.get("proteinas")),
        "granos_picados":  to_float(d.get("granos_picados")),
    }
    kg = to_float(d.get("kg")) or 0

    res = calcular_comercial(silo["cereal"], datos)

    conn.execute("""
        UPDATE llenado SET
            kg=?, temperatura=?, humedad=?, danados=?, quebrados=?,
            materia_extrana=?, olor=?, moho=?, insectos=?, chamico=?,
            grado=?, factor=?, tas=?
        WHERE id=? AND empresa_id=?
    """, (
        kg, datos["temperatura"], datos["humedad"], datos["danados"], datos["quebrados"],
        datos["materia_extrana"], datos["olor"], datos["moho"], datos["insectos"], datos["chamico"],
        str(res.get("grado") or "F/E"), res.get("factor"), res.get("tas"),
        id, current_user.empresa_id
    ))

    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ======================
# LLENADO — ELIMINAR
# ======================
@api_bp.route("/api/llenado/<int:id>", methods=["DELETE"])
@login_required
def eliminar_carga_llenado(id):

    if not tiene_permiso("form"):
        return jsonify(ok=False, error="No autorizado"), 403

    conn = get_db()

    carga = conn.execute(
        "SELECT id FROM llenado WHERE id=? AND empresa_id=?",
        (id, current_user.empresa_id)
    ).fetchone()

    if not carga:
        conn.close()
        return jsonify(ok=False, error="Carga no encontrada"), 404

    conn.execute("DELETE FROM llenado WHERE id=? AND empresa_id=?",
                 (id, current_user.empresa_id))
    conn.commit()
    conn.close()
    return jsonify(ok=True)
