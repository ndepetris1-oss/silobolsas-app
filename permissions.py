from flask_login import current_user, login_required
from db import get_db
from flask import Blueprint
from datetime import datetime
from flask import render_template, request

permissions_bp = Blueprint("permissions", __name__)

def tiene_permiso(pantalla):

    if not current_user.is_authenticated:
        return False

    if current_user.es_superadmin == 1:
        return True

    conn = get_db()

    empresa = conn.execute("""
        SELECT fecha_vencimiento, activa
        FROM empresas
        WHERE id=?
    """, (current_user.empresa_id,)).fetchone()

    # 🔴 EMPRESA PAUSADA MANUALMENTE
    if empresa and empresa["activa"] == 0:
        if pantalla == "form":
            return True
        else:
            return False

    if empresa and empresa["fecha_vencimiento"]:
        fecha_venc = datetime.strptime(
            empresa["fecha_vencimiento"], "%Y-%m-%d"
        )

        if datetime.now() > fecha_venc:
            # Empresa vencida
            if pantalla == "form":
                return True
            else:
                return False

    # permiso normal
    row = conn.execute("""
        SELECT 1 FROM permisos
        WHERE user_id=? AND pantalla=?
    """, (current_user.id, pantalla)).fetchone()

    conn.close()

    return row is not None

def acceso_denegado(pantalla):

    conn = get_db()

    ya_solicitado = conn.execute("""
        SELECT 1 FROM solicitudes
        WHERE user_id=? AND pantalla=? AND estado='pendiente'
    """, (current_user.id, pantalla)).fetchone()

    solicitud_enviada = False

    if request.method == "POST" and not ya_solicitado:
        conn.execute("""
            INSERT INTO solicitudes (user_id, pantalla, fecha)
            VALUES (?,?,datetime('now'))
        """, (
            current_user.id,
            pantalla
        ))
        conn.commit()
        solicitud_enviada = True

    elif ya_solicitado:
        solicitud_enviada = True

    conn.close()

    return render_template(
        "no_autorizado.html",
        pantalla=pantalla,
        solicitud_enviada=solicitud_enviada
    ), 403

@permissions_bp.route("/acceso/<pantalla>")
@login_required
def acceso(pantalla):
    return acceso_denegado(pantalla)