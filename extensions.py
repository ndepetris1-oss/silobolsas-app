from flask_login import LoginManager
from db import get_db
from auth.models import User

login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    u = conn.execute(
        "SELECT * FROM usuarios WHERE id=?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not u:
        return None

    return User(
        u["id"],
        u["username"],
        u["rol"],
        u["empresa_id"],
        u["sucursal_id"],
        u["es_superadmin"]
    )
