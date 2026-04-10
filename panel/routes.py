from flask import Blueprint, render_template, session, redirect, url_for, send_file
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font
from io import BytesIO

panel_bp = Blueprint("panel", __name__)

# ==========================================
# CONTEXTO EMPRESA UNIFICADO
# ==========================================
def empresa_actual():
    if current_user.es_superadmin:
        return session.get("empresa_contexto")
    return current_user.empresa_id


# ==========================================
# VER SILO
# ==========================================
@panel_bp.route("/silo/<qr>")
@login_required
def ver_silo(qr):

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()
    empresa_id = empresa_actual()

    silo = conn.execute("""
        SELECT * FROM silos
        WHERE numero_qr=? AND empresa_id=?
    """, (qr, empresa_id)).fetchone()

    if not silo:
        conn.close()
        return "Silo no encontrado", 404

    mercado = conn.execute("""
        SELECT
            CASE
                WHEN usar_manual = 1 THEN pizarra_manual
                ELSE pizarra_auto
            END AS pizarra,
            dolar
        FROM mercado
        WHERE cereal = ? AND empresa_id = ?
    """, (silo["cereal"], empresa_id)).fetchone()

    muestreos_raw_db = conn.execute("""
        SELECT m.id, m.fecha_muestreo
        FROM muestreos m
        WHERE m.numero_qr=? AND empresa_id=?
        ORDER BY m.fecha_muestreo DESC
    """, (qr, empresa_id)).fetchall()

    # Calcular dias en Python (compatible SQLite y PostgreSQL)
    muestreos_raw = []
    for m in muestreos_raw_db:
        fecha_val = m["fecha_muestreo"]
        dias = None
        if fecha_val:
            try:
                if isinstance(fecha_val, str):
                    fecha = None
                    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            fecha = datetime.strptime(fecha_val, fmt)
                            break
                        except ValueError:
                            continue
                else:
                    fecha = fecha_val
                if fecha:
                    dias = (datetime.now() - fecha).days
            except:
                dias = None
        muestreos_raw.append({"id": m["id"], "fecha_muestreo": fecha_val, "dias": dias})

    muestreos = []
    precio_estimado = None
    precio_usd = None
    factor_prom = None
    tas_usada = None
    analisis_pendiente = False

    for idx, m in enumerate(muestreos_raw):

        analisis = conn.execute("""
            SELECT seccion, grado, factor, tas, temperatura
            FROM analisis
            WHERE id_muestreo=? AND empresa_id=?
        """, (m["id"], empresa_id)).fetchall()

        por_seccion = {a["seccion"]: a for a in analisis}

        if idx == 0:
            if not analisis:
                analisis_pendiente = True
            else:
                factores = []
                tass = []

                for sec in ["punta", "medio", "final"]:
                    a = por_seccion.get(sec)
                    if a:
                        if a["factor"] is not None:
                            factores.append(a["factor"])
                        if a["tas"] is not None:
                            tass.append(a["tas"])

                if factores:
                    factor_prom = round(sum(factores) / len(factores), 4)

                if tass:
                    tas_usada = min(tass)

                if mercado and factor_prom and mercado["pizarra"] and mercado["dolar"]:
                    precio_estimado = round(
                        mercado["pizarra"] * factor_prom, 2
                    )
                    precio_usd = round(
                        precio_estimado / mercado["dolar"], 2
                    )

        muestreos.append({
            "id": m["id"],
            "fecha_muestreo": m["fecha_muestreo"],
            "dias": m["dias"],
            "punta": por_seccion.get("punta"),
            "medio": por_seccion.get("medio"),
            "final": por_seccion.get("final")
        })

    eventos_pendientes = conn.execute("""
        SELECT tipo, fecha_evento, foto_evento
        FROM monitoreos
        WHERE numero_qr = ? AND empresa_id=? AND resuelto = 0
        ORDER BY fecha_evento DESC
    """, (qr, empresa_id)).fetchall()

    eventos_resueltos = conn.execute("""
        SELECT tipo, fecha_resolucion, foto_resolucion
        FROM monitoreos
        WHERE numero_qr = ? AND empresa_id=? AND resuelto = 1
        ORDER BY fecha_resolucion DESC
    """, (qr, empresa_id)).fetchall()

    conn.close()

    return render_template(
        "silo.html",
        silo=silo,
        muestreos=muestreos,
        eventos_pendientes=eventos_pendientes,
        eventos_resueltos=eventos_resueltos,
        mercado=mercado,
        precio_estimado=precio_estimado,
        precio_usd=precio_usd,
        factor_prom=factor_prom,
        tas_usada=tas_usada,
        analisis_pendiente=analisis_pendiente,
        puede_calado=tiene_permiso("calado"),
        dif_matba=None
    )


