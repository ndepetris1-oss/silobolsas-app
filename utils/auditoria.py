# utils/auditoria.py
from utils.fechas import ahora_completo

ACCIONES = {
    "registro_silo":     "🌾 Registró silo",
    "extraccion":        "📦 Marcó extracción",
    "calado":            "🧪 Registró calado",
    "evento_monitoreo":  "📸 Cargó evento",
    "resolucion_evento": "✅ Resolvió evento",
    "llenado":           "🌽 Cargó llenado",
    "analisis":          "🔬 Cargó análisis",
    "exportacion_excel": "📥 Exportó Excel",
    "inicio_extraccion": "🚛 Inició extracción",
    "cierre_extraccion": "✔ Cerró extracción",
    "camionada_vaciado": "🚛 Registró camionada",
    "completar_camionada": "📋 Completó camionada (lab)",
    "eliminar_camionada": "🗑️ Eliminó camionada",
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
            ahora_completo()
        ))
    except Exception as e:
        print(f"Error auditoría: {e}")
