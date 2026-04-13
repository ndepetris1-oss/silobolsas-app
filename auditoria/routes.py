from flask import Blueprint, render_template, session
from flask_login import login_required, current_user
from db import get_db
from permissions import tiene_permiso, acceso_denegado

auditoria_bp = Blueprint("auditoria", __name__, url_prefix="/auditoria")

@auditoria_bp.route("/")
@login_required
def index():

    if not tiene_permiso("auditoria"):
        return acceso_denegado("auditoria")

    conn = get_db()

    # Superadmin ve todo, admin ve solo su empresa
    if current_user.es_superadmin:
        empresa_id = session.get("empresa_contexto")
        if empresa_id:
            registros = conn.execute("""
                SELECT a.*, u.username, e.nombre as empresa_nombre
                FROM auditoria a
                JOIN usuarios u ON u.id = a.user_id
                JOIN empresas e ON e.id = a.empresa_id
                WHERE a.empresa_id = ?
                ORDER BY a.fecha DESC
                LIMIT 500
            """, (empresa_id,)).fetchall()
        else:
            registros = conn.execute("""
                SELECT a.*, u.username, e.nombre as empresa_nombre
                FROM auditoria a
                JOIN usuarios u ON u.id = a.user_id
                JOIN empresas e ON e.id = a.empresa_id
                ORDER BY a.fecha DESC
                LIMIT 500
            """).fetchall()
    else:
        registros = conn.execute("""
            SELECT a.*, u.username, e.nombre as empresa_nombre
            FROM auditoria a
            JOIN usuarios u ON u.id = a.user_id
            JOIN empresas e ON e.id = a.empresa_id
            WHERE a.empresa_id = ?
            ORDER BY a.fecha DESC
            LIMIT 500
        """, (current_user.empresa_id,)).fetchall()

    conn.close()

    return render_template("auditoria.html", registros=registros)