# ==========================================
# VER MUESTREO
# ==========================================
@panel_bp.route("/muestreo/<int:id>")
@login_required
def ver_muestreo(id):

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()
    empresa_id = empresa_actual()

    muestreo = conn.execute("""
        SELECT m.*, s.numero_qr, s.cereal
        FROM muestreos m
        JOIN silos s
        ON s.numero_qr = m.numero_qr
        AND s.empresa_id = m.empresa_id
        WHERE m.id=? AND m.empresa_id=?
    """, (id, empresa_id)).fetchone()

    if not muestreo:
        conn.close()
        return "Muestreo no encontrado", 404

    analisis = conn.execute("""
        SELECT *
        FROM analisis
        WHERE id_muestreo=? AND empresa_id=?
        ORDER BY seccion
    """, (id, empresa_id)).fetchall()

    conn.close()

    return render_template(
        "muestreo.html",
        muestreo=muestreo,
        analisis=analisis,
        puede_laboratorio=tiene_permiso("laboratorio")
    )


# ==========================================
# PANEL
# ==========================================
@panel_bp.route("/")
@panel_bp.route("/panel")
@login_required
def panel():


    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()

    # 🔥 SUPERADMIN
    if current_user.es_superadmin:

        # Si no seleccionó empresa → mostrar selector
        if "empresa_contexto" not in session:

            empresas = conn.execute("""
                SELECT id, nombre
                FROM empresas
                WHERE activa = 1
                ORDER BY nombre
            """).fetchall()

            conn.close()

            return render_template(
                "seleccionar_empresa.html",
                empresas=empresas
            )

        # Si ya seleccionó
        empresa_id = session["empresa_contexto"]

    else:
        empresa_id = current_user.empresa_id

    silos = conn.execute("""
        SELECT *
        FROM silos
        WHERE empresa_id=?
        ORDER BY fecha_confeccion DESC
    """, (empresa_id,)).fetchall()

    registros = []

    for s in silos:

        ultimo = conn.execute("""
            SELECT id, fecha_muestreo
            FROM muestreos
            WHERE numero_qr=? AND empresa_id=?
            ORDER BY fecha_muestreo DESC
            LIMIT 1
        """, (s["numero_qr"], empresa_id)).fetchone()

        grado = None
        factor_prom = None
        tas_min = None
        fecha_estimada = None

        if ultimo:

            analisis = conn.execute("""
                SELECT grado, factor, tas
                FROM analisis
                WHERE id_muestreo=? AND empresa_id=?
            """, (ultimo["id"], empresa_id)).fetchall()

            grados = []
            factores = []
            tass = []

            for a in analisis:

                g = a["grado"]

                if g is not None:
                    if str(g).upper() == "F/E":
                        grados = ["F/E"]
                    else:
                        try:
                            grados.append(int(g))
                        except:
                            pass

                if a["factor"] is not None:
                    try:
                        factores.append(float(a["factor"]))
                    except:
                        pass

                if a["tas"] is not None:
                    try:
                        tass.append(int(a["tas"]))
                    except:
                        pass

            if "F/E" in grados:
                grado = "F/E"
            elif grados:
                grado = max(grados)

            if factores:
                factor_prom = round(sum(factores) / len(factores), 4)

            if tass:
                tas_min = min(tass)

            if tas_min is not None and ultimo["fecha_muestreo"]:

                fecha_str = ultimo["fecha_muestreo"]
                fecha_base = None

                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                    try:
                        fecha_base = datetime.strptime(fecha_str, fmt)
                        break
                    except ValueError:
                        continue

                if fecha_base:
                    fecha_estimada = (
                        fecha_base + timedelta(days=tas_min)
                    ).strftime("%Y-%m-%d")

        eventos = conn.execute("""
            SELECT COUNT(*) as cant
            FROM monitoreos
            WHERE numero_qr=? AND empresa_id=? AND resuelto=0
        """, (s["numero_qr"], empresa_id)).fetchone()["cant"]

        registros.append({
            **dict(s),
            "grado": grado,
            "factor": factor_prom,
            "tas_min": tas_min,
            "fecha_extraccion_estimada": fecha_estimada,
            "eventos": eventos
        })

    conn.close()

    # ==========================================
    # RESUMEN RÁPIDO PARA EL PANEL
    # ==========================================
    total_activos   = sum(1 for r in registros if r.get("estado_silo") != "Extraído")
    total_extraidos = sum(1 for r in registros if r.get("estado_silo") == "Extraído")
    con_alertas     = sum(1 for r in registros if r.get("tas_min") is not None and r["tas_min"] <= 30)
    con_eventos     = sum(1 for r in registros if r.get("eventos", 0) > 0)

    # Conteo por cereal (sólo activos)
    por_cereal = {}
    for r in registros:
        if r.get("estado_silo") != "Extraído":
            c = r.get("cereal", "Otro")
            por_cereal[c] = por_cereal.get(c, 0) + 1

    return render_template(
        "panel.html",
        registros=registros,
        puede_form=tiene_permiso("form"),
        puede_comercial=tiene_permiso("comercial"),
        puede_admin=tiene_permiso("admin"),
        resumen={
            "total_activos":   total_activos,
            "total_extraidos": total_extraidos,
            "con_alertas":     con_alertas,
            "con_eventos":     con_eventos,
            "por_cereal":      por_cereal,
        }
    )

