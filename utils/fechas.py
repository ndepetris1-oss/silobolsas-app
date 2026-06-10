from datetime import datetime
from zoneinfo import ZoneInfo

ARG = ZoneInfo("America/Argentina/Buenos_Aires")

def ahora():
    """Retorna la fecha y hora actual en Argentina (GMT-3) como string."""
    return datetime.now(ARG).strftime("%Y-%m-%d %H:%M")

def ahora_completo():
    """Retorna la fecha y hora actual en Argentina con segundos."""
    return datetime.now(ARG).strftime("%Y-%m-%d %H:%M:%S")

def normalizar_fecha(valor):
    if not valor:
        return None
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor)
        except:
            return None
    return valor

def fecha_argentina(valor):
    """Convierte una fecha UTC a formato legible en Argentina."""
    dt = normalizar_fecha(valor)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt = dt.astimezone(ARG)
    return dt.strftime("%d/%m/%Y %H:%M")
