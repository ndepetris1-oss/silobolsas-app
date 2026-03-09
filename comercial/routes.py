from flask import Blueprint, render_template, redirect, request, jsonify, url_for
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from calculos import calcular_merma_humedad
import requests
from datetime import datetime
from panel.routes import empresa_actual
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
from utils.fechas import normalizar_fecha

comercial_bp = Blueprint("comercial", __name__, url_prefix="/comercial")

def ahora():
    return datetime.now()
# ======================
# COMERCIAL – PANTALLA
# ======================
@comercial_bp.route("/")
@login_required
def comercial():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    empresa_id = empresa_actual()

    if not empresa_id:
        return redirect(url_for("panel.panel"))

    conn = get_db()

    rows = conn.execute("""
        SELECT cereal,
            pizarra_auto,
            fuente,
            fecha_fuente,
            pizarra_manual,
            usar_manual,
            obs_precio,
            dolar,
            fecha
        FROM mercado
        WHERE empresa_id=?
        ORDER BY cereal
    """, (empresa_id,)).fetchall()

    dolar_info = conn.execute("""
        SELECT dolar, fecha
        FROM mercado
        WHERE empresa_id=?
        AND dolar > 0
        ORDER BY fecha DESC
        LIMIT 1
    """, (empresa_id,)).fetchone()
    fecha_dolar_arg = None

    if dolar_info and dolar_info["fecha"]:

        fecha_utc = normalizar_fecha(dolar_info["fecha"])

        fecha_utc = fecha_utc.replace(
            tzinfo=ZoneInfo("UTC")
        )

        fecha_arg = fecha_utc.astimezone(
            ZoneInfo("America/Argentina/Buenos_Aires")
        )

        fecha_dolar_arg = fecha_arg.strftime("%Y-%m-%d %H:%M:%S")

    fecha_pizarra = None

    if rows and rows[0]["fecha_fuente"]:
        fecha_pizarra = rows[0]["fecha_fuente"]
    # ======================
    # TRAER ROFEX
    # ======================

    rofex = conn.execute("""
        SELECT posicion, ajuste, variacion, fecha
        FROM rofex
        ORDER BY fecha DESC
        LIMIT 10
    """).fetchall()

    rofex_fecha = conn.execute("""
        SELECT fecha
        FROM rofex
        ORDER BY fecha DESC
        LIMIT 1
    """).fetchone()

    fecha_rofex_arg = None

    if rofex_fecha and rofex_fecha["fecha"]:

        fecha_utc = normalizar_fecha(rofex_fecha["fecha"])

        fecha_utc = fecha_utc.replace(
            tzinfo=ZoneInfo("UTC")
        )

        fecha_arg = fecha_utc.astimezone(
            ZoneInfo("America/Argentina/Buenos_Aires")
        )

        fecha_rofex_arg = fecha_arg.strftime("%Y-%m-%d %H:%M:%S")

    matba = conn.execute("""
        SELECT posicion, cereal, precio, variacion, fecha, mes
        FROM matba
        ORDER BY fecha DESC
        LIMIT 18
    """).fetchall()

    matba_fecha = conn.execute("""
        SELECT fecha
        FROM matba
        ORDER BY fecha DESC
        LIMIT 1
    """).fetchone()

    fecha_matba_arg = None

    if matba_fecha and matba_fecha["fecha"]:

        fecha_obj = normalizar_fecha(matba_fecha["fecha"])
        fecha_matba_arg = fecha_obj.strftime("%d/%m/%Y %H:%M")

    conn.close()
    return render_template(
        "comercial.html",
        mercado=rows,
        dolar_info=dolar_info,
        fecha_dolar_arg=fecha_dolar_arg,
        fecha_pizarra=fecha_pizarra,
        rofex=rofex,
        fecha_rofex_arg=fecha_rofex_arg,
        matba=matba,
        fecha_matba_arg=fecha_matba_arg,
        puede_comparador=tiene_permiso("comparador"),
    )
# ======================
# COMPARADOR REDIRECT
# ======================
@comercial_bp.route("/comparador")
@login_required
def comparador_redirect():

    if not tiene_permiso("comparador"):
        return acceso_denegado("comparador")

    return redirect("/comercial")

def elegir_futuro(futuros, criterio):
    if not futuros:
        return None

    if criterio == "mejor_precio":
        return max(futuros, key=lambda x: x["precio"])

    if criterio == "mas_cercano_actual":
        return futuros[0]

    # por ahora mas_cercano_tas lo implementamos después
    return futuros[0]
