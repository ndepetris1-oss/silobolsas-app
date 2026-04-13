# utils/auditoria.py — función helper para registrar eventos
from db import get_db
from datetime import datetime

ACCIONES = {
    "registro_silo":     "🌾 Registró silo",
    "extraccion":        "📦 Marcó extracción",
    "calado":            "🧪 Registró calado",
    "evento_monitoreo":  "📸 Cargó evento",
    "resolucion_evento": "✅ Resolvió evento",
    "llenado":           "🌽 Cargó llenado",
    "analisis":          "🔬 Cargó análisis",
    "exportacion_excel": "📥 Exportó Excel",
}

def registrar_auditoria(conn, user_id, empresa_id, accion, detalle=None, numero_qr=None):
    try:
        conn.execute("""
            INSERT INTO auditoria (
                user_id, empresa_id, accion, detalle, numero_qr, fecha
            ) VALUES (?,?,?,?,?,?)
        """, (
            user_id,
            empresa_id,
            accion,
            detalle,
            numero_qr,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    except Exception as e:
        # No romper la app si falla la auditoría
        print(f"Error auditoría: {e}")
