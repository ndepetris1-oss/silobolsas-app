from db import get_db
from werkzeug.security import generate_password_hash

def init_db():
    conn = get_db()
    c = conn.cursor()

    # =====================
    # EMPRESAS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            fecha_alta TEXT NOT NULL,
            tipo_contrato TEXT,
            fecha_vencimiento TEXT,
            activa INTEGER DEFAULT 1
        )
    """)
    
    # =====================
    # SUCURSALES
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS sucursales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)

    # =====================
    # USUARIOS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            empresa_id INTEGER,
            sucursal_id INTEGER,
            es_superadmin INTEGER DEFAULT 0,
            forzar_cambio_password INTEGER DEFAULT 0,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            FOREIGN KEY (sucursal_id) REFERENCES sucursales(id)
        )
    """)

    # =====================
    # PERMISOS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS permisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pantalla TEXT
        )
    """)
    # =====================
    # SOLICITUDES
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pantalla TEXT,
            fecha TEXT,
            estado TEXT DEFAULT 'pendiente'
        )
    """)

    # =====================
    # SILOS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS silos (
            numero_qr TEXT NOT NULL,
            empresa_id INTEGER NOT NULL,
            sucursal_id INTEGER NOT NULL,
            cereal TEXT,
            estado_grano TEXT,
            estado_silo TEXT,
            metros INTEGER,
            lat REAL,
            lon REAL,
            fecha_confeccion TEXT,
            fecha_extraccion TEXT,
            PRIMARY KEY (numero_qr, empresa_id)
        )
    """)          

    # =====================
    # MUESTREOS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS muestreos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT,
            empresa_id INTEGER NOT NULL,
            fecha_muestreo TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)

    # =====================
    # ANALISIS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS analisis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_muestreo INTEGER,
            empresa_id INTEGER NOT NULL,
            seccion TEXT,
            temperatura REAL,
            humedad REAL,
            ph REAL,
            danados REAL,
            quebrados REAL,
            materia_extrana REAL,
            olor REAL,
            moho REAL,
            insectos INTEGER,
            chamico REAL,
            grado INTEGER,
            factor REAL,
            tas INTEGER,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)

    # =====================
    # MONITOREOS
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS monitoreos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_qr TEXT,
            empresa_id INTEGER NOT NULL,
            fecha_evento TEXT,
            tipo TEXT,
            detalle TEXT,
            foto_evento TEXT,
            resuelto INTEGER DEFAULT 0,
            fecha_resolucion TEXT,
            foto_resolucion TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)
    # =====================
    # MERCADO (COMERCIAL)
    # =====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS mercado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            cereal TEXT,
            pizarra_auto REAL,
            fuente TEXT,
            fecha_fuente TEXT,
            pizarra_manual REAL,
            usar_manual INTEGER DEFAULT 0,
            obs_precio TEXT,
            dolar REAL,
            fecha TEXT,
            UNIQUE(empresa_id, cereal),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER,
        fecha_pago TEXT,
        monto REAL,
        silos_cobrados INTEGER,
        periodo TEXT,
        observacion TEXT,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rofex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        posicion TEXT NOT NULL,
        ajuste REAL,
        ajuste_anterior REAL,
        variacion REAL,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS matba (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        posicion TEXT NOT NULL,
        cereal TEXT,
        precio REAL,
        precio_anterior REAL,
        variacion REAL,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # =====================
    # SUPERADMIN
    # =====================
    c.execute("""
        INSERT OR IGNORE INTO usuarios (
            username,
            password,
            rol,
            es_superadmin
        )
        VALUES (?,?,?,1)
    """, (
    "superadmin",
    generate_password_hash("Super123"),
    "superadmin"
    ))

    conn.commit()
    conn.close()