# ======================
# COMPARADOR DETALLE
# ======================
@comercial_bp.route("/<cereal>")
@login_required
def comparador(cereal):

    if not tiene_permiso("comparador"):
        return acceso_denegado("comparador")

    empresa_id = empresa_actual()

    if not empresa_id:
        return redirect(url_for("panel.panel"))

    conn = get_db()

    # Obtener precio base (manual o automático)
    precio_row = conn.execute("""
        SELECT 
            CASE 
                WHEN usar_manual = 1 AND pizarra_manual IS NOT NULL 
                THEN pizarra_manual 
                ELSE pizarra_auto 
            END as precio_base,
            dolar
        FROM mercado
        WHERE cereal=? AND empresa_id=?
    """, (cereal, empresa_id)).fetchone()

    precio_base = precio_row["precio_base"] if precio_row and precio_row["precio_base"] else 0
    dolar = precio_row["dolar"] if precio_row and precio_row["dolar"] else 0

    # Obtener criterio configurado por empresa
    criterio_row = conn.execute("""
        SELECT criterio_futuro
        FROM empresas
        WHERE id=?
    """, (empresa_id,)).fetchone()

    criterio_futuro = criterio_row["criterio_futuro"] if criterio_row else "mas_cercano_actual"

    rows = conn.execute("""
        SELECT
                s.numero_qr,

                (
                SELECT MIN(a.tas)
                FROM analisis a
                JOIN muestreos m ON m.id = a.id_muestreo
                WHERE m.numero_qr = s.numero_qr
                    AND m.empresa_id = s.empresa_id
                    AND a.tas IS NOT NULL
                ) AS tas_min,

            (
                SELECT AVG(a.factor)
                FROM analisis a
                JOIN muestreos m ON m.id = a.id_muestreo
                WHERE m.numero_qr = s.numero_qr
                    AND m.empresa_id = s.empresa_id
                    AND a.factor IS NOT NULL
                ) AS factor_prom,

            (
                SELECT AVG(a.humedad)
                FROM analisis a
                JOIN muestreos m ON m.id = a.id_muestreo
                WHERE m.numero_qr = s.numero_qr
                    AND m.empresa_id = s.empresa_id
                    AND a.humedad IS NOT NULL
                ) AS humedad_prom,

            (
              SELECT COUNT(*)
              FROM analisis a
              JOIN muestreos m ON m.id = a.id_muestreo
              WHERE m.numero_qr = s.numero_qr
                AND m.empresa_id = s.empresa_id
                AND a.insectos = 1
            ) AS tiene_insectos

        FROM silos s
        WHERE s.estado_silo = 'Activo'
          AND s.cereal = ?
          AND s.empresa_id = ?
        ORDER BY s.numero_qr
    """, (cereal, empresa_id)).fetchall()
    # Mapear cereal a prefijo MATBA
    prefijos = {
        "Maíz": "CR",
        "Soja": "SR",
        "Trigo": "WR"
    }

    prefijo = prefijos.get(cereal)

    if prefijo:
        futuros = conn.execute("""
            SELECT posicion, cereal, precio, fecha, mes
            FROM matba
            WHERE posicion LIKE ?
            ORDER BY fecha
        """, (f"{prefijo}%",)).fetchall()
    else:
        futuros = []

    futuro_sugerido = elegir_futuro(futuros, criterio_futuro)

    futuros_lista = []

    for f in futuros:

            f = dict(f)

            precio = float(f["precio"]) if f["precio"] else 0

            gastos = 34

            f["gastos"] = gastos
            f["precio_neto"] = precio - gastos

            futuros_lista.append(f)

    futuros = futuros_lista

    mejor_precio = 0

    for f in futuros:
        if f["precio_neto"] > mejor_precio:
            mejor_precio = f["precio_neto"]

    conn.close()

    silos = []

    for r in rows:
        silo_dict = dict(r)

        if silo_dict.get("factor_prom") is not None:
            silo_dict["factor_prom"] = round(float(silo_dict["factor_prom"]), 4)

        if silo_dict.get("humedad_prom") is not None:
            silo_dict["humedad_prom"] = round(float(silo_dict["humedad_prom"]), 2)

        silo_dict["tiene_insectos"] = True if r["tiene_insectos"] > 0 else False

        silo_dict["merma_humedad"] = calcular_merma_humedad(
            cereal,
            silo_dict.get("humedad_prom")
        )

        silo_dict["tas_min"] = r["tas_min"]

        silos.append(silo_dict)

    return render_template(
        "comparador.html",
        cereal=cereal,
        silos=silos,
        criterio_futuro=criterio_futuro,
        precio_base=precio_base,
        dolar=dolar,
        futuro_sugerido=futuro_sugerido,
        futuros=futuros,
        mejor_precio=mejor_precio
    )

# ======================
# COMERCIAL – API
# ======================
@comercial_bp.route("/api/mercado/manual", methods=["POST"])
@login_required
def mercado_manual():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    d = request.get_json()

    conn = get_db()

    conn.execute("""
        UPDATE mercado
        SET
            pizarra_manual=?,
            usar_manual=?,
            obs_precio=?,
            dolar=?,
            fecha=CURRENT_TIMESTAMP
        WHERE cereal=? AND empresa_id=?
    """, (
        d.get("pizarra_manual"),
        1 if d.get("usar_manual") else 0,
        d.get("obs_precio"),
        d.get("dolar"),
        d["cereal"], current_user.empresa_id
    ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)
# ======================
# DÓLAR OFICIAL
# ======================
def obtener_dolar_oficial():
    try:
        r = requests.get(
            "https://api.bluelytics.com.ar/v2/latest",
            timeout=10
        )
        data = r.json()
        return data["oficial"]["value_avg"]
    except Exception as e:
        print("Error dólar:", e)
        return None


@comercial_bp.route("/api/actualizar_dolar", methods=["POST"])
@login_required
def actualizar_dolar():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    dolar = obtener_dolar_oficial()

    if dolar is None:
        return jsonify({"ok": False, "error": "No se pudo obtener el dólar"})

    conn = get_db()

    conn.execute("""
        UPDATE mercado
        SET dolar = ?, fecha = CURRENT_TIMESTAMP
        WHERE empresa_id = ?
    """, (dolar, current_user.empresa_id))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "dolar": dolar})
