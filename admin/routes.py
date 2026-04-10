from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado
from datetime import datetime
from werkzeug.security import generate_password_hash
import secrets
import string
from panel.routes import empresa_actual
import sqlite3

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")
    
# ==========================
# EMPRESAS
# ==========================
@admin_bp.route("/empresas")
@login_required
def admin_empresas():

    if not current_user.es_superadmin:
        return "No autorizado", 403

    conn = get_db()
    empresas = conn.execute("""
        SELECT * FROM empresas
        ORDER BY fecha_alta DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin_empresas.html",
        empresas=empresas,
        fecha_hoy=datetime.now().strftime("%Y-%m-%d")  # 👈 ESTA LÍNEA ES CLAVE
    )
# ==========================
# CREAR EMPRESA
# ==========================
@admin_bp.route("/empresas/crear", methods=["POST"])
@login_required
def crear_empresa():

    if not current_user.es_superadmin:
        return "No autorizado", 403

    nombre = request.form.get("nombre")
    tipo_contrato = request.form.get("tipo_contrato")
    fecha_vencimiento = request.form.get("fecha_vencimiento")

    if not nombre:
        return redirect("/admin/empresas")

    conn = get_db()

    # Crear empresa
    conn.execute("""
        INSERT INTO empresas (
            nombre,
            fecha_alta,
            tipo_contrato,
            fecha_vencimiento,
            activa
        )
        VALUES (?,?,?,?,1)
    """, (
        nombre,
        datetime.now().strftime("%Y-%m-%d"),
        tipo_contrato,
        fecha_vencimiento
    ))

    empresa = conn.execute(
        "SELECT id FROM empresas WHERE nombre=?", (nombre,)
    ).fetchone()
    empresa_id = empresa["id"]
    # ======================
    # CREAR MERCADO BASE
    # ======================
    cereales = ["Soja", "Maíz", "Trigo", "Girasol"]

    for cereal in cereales:
        conn.execute("""
            INSERT INTO mercado (empresa_id, cereal)
            VALUES (?,?)
        """, (empresa_id, cereal))

    # Crear sucursal central
    conn.execute("""
    INSERT INTO sucursales (empresa_id, nombre)
    VALUES (?,?)
    """, (empresa_id, "Casa Central"))

    sucursal = conn.execute(
        "SELECT id FROM sucursales WHERE empresa_id=? ORDER BY id DESC LIMIT 1",
        (empresa_id,)
    ).fetchone()
    sucursal_id = sucursal["id"]

    # 🔥 GENERAR PASSWORD TEMPORAL SEGURA
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))

    username_admin = nombre.lower().replace(" ", "_") + "_admin"

    # Crear usuario administrador de la empresa
    conn.execute("""
        INSERT INTO usuarios (
            username,
            password,
            rol,
            empresa_id,
            sucursal_id,
            es_superadmin,
            forzar_cambio_password
        )
        VALUES (?,?,?,?,?,?,1)
    """, (
        username_admin,
        generate_password_hash(temp_password),
        "admin_empresa",
        empresa_id,
        sucursal_id,
        0
    ))

    conn.commit()
    conn.close()

    return render_template(
        "empresa_creada.html",
        username=username_admin,
        password=temp_password
    )

# ==============================
# PAUSAR / REACTIVAR EMPRESA
# ==============================
@admin_bp.route("/empresa/toggle/<int:id>")
@login_required
def toggle_empresa(id):

    # Solo superadmin
    if current_user.es_superadmin != 1:
        return "No autorizado", 403

    conn = get_db()

    empresa = conn.execute(
        "SELECT activa FROM empresas WHERE id=?",
        (id,)
    ).fetchone()

    if empresa:
        nueva = 0 if empresa["activa"] == 1 else 1

        conn.execute(
            "UPDATE empresas SET activa=? WHERE id=?",
            (nueva, id)
        )

        conn.commit()

    conn.close()

    return redirect(url_for("admin.admin_empresas"))
# ==============================
# ELIMINAR EMPRESA
# ==============================
@admin_bp.route("/empresa/eliminar/<int:id>")
@login_required
def eliminar_empresa(id):

    if current_user.es_superadmin != 1:
        return "No autorizado", 403

    conn = get_db()

    # Borrar usuarios primero
    conn.execute("DELETE FROM usuarios WHERE empresa_id=?", (id,))

    # Borrar sucursales
    conn.execute("DELETE FROM sucursales WHERE empresa_id=?", (id,))

    # Borrar empresa
    conn.execute("DELETE FROM empresas WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_empresas"))
@admin_bp.route("/usuarios")
@login_required
def admin_usuarios():

    if not (current_user.es_superadmin or tiene_permiso("admin")):
        return acceso_denegado("admin")

    empresa_id = empresa_actual()

    if not empresa_id:
        return redirect(url_for("panel.panel"))

    conn = get_db()

    usuarios = conn.execute("""
        SELECT *
        FROM usuarios
        WHERE empresa_id=?
        ORDER BY id DESC
    """, (empresa_id,)).fetchall()

    permisos = conn.execute("""
        SELECT user_id, pantalla
        FROM permisos
    """).fetchall()

    solicitudes = conn.execute("""
        SELECT s.*, u.username
        FROM solicitudes s
        JOIN usuarios u ON u.id = s.user_id
        WHERE u.empresa_id=? AND s.estado='pendiente'
    """, (empresa_id,)).fetchall()

    conn.close()

    permisos_set = {(p["user_id"], p["pantalla"]) for p in permisos}

    return render_template(
        "admin_usuarios.html",
        usuarios=usuarios,
        permisos_set=permisos_set,
        solicitudes=solicitudes
    )
@admin_bp.route("/permisos", methods=["POST"])
@login_required
def guardar_permisos():

    if current_user.rol != "admin_empresa":
        return "No autorizado", 403

    user_id = request.form.get("user_id")
    permisos = request.form.getlist("permisos")

    conn = get_db()

    # Borrar permisos actuales
    conn.execute("DELETE FROM permisos WHERE user_id=?", (user_id,))

    # Insertar nuevos
    for p in permisos:
        conn.execute(
            "INSERT INTO permisos (user_id, pantalla) VALUES (?,?)",
            (user_id, p)
        )

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_usuarios"))
@admin_bp.route("/crear_usuario", methods=["POST"])
@login_required
def crear_usuario():

    if current_user.rol != "admin_empresa":
        return "No autorizado", 403

    username = request.form.get("username")
    password = request.form.get("password")
    rol = request.form.get("rol")

    conn = get_db()
    empresa_id = empresa_actual()

    # 🔥 buscar sucursal de la empresa
    sucursal = conn.execute("""
        SELECT id FROM sucursales
        WHERE empresa_id=?
        LIMIT 1
    """, (empresa_id,)).fetchone()

    sucursal_id = sucursal["id"] if sucursal else None

    conn.execute("""
        INSERT INTO usuarios (
            username,
            password,
            rol,
            empresa_id,
            sucursal_id,
            forzar_cambio_password
        )
        VALUES (?,?,?,?,?,1)
    """, (
        username,
        generate_password_hash(password),
        rol,
        empresa_id,
        sucursal_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_usuarios"))
@admin_bp.route("/eliminar_usuario", methods=["POST"])
@login_required
def eliminar_usuario():

    if current_user.rol != "admin_empresa":
        return "No autorizado", 403

    user_id = request.form.get("user_id")

    # No permitir que se elimine a sí mismo
    if int(user_id) == current_user.id:
        return redirect(url_for("admin.admin_usuarios"))

    conn = get_db()

    conn.execute("DELETE FROM permisos WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM usuarios WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_usuarios"))
@admin_bp.route("/aprobar_solicitud", methods=["POST"])
@login_required
def aprobar_solicitud():

    solicitud_id = request.form.get("id")

    empresa_id = empresa_actual()

    conn = get_db()  # 🔥 FALTABA ESTO

    s = conn.execute("""
        SELECT sol.*
        FROM solicitudes sol
        JOIN usuarios u ON sol.user_id = u.id
        WHERE sol.id = ?
        AND u.empresa_id = ?
    """, (
        solicitud_id,
        empresa_id
    )).fetchone()

    if s:
        conn.execute(
            "INSERT INTO permisos (user_id, pantalla) VALUES (?,?)",
            (s["user_id"], s["pantalla"])
        )

        conn.execute(
            "UPDATE solicitudes SET estado='aprobado' WHERE id=?",
            (solicitud_id,)
        )

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_usuarios"))
@admin_bp.route("/rechazar_solicitud", methods=["POST"])
@login_required
def rechazar_solicitud():

    solicitud_id = request.form.get("id")

    conn = get_db()

    conn.execute(
        "UPDATE solicitudes SET estado='rechazado' WHERE id=?",
        (solicitud_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_usuarios"))
@admin_bp.route("/solicitar_acceso/<pantalla>", methods=["POST"])
@login_required
def solicitar_acceso(pantalla):

    conn = get_db()

    ya_solicitado = conn.execute("""
        SELECT 1 FROM solicitudes
        WHERE user_id=? AND pantalla=? AND estado='pendiente'
    """, (current_user.id, pantalla)).fetchone()

    if not ya_solicitado:
        conn.execute("""
            INSERT INTO solicitudes (user_id, pantalla, fecha, estado)
            VALUES (?,?,?,'pendiente')
        """, (current_user.id, pantalla, datetime.now().strftime("%Y-%m-%d %H:%M")))

        conn.commit()

    conn.close()

    return redirect(request.referrer or url_for("panel.panel"))

@admin_bp.route("/empresa/reactivar/<int:id>", methods=["POST"])
@login_required
def reactivar_empresa(id):

    if current_user.es_superadmin != 1:
        return "No autorizado", 403

    nueva_fecha = request.form.get("nueva_fecha")

    conn = get_db()

    conn.execute("""
        UPDATE empresas
        SET activa=1,
            fecha_vencimiento=?
        WHERE id=?
    """, (nueva_fecha, id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_empresas"))

@admin_bp.route("/finanzas")
@login_required
def admin_finanzas():

    if current_user.es_superadmin != 1:
        return "No autorizado", 403

    conn = get_db()

    empresas = conn.execute("""
        SELECT id, nombre, tipo_contrato
        FROM empresas
    """).fetchall()

    resumen = []

    for e in empresas:

        total_silos = conn.execute("""
            SELECT COUNT(*) AS total
            FROM silos
            WHERE empresa_id=? AND estado_silo='Activo'
        """, (e["id"],)).fetchone()["total"]

        silos_cobrados = conn.execute("""
            SELECT COALESCE(SUM(silos_cobrados),0) AS total
            FROM pagos
            WHERE empresa_id=?
        """, (e["id"],)).fetchone()["total"]

        total_monto = conn.execute("""
            SELECT COALESCE(SUM(monto),0) AS total
            FROM pagos
            WHERE empresa_id=?
        """, (e["id"],)).fetchone()["total"]

        pendiente = total_silos - silos_cobrados

        resumen.append({
            "id": e["id"],
            "nombre": e["nombre"],
            "tipo": e["tipo_contrato"],
            "silos": total_silos,
            "cobrados": silos_cobrados,
            "pendiente": pendiente,
            "monto": total_monto
        })

    conn.close()

    return render_template(
        "admin_finanzas.html",
        resumen=resumen
    )
from datetime import datetime

@admin_bp.route("/finanzas/pago/<int:id>", methods=["GET","POST"])
@login_required
def registrar_pago(id):

    if current_user.es_superadmin != 1:
        return "No autorizado", 403

    conn = get_db()

    # 🔹 Traer nombre empresa
    empresa = conn.execute(
        "SELECT nombre FROM empresas WHERE id=?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        monto = request.form.get("monto")
        silos = request.form.get("silos_cobrados")
        observacion = request.form.get("observacion")
        fecha_pago = request.form.get("fecha_pago")

        conn.execute("""
            INSERT INTO pagos (
                empresa_id,
                fecha_pago,
                monto,
                silos_cobrados,
                observacion
            )
            VALUES (?,?,?,?,?)
        """, (
            id,
            fecha_pago,
            monto,
            silos,
            observacion
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("admin.admin_finanzas"))

    conn.close()

    return render_template(
        "registrar_pago.html",
        empresa_id=id,
        empresa_nombre=empresa["nombre"],
        fecha_hoy=datetime.now().strftime("%Y-%m-%d")
    )
