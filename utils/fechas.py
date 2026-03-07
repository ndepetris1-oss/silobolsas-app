from datetime import datetime
from zoneinfo import ZoneInfo

def normalizar_fecha(valor):

    if not valor:
        return None

    if isinstance(valor, str):
        return datetime.fromisoformat(valor)

    return valor


def fecha_argentina(valor):

    dt = normalizar_fecha(valor)

    if not dt:
        return None

    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt = dt.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))

    return dt.strftime("%d/%m/%Y %H:%M")