# ======================
# PIZARRA AUTO (MOCK)
# ======================
def obtener_pizarra_auto(cereal):

    url = "https://www.cac.bcr.com.ar/es/precios-de-pizarra"

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        mapa = {
            "Soja": "soja",
            "Maíz": "maiz",
            "Trigo": "trigo",
            "Girasol": "girasol"
        }

        clave = mapa.get(cereal)

        if not clave:
            return None

        board = soup.select_one(f".board-{clave}")

        if not board:
            print("No se encontró board para:", cereal)
            return None

        price_div = board.select_one(".price")

        if not price_div:
            return None

        precio_texto = price_div.text.strip()

        if "S/C" in precio_texto:
            return None

        precio = (
            precio_texto
            .replace("$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

        precio = float(precio)

        return {
            "precio": precio,
            "fuente": "CAC BCR",
            "fecha": datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%Y-%m-%d %H:%M")
        }

    except Exception as e:
        print("Error obteniendo pizarra:", e)
        return None
@comercial_bp.route("/api/actualizar_pizarra", methods=["POST"])
@login_required
def actualizar_pizarra():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    conn = get_db()

    rows = conn.execute(
        "SELECT cereal FROM mercado WHERE empresa_id=?",
        (current_user.empresa_id,)
    ).fetchall()

    for r in rows:

        cereal = r["cereal"]
        data = obtener_pizarra_auto(cereal)

        if not data:
            continue

        conn.execute("""
            UPDATE mercado
            SET
                pizarra_auto = ?,
                fuente = ?,
                fecha_fuente = ?,
                fecha = CURRENT_TIMESTAMP
            WHERE cereal = ?
            AND empresa_id = ?
        """, (
            data["precio"],
            data["fuente"],
            data["fecha"],
            cereal,
            current_user.empresa_id
        ))

    conn.commit()
    conn.close()

    return jsonify(ok=True)


@comercial_bp.route("/api/actualizar_rofex", methods=["POST"])
@login_required
def actualizar_rofex():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    url = "https://p2.acacoop.com.ar/dkmserver.services/html/acabaseservice.aspx"

    params = {
        "mt": "GetMercadosCMA",
        "appname": "acabase",
        "mrkt": "rofex"
    }

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()

        if data["result"]["resultCode"] != 600:
            print("Error API ROFEX:", data)
            return jsonify(ok=False)

        valores = data["result"]["value"]

        conn = get_db()
        conn.execute("DELETE FROM rofex")

        for item in valores:
            conn.execute("""
                INSERT INTO rofex (
                    posicion,
                    ajuste,
                    ajuste_anterior,
                    variacion,
                    fecha
                )
                VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)
                """, (
                    item.get("CODIGO"),
                    float(item.get("AJUSTE", 0)),
                    float(item.get("CIERRE", 0)),
                    float(item.get("VARIACION", 0))
                ))

        conn.commit()
        conn.close()

        print("ROFEX actualizado correctamente")
        return jsonify(ok=True)

    except Exception as e:
        print("Error actualizando ROFEX:", e)
        return jsonify(ok=False)
@comercial_bp.route("/api/actualizar_matba", methods=["POST"])
@login_required
def actualizar_matba():

    if not tiene_permiso("comercial"):
        return acceso_denegado("comercial")

    url = "https://p2.acacoop.com.ar/dkmserver.services/html/acabaseservice.aspx"

    params = {
        "mt": "GetMercadosCMA",
        "appname": "acabase",
        "mrkt": "MATBAPISO"
    }

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        data = r.json()

        if data["result"]["resultCode"] != 600:
            print("Error API MATBA:", data)
            return jsonify(ok=False)

        valores = data["result"]["value"]
        fecha_actualizacion = data["result"]["lastUpdatedDateData"]

        conn = get_db()
        conn.execute("DELETE FROM matba")

        for item in valores:

            mes_contrato = item.get("MES")  # 👈 ESTO ES CLAVE

            conn.execute("""
            INSERT INTO matba (
                posicion,
                cereal,
                precio,
                precio_anterior,
                variacion,
                fecha,
                mes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item["CODIGO"],
                item["DESCRIPCION"],
                float(item["AJUSTE"]),
                float(item["CIERRE"]),
                float(item["VARIACION"]),
                fecha_actualizacion,
                mes_contrato
            ))

        conn.commit()
        conn.close()

        print("MATBA actualizado correctamente")
        return jsonify(ok=True)

    except Exception as e:
        print("Error actualizando MATBA:", e)
        return jsonify(ok=False)
