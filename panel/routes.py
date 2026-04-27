from flask import Blueprint, render_template, session, redirect, url_for, send_file
from utils.auditoria import registrar_auditoria
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font
from io import BytesIO

panel_bp = Blueprint("panel", __name__)

def empresa_actual():
    if current_user.es_superadmin:
        return session.get("empresa_contexto")
    return current_user.empresa_id


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

    try:
        cargas_raw = conn.execute("""
            SELECT id, fecha, kg, temperatura, humedad, danados,
                quebrados, materia_extrana, olor, moho, insectos,
                chamico, grado, factor, tas
            FROM llenado
            WHERE numero_qr=? AND empresa_id=?
            ORDER BY fecha DESC
        """, (qr, empresa_id)).fetchall()

        cargas_llenado = [dict(x) for x in cargas_raw]

        kg_total = sum(float(c["kg"] or 0) for c in cargas_llenado)

    except Exception:
        conn.rollback()
        cargas_llenado = []
        kg_total = 0

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
        dif_matba=None,
        cargas_llenado=cargas_llenado,
        kg_total=kg_total
    )


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


@panel_bp.route("/")
@panel_bp.route("/panel")
@login_required
def panel():

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()

    if current_user.es_superadmin:

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

        try:
            kg_row = conn.execute("""
                SELECT COALESCE(SUM(kg), 0) as total
                FROM llenado
                WHERE numero_qr=? AND empresa_id=?
            """, (s["numero_qr"], empresa_id)).fetchone()
            kg_total = int(kg_row["total"]) if kg_row else 0
        except Exception:
            conn.rollback()
            kg_total = 0

        # Si no hay calado, usar datos ponderados del llenado
        fuente = "calado"
        if grado is None and factor_prom is None and tas_min is None:
            try:
                cargas = conn.execute("""
                    SELECT kg, factor, tas, fecha
                    FROM llenado
                    WHERE numero_qr=? AND empresa_id=?
                    ORDER BY fecha DESC
                """, (s["numero_qr"], empresa_id)).fetchall()

                if cargas:
                    fuente = "llenado"
                    cargas_con_factor = [c for c in cargas if c["factor"] is not None]
                    if cargas_con_factor:
                        kg_total_pond = sum(float(c["kg"] or 0) for c in cargas_con_factor)
                        if kg_total_pond > 0:
                            factor_pond = sum(
                                float(c["factor"]) * float(c["kg"] or 0)
                                for c in cargas_con_factor
                            ) / kg_total_pond
                            factor_prom = round(factor_pond, 4)
                        else:
                            factores = [float(c["factor"]) for c in cargas_con_factor]
                            factor_prom = round(sum(factores) / len(factores), 4)

                    tas_vals = [int(c["tas"]) for c in cargas if c["tas"] is not None]
                    if tas_vals:
                        tas_min = min(tas_vals)

                    if tas_min and cargas[0]["fecha"]:
                        fecha_str = cargas[0]["fecha"]
                        try:
                            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                                try:
                                    fecha_base = datetime.strptime(fecha_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            fecha_estimada = (
                                fecha_base + timedelta(days=tas_min)
                            ).strftime("%Y-%m-%d")
                        except:
                            pass
            except Exception:
                pass

        registros.append({
            **dict(s),
            "grado": grado,
            "factor": factor_prom,
            "tas_min": tas_min,
            "fecha_extraccion_estimada": fecha_estimada,
            "eventos": eventos,
            "kg_total": kg_total,
            "fuente_calidad": fuente
        })

    conn.close()

    total_activos   = sum(1 for r in registros if r.get("estado_silo") != "Extraído")
    total_extraidos = sum(1 for r in registros if r.get("estado_silo") == "Extraído")
    con_alertas     = sum(1 for r in registros if r.get("tas_min") is not None and r["tas_min"] <= 30)
    con_eventos     = sum(1 for r in registros if r.get("eventos", 0) > 0)

    por_cereal = {}
    for r in registros:
        if r.get("estado_silo") != "Extraído":
            c = r.get("cereal", "Otro")
            por_cereal[c] = por_cereal.get(c, 0) + 1
    # ==========================================
    # RESUMEN COMERCIAL POR CEREAL
    # ==========================================
    conn2 = get_db()
    resumen_comercial = {}

    for cereal in por_cereal.keys():
        mercado = conn2.execute("""
            SELECT
                CASE WHEN usar_manual = 1 THEN pizarra_manual
                     ELSE pizarra_auto
                END AS pizarra,
                dolar
            FROM mercado
            WHERE cereal = ? AND empresa_id = ?
        """, (cereal, empresa_id)).fetchone()

        silos_cereal = [
            r for r in registros
            if r.get("cereal") == cereal
            and r.get("estado_silo") != "Extraído"
            and r.get("factor") is not None
        ]

        if not silos_cereal:
            continue

        kg_con_factor = []
        for r in silos_cereal:
            kg = r.get("kg_total") or 0
            if kg == 0:
                kg = (r.get("metros") or 0) * 1000
            if kg > 0:
                kg_con_factor.append((kg, r["factor"]))

        if not kg_con_factor:
            continue

        kg_total_cereal = sum(k for k, _ in kg_con_factor)
        factor_pond = sum(k * f for k, f in kg_con_factor) / kg_total_cereal if kg_total_cereal > 0 else None

        precio_ars = None
        precio_usd = None
        if factor_pond and mercado and mercado["pizarra"] and mercado["dolar"]:
            precio_ars = round(mercado["pizarra"] * factor_pond, 2)
            precio_usd = round(precio_ars / mercado["dolar"], 2)

        resumen_comercial[cereal] = {
            "silos":       len(silos_cereal),
            "kg_total":    int(kg_total_cereal),
            "factor_pond": round(factor_pond * 100, 2) if factor_pond else None,
            "pizarra":     mercado["pizarra"] if mercado else None,
            "precio_ars":  precio_ars,
            "precio_usd":  precio_usd,
        }

    conn2.close()

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
        },
        resumen_comercial=resumen_comercial
    )


