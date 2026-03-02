from flask_login import UserMixin
from db import get_db


class User(UserMixin):

    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.rol = row["rol"]
        self.empresa_id = row["empresa_id"]
        self.sucursal_id = row["sucursal_id"]
        self.es_superadmin = row["es_superadmin"]  # 👈 MUY IMPORTANTE
        self.forzar_cambio_password = row["forzar_cambio_password"]
        
    @staticmethod
    def get(user_id):
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id=?",
            (user_id,)
        ).fetchone()
        conn.close()

        if row:
            return User(row)
        return None
