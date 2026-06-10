from flask_login import UserMixin
from db import get_db


class User(UserMixin):

    def __init__(self, row):
        # Convertir a dict para acceso seguro
        if hasattr(row, 'keys'):
            data = dict(row)
        else:
            data = row

        # Flask-Login usa get_id() que por defecto retorna self.id
        # Usamos _id interno para evitar conflicto con UserMixin
        self._id = data.get("id")
        self.username = data.get("username")
        self.rol = data.get("rol")
        self.empresa_id = data.get("empresa_id")
        self.sucursal_id = data.get("sucursal_id")
        self.es_superadmin = data.get("es_superadmin")
        self.forzar_cambio_password = data.get("forzar_cambio_password", 0)

    def get_id(self):
        return str(self._id)

    @property
    def id(self):
        return self._id

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