@panel_bp.route("/form")
@login_required
def form():

    if not tiene_permiso("form"):
        return acceso_denegado("form")

    return render_template(
        "form.html",
        puede_calado=tiene_permiso("calado")
    )


@panel_bp.route("/exportar_excel")
@login_required
def exportar_excel():

    if not tiene_permiso("panel"):
        return acceso_denegado("panel")

    conn = get_db()
    empresa_id = empresa_actual()

    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, PatternFill, Border, Side,
        Alignment
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import CellIsRule
    from io import BytesIO

    # =====================================================
    # ESTILOS
    # =====================================================
    VERDE = "1B5E20"
    VERDE2 = "43A047"
    VERDE3 = "E8F5E9"
    AZUL = "1565C0"
    GRIS = "F5F5F5"
    BLANCO = "FFFFFF"
    ROJO = "C62828"
    AMARILLO = "FFF9C4"

    thin = Side(style="thin", color="CCCCCC")

    def borde():
        return Border(left=thin, right=thin, top=thin, bottom=thin)

    def fill(c):
        return PatternFill("solid", start_color=c, end_color=c)

    def center():
        return Alignment(horizontal="center", vertical="center", wrap_text=True)

    def estilo_titulo(celda, color=VERDE):
        celda.font = Font(bold=True, color=BLANCO, size=14)
        celda.fill = fill(color)
        celda.alignment = center()

    def estilo_header(celda, color=VERDE2):
        celda.font = Font(bold=True, color=BLANCO)
        celda.fill = fill(color)
        celda.alignment = center()
        celda.border = borde()

    def estilo_body(celda, color=None):
        if color:
            celda.fill = fill(color)
        celda.border = borde()
        celda.alignment = center()

    # =====================================================
    # DATOS BASE
    # =====================================================
    silos = conn.execute("""
        SELECT s.*,
        (
            SELECT m.id
            FROM muestreos m
            WHERE m.numero_qr = s.numero_qr
            AND m.empresa_id = s.empresa_id
            ORDER BY m.id DESC
            LIMIT 1
        ) ultimo_muestreo
        FROM silos s
        WHERE s.empresa_id=?
        ORDER BY s.cereal, s.numero_qr
    """, (empresa_id,)).fetchall()

    mercado_rows = conn.execute("""
        SELECT cereal,
        CASE
            WHEN usar_manual=1 THEN pizarra_manual
            ELSE pizarra_auto
        END pizarra,
        dolar
        FROM mercado
        WHERE empresa_id=?
    """, (empresa_id,)).fetchall()

    mercado = {r["cereal"]: r for r in mercado_rows}

    try:
        matba_rows = conn.execute("""
            SELECT cereal, posicion, mes, precio
            FROM matba
            WHERE empresa_id=?
            ORDER BY cereal, posicion
        """, (empresa_id,)).fetchall()
    except:
        matba_rows = []

    wb = Workbook()
    wb.remove(wb.active)

    cereales = ["Soja", "Maíz", "Trigo", "Girasol", "Sorgo"]

    # =====================================================
    # HOJA RESUMEN
    # =====================================================
    ws = wb.create_sheet("Resumen", 0)

    ws.merge_cells("A1:H1")
    ws["A1"] = "RESUMEN GENERAL SILO BOLSAS"
    estilo_titulo(ws["A1"])

    ws.merge_cells("A2:H2")
    ws["A2"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].alignment = center()

    headers = [
        "Cereal", "Silos Activos", "Silos Extraídos",
        "KG Est.", "Pizarra", "USD", "Valor ARS/TN", "Valor USD/TN"
    ]

    row = 4
    for c, h in enumerate(headers, 1):
        ws.cell(row=row, column=c, value=h)
        estilo_header(ws.cell(row=row, column=c))

    row += 1

    for cereal in cereales:

        silos_cereal = [x for x in silos if x["cereal"] == cereal]

        if not silos_cereal:
            continue

        activos = [x for x in silos_cereal if x["estado_silo"] != "Extraído"]
        extraidos = [x for x in silos_cereal if x["estado_silo"] == "Extraído"]

        kg_total = 0
        for s in activos:
            try:
                kg = conn.execute("""
                    SELECT COALESCE(SUM(kg),0) total
                    FROM llenado
                    WHERE numero_qr=? AND empresa_id=?
                """, (s["numero_qr"], empresa_id)).fetchone()["total"]
            except:
                kg = 0

            if not kg:
                kg = (s["metros"] or 0) * 1000

            kg_total += kg

        merc = mercado.get(cereal)

        pizarra = merc["pizarra"] if merc else None
        dolar = merc["dolar"] if merc else None

        precio_usd = round(pizarra / dolar, 2) if pizarra and dolar else None

        vals = [
            cereal,
            len(activos),
            len(extraidos),
            int(kg_total),
            pizarra,
            dolar,
            pizarra,
            precio_usd
        ]

        for c, v in enumerate(vals, 1):
            ws.cell(row=row, column=c, value=v)
            estilo_body(ws.cell(row=row, column=c),
                        GRIS if row % 2 == 0 else None)

        row += 1

    # =====================================================
    # HOJAS POR CEREAL
    # =====================================================
    for cereal in cereales:

        silos_cereal = [x for x in silos if x["cereal"] == cereal]

        if not silos_cereal:
            continue

        ws = wb.create_sheet(cereal)

        ws.merge_cells("A1:L1")
        ws["A1"] = f"{cereal.upper()} - SILOS"
        estilo_titulo(ws["A1"])

        headers = [
            "QR",
            "Fecha Confección",
            "Estado Silo",
            "Estado Grano",
            "Metros",
            "KG",
            "Grado",
            "Factor %",
            "TAS",
            "Fecha Extracción Est.",
            "Precio ARS",
            "Precio USD"
        ]

        for c, h in enumerate(headers, 1):
            ws.cell(row=3, column=c, value=h)
            estilo_header(ws.cell(row=3, column=c))

        row = 4

        for s in silos_cereal:

            grado = None
            factor = None
            tas = None
            fecha_est = None

            if s["ultimo_muestreo"]:

                ana = conn.execute("""
                    SELECT grado, factor, tas
                    FROM analisis
                    WHERE id_muestreo=? AND empresa_id=?
                """, (s["ultimo_muestreo"], empresa_id)).fetchall()

                grados = []
                factores = []
                tass = []

                for a in ana:

                    if a["grado"] is not None:
                        try:
                            grados.append(int(a["grado"]))
                        except:
                            pass

                    if a["factor"] is not None:
                        factores.append(float(a["factor"]))

                    if a["tas"] is not None:
                        tass.append(int(a["tas"]))

                if grados:
                    grado = max(grados)

                if factores:
                    factor = round(sum(factores) / len(factores), 4)

                if tass:
                    tas = min(tass)

                    f = conn.execute("""
                        SELECT fecha_muestreo
                        FROM muestreos
                        WHERE id=? AND empresa_id=?
                    """, (s["ultimo_muestreo"], empresa_id)).fetchone()

                    if f and f["fecha_muestreo"]:
                        try:
                            base = datetime.strptime(
                                f["fecha_muestreo"],
                                "%Y-%m-%d %H:%M"
                            )
                            fecha_est = (
                                base + timedelta(days=tas)
                            ).strftime("%Y-%m-%d")
                        except:
                            pass

            try:
                kg = conn.execute("""
                    SELECT COALESCE(SUM(kg),0) total
                    FROM llenado
                    WHERE numero_qr=? AND empresa_id=?
                """, (s["numero_qr"], empresa_id)).fetchone()["total"]
            except:
                kg = 0

            if not kg:
                kg = (s["metros"] or 0) * 1000

            merc = mercado.get(cereal)

            precio_ars = None
            precio_usd = None

            if factor and merc and merc["pizarra"]:
                precio_ars = round(merc["pizarra"] * factor, 2)

                if merc["dolar"]:
                    precio_usd = round(precio_ars / merc["dolar"], 2)

            vals = [
                s["numero_qr"],
                s["fecha_confeccion"],
                s["estado_silo"],
                s["estado_grano"],
                s["metros"],
                int(kg),
                grado,
                round(factor * 100, 2) if factor else None,
                tas,
                fecha_est,
                precio_ars,
                precio_usd
            ]

            alerta = (
                s["estado_silo"] == "Extraído"
            )

            for c, v in enumerate(vals, 1):
                ws.cell(row=row, column=c, value=v)

                color = None

                if alerta:
                    color = "FFEBEE"
                elif row % 2 == 0:
                    color = GRIS

                estilo_body(ws.cell(row=row, column=c), color)

            row += 1

        for col in range(1, 13):
            ws.column_dimensions[get_column_letter(col)].width = 18

        ws.auto_filter.ref = f"A3:L{row}"

    # =====================================================
    # FUTUROS MATBA
    # =====================================================
    ws = wb.create_sheet("Futuros")

    ws.merge_cells("A1:H1")
    ws["A1"] = "PIZARRA VS FUTUROS MATBA"
    estilo_titulo(ws["A1"], AZUL)

    headers = [
        "Cereal",
        "Posición",
        "Mes",
        "Futuro USD",
        "Pizarra ARS",
        "USD Hoy",
        "Diferencia %",
        "Recomendación"
    ]

    for c, h in enumerate(headers, 1):
        ws.cell(row=3, column=c, value=h)
        estilo_header(ws.cell(row=3, column=c), AZUL)

    row = 4

    for m in matba_rows:

        cereal = m["cereal"]
        merc = mercado.get(cereal)

        if not merc:
            continue

        hoy_usd = None
        dif = None
        rec = "Sin dato"

        if merc["pizarra"] and merc["dolar"]:
            hoy_usd = round(
                merc["pizarra"] / merc["dolar"],
                2
            )

            if hoy_usd > 0:
                dif = round(
                    ((m["precio"] - hoy_usd) / hoy_usd) * 100,
                    2
                )

                rec = "Esperar" if dif > 5 else "Vender Hoy"

        vals = [
            cereal,
            m["posicion"],
            m["mes"],
            m["precio"],
            merc["pizarra"],
            hoy_usd,
            dif,
            rec
        ]

        for c, v in enumerate(vals, 1):
            ws.cell(row=row, column=c, value=v)

            color = None
            if dif and dif > 5:
                color = VERDE3
            elif dif and dif < 0:
                color = "FFEBEE"

            estilo_body(ws.cell(row=row, column=c), color)

        row += 1

    for col in range(1, 9):
        ws.column_dimensions[get_column_letter(col)].width = 18

    ws.auto_filter.ref = f"A3:H{row}"

    # =====================================================
    # GUARDAR
    # =====================================================
    registrar_auditoria(
        conn,
        current_user.id,
        empresa_id,
        "exportacion_excel",
        "Exportación de datos",
        None
    )

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"silos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@panel_bp.route("/seleccionar_empresa/<int:id>")
@login_required
def seleccionar_empresa(id):
    if not current_user.es_superadmin:
        return "No autorizado", 403
    session["empresa_contexto"] = id
    return redirect(url_for("panel.panel"))


@panel_bp.route("/cambiar_empresa")
@login_required
def cambiar_empresa():
    if not current_user.es_superadmin:
        return "No autorizado", 403
    session.pop("empresa_contexto", None)
    return redirect(url_for("panel.panel"))
