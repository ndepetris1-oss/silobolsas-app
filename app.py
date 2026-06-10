from flask import Flask
from config import SECRET_KEY
from extensions import login_manager
from auth.routes import auth_bp
from panel.routes import panel_bp
from api.routes import api_bp
from admin.routes import admin_bp
from db_init import init_db
from comercial.routes import comercial_bp
from calado.routes import calado_bp
from muestreo.routes import muestreo_bp
from permissions import permissions_bp
from migraciones import ejecutar_migraciones
from silo.routes import silo_bp
from auditoria.routes import auditoria_bp

app = Flask(__name__)
ejecutar_migraciones()
app.secret_key = SECRET_KEY

login_manager.init_app(app)
login_manager.login_view = "auth.login"

app.register_blueprint(auth_bp)
app.register_blueprint(panel_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(comercial_bp)
app.register_blueprint(calado_bp)
app.register_blueprint(muestreo_bp)
app.register_blueprint(permissions_bp)
app.register_blueprint(silo_bp)
app.register_blueprint(auditoria_bp)
from permissions import tiene_permiso

@app.context_processor
def inject_permisos():
    return dict(tiene_permiso=tiene_permiso)
from flask_login import current_user
from panel.routes import empresa_actual
from db import get_db
from datetime import datetime


@app.context_processor
def inject_estado_contrato():

    empresa_alerta = None
    empresa_vencida = False

    if current_user.is_authenticated and not current_user.es_superadmin:

        conn = get_db()

        empresa = conn.execute("""
            SELECT fecha_vencimiento
            FROM empresas
            WHERE id=?
        """, (current_user.empresa_id,)).fetchone()

        conn.close()

        if empresa and empresa["fecha_vencimiento"]:

            fecha_venc = datetime.strptime(
                empresa["fecha_vencimiento"], "%Y-%m-%d"
            )

            hoy = datetime.now()
            dias_restantes = (fecha_venc - hoy).days

            # 🔴 Vencida
            if dias_restantes < 0:
                empresa_vencida = True

            # 🟡 7 días antes
            elif 0 < dias_restantes <= 7:
                empresa_alerta = empresa["fecha_vencimiento"]

    return dict(
        empresa_alerta=empresa_alerta,
        empresa_vencida=empresa_vencida
    )
@app.context_processor
def inject_empresa_contexto():

    empresa_nombre = None

    if current_user.is_authenticated and current_user.es_superadmin:
        empresa_id = empresa_actual()

        if empresa_id:
            conn = get_db()
            row = conn.execute(
                "SELECT nombre FROM empresas WHERE id=?",
                (empresa_id,)
            ).fetchone()
            conn.close()

            if row:
                empresa_nombre = row["nombre"]

    return dict(empresa_activa=empresa_nombre)
init_db()

if __name__ == "__main__":
    app.run(debug=True)
