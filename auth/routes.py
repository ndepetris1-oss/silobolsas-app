from auth.models import User
from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db
from extensions import login_manager
import re

auth_bp = Blueprint("auth", __name__)

def validar_password(password):
    if len(password) < 8:
        return "Debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return "Debe tener al menos una mayúscula"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Debe tener al menos un carácter especial"
    return None
# ==========================
# LOAD USER
# ==========================

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# ==========================
# LOGIN
# ==========================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")

        if not username:
            return render_template("login.html", error="Ingrese usuario")

        username = username.strip().lower()
        password = request.form.get("password")
        if not password:
            return render_template("login.html", error="Ingrese contraseña")
    
        conn = get_db()

        u = conn.execute(
            "SELECT * FROM usuarios WHERE LOWER(username)=?",
            (username,)
        ).fetchone()

        conn.close()

        if u and check_password_hash(u["password"], password):

            # 🔥 SI NO ES SUPERADMIN, VALIDAR EMPRESA
            if u["es_superadmin"] != 1:

                conn = get_db()

                empresa = conn.execute("""
                    SELECT activa, fecha_vencimiento
                    FROM empresas
                    WHERE id=?
                """, (u["empresa_id"],)).fetchone()

                conn.close()

                if not empresa:
                    return render_template("login.html", error="Empresa no válida")

                if empresa["activa"] == 0:
                    return render_template(
                        "login.html",
                        error="Empresa suspendida. Contacte al administrador."
                    )

                if empresa["fecha_vencimiento"]:
                    from datetime import datetime
                    hoy = datetime.now().strftime("%Y-%m-%d")

                    if empresa["fecha_vencimiento"] < hoy:
                        return render_template(
                            "login.html",
                            error="Contrato vencido. Contacte al administrador."
                        )

            # 🔥 CREAR USER
            user = User(u)
            login_user(user)

            if user.es_superadmin:
                session.pop("empresa_contexto", None)

            # 🔥 FORZAR CAMBIO PASSWORD
            if user.forzar_cambio_password == 1:
                return redirect(url_for("auth.cambiar_password"))

            # SUPERADMIN va al panel general
            if user.es_superadmin == 1:
                return redirect(url_for("panel.panel"))

            # Admin de empresa va a gestión de usuarios
            if user.rol == "admin_empresa":
                return redirect(url_for("admin.admin_usuarios"))

            # Usuarios normales al panel
            return redirect(url_for("panel.panel"))

        # 🔥 SI PASSWORD INCORRECTA
        return render_template(
            "login.html",
            error="Credenciales incorrectas"
        )

    return render_template("login.html")

# ==========================
# RESET SUPERADMIN
# ==========================
@auth_bp.route("/admin/reset_password", methods=["POST"])
@login_required
def reset_password_admin():

    if not current_user.es_superadmin:
        return {"ok": False, "error": "No autorizado"}, 403

    user_id = request.form.get("user_id")
    nueva = request.form.get("password")

    if not nueva:
        return {"ok": False, "error": "Falta contraseña"}, 400

    error = validar_password(nueva)
    if error:
        return {"ok": False, "error": error}, 400

    conn = get_db()

    conn.execute("""
        UPDATE usuarios
        SET password=?, forzar_cambio_password=1
        WHERE id=?
    """, (
        generate_password_hash(nueva),
        user_id
    ))

    conn.commit()
    conn.close()

    return {"ok": True}
# ==========================
# LOGOUT
# ==========================

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
@auth_bp.route("/cambiar_password", methods=["GET","POST"])
@login_required
def cambiar_password():

    if request.method == "POST":

        nueva = request.form.get("password")
        confirmar = request.form.get("confirmar_password")

        if not nueva:
            return render_template("cambiar_password.html", error="Ingrese contraseña")

        if nueva != confirmar:
            return render_template("cambiar_password.html", error="Las contraseñas no coinciden")

        error = validar_password(nueva)
        if error:
            return render_template("cambiar_password.html", error=error)

        conn = get_db()

        conn.execute("""
            UPDATE usuarios
            SET password=?, forzar_cambio_password=0
            WHERE id=?
        """, (
            generate_password_hash(nueva),
            current_user.id
        ))

        conn.commit()
        conn.close()

        # SUPERADMIN
        if current_user.es_superadmin == 1:
            return redirect(url_for("panel.panel"))

        # ADMIN EMPRESA
        if current_user.rol == "admin_empresa":
            return redirect(url_for("admin.admin_usuarios"))

        # USUARIO NORMAL
        return redirect(url_for("panel.panel"))

    return render_template("cambiar_password.html")