# ==========================================
# FORM
# ==========================================
@panel_bp.route("/form")
@login_required
def form():

    if not tiene_permiso("form"):
        return acceso_denegado("form")

    return render_template(
        "form.html",
        puede_calado=tiene_permiso("calado")
    )
# ==========================================
# EXPORTAR EXCEL
# ==========================================
@panel_bp.route("/exportar_excel")
@login_required
def exportar_excel():

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()
    empresa_id = empresa_actual()

    silos = conn.execute("""
        SELECT s.*,
        (
            SELECT m.id
            FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
            AND m.empresa_id = s.empresa_id
            ORDER BY m.id DESC
            LIMIT 1
        ) AS ultimo_muestreo
        FROM silos s
        WHERE s.empresa_id=?
        ORDER BY s.cereal, s.numero_qr
    """, (empresa_id,)).fetchall()

    wb = Workbook()
    wb.remove(wb.active)

    cereales = ["Soja", "Maíz", "Trigo", "Girasol"]

    for cereal in cereales:
        ws = wb.create_sheet(title=cereal)

        ws["A1"] = "PRECIO BASE ($)"
        ws["A1"].font = Font(bold=True)
        ws["B1"] = 0

        headers = [
            "QR", "Fecha confección", "Estado silo", "Estado grano",
            "Metros", "Grado", "Factor", "TAS mín",
            "Fecha extracción estimada", "Precio estimado"
        ]

        ws.append([])
        ws.append(headers)

        for col in range(1, len(headers) + 1):
            ws.cell(row=3, column=col).font = Font(bold=True)

        row_excel = 4

        for s in silos:

            if s["cereal"] != cereal:
                continue

            grado = None
            factor = None
            tas_min = None
            fecha_estimada = None

            if s["ultimo_muestreo"]:

                analisis = conn.execute("""
                    SELECT grado, factor, tas
                    FROM analisis
                    WHERE id_muestreo=? AND empresa_id=?
                """, (s["ultimo_muestreo"], empresa_id)).fetchall()

                grados = []
                factores = []
                tass = []

                for a in analisis:
                    if a["grado"] is not None:
                        try:
                            grados.append(int(a["grado"]))
                        except:
                            pass

                    if a["factor"] is not None:
                        try:
                            factores.append(float(a["factor"]))
                        except:
                            pass

                    if a["tas"] is not None:
                        try:
                            tass.append(int(a["tas"]))
                        except:
                            pass

                if grados:
                    grado = max(grados)

                if factores:
                    factor = round(sum(factores) / len(factores), 4)

                if tass:
                    tas_min = min(tass)

                    row_fecha = conn.execute("""
                        SELECT fecha_muestreo
                        FROM muestreos
                        WHERE id=? AND empresa_id=?
                    """, (s["ultimo_muestreo"], empresa_id)).fetchone()

                    if row_fecha and row_fecha["fecha_muestreo"]:
                        try:
                            fm = datetime.strptime(
                                row_fecha["fecha_muestreo"],
                                "%Y-%m-%d %H:%M"
                            )
                            fecha_estimada = fm + timedelta(days=int(tas_min))
                        except:
                            pass

            ws.cell(row=row_excel, column=1, value=s["numero_qr"])
            ws.cell(row=row_excel, column=3, value=s["estado_silo"])
            ws.cell(row=row_excel, column=4, value=s["estado_grano"])
            ws.cell(row=row_excel, column=5, value=s["metros"])
            ws.cell(row=row_excel, column=6, value=grado)
            ws.cell(row=row_excel, column=7, value=factor)
            ws.cell(row=row_excel, column=8, value=tas_min)
            ws.cell(row=row_excel, column=9, value=fecha_estimada)
            ws.cell(row=row_excel, column=10, value=f"=B1*G{row_excel}")

            row_excel += 1

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="silos_comercial.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==========================================
# SELECCIONAR EMPRESA
# ==========================================
@panel_bp.route("/seleccionar_empresa/<int:id>")
@login_required
def seleccionar_empresa(id):

    if not current_user.es_superadmin:
        return "No autorizado", 403

    session["empresa_contexto"] = id
    return redirect(url_for("panel.panel"))
# ==========================================
# CAMBIAR EMPRESA (SUPERADMIN)
# ==========================================
@panel_bp.route("/cambiar_empresa")
@login_required
def cambiar_empresa():

    if not current_user.es_superadmin:
        return "No autorizado", 403

    session.pop("empresa_contexto", None)
    return redirect(url_for("panel.panel"))