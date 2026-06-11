from db import get_db
import os

def ejecutar_migraciones():

    conn = get_db()
    es_postgres = os.environ.get("DATABASE_URL") is not None

    # ==========================
    # ANALISIS
    # ==========================

    columnas_analisis = [
        ("granos_carbon", "REAL"),
    ]

    for nombre, tipo in columnas_analisis:
        try:
            conn.execute(f"ALTER TABLE analisis ADD COLUMN {nombre} {tipo}")
            print(f"Migración aplicada: analisis.{nombre}")
        except:
            pass

    # ==========================
    # MATBA
    # ==========================

    columnas_matba = [
        ("mes", "TEXT")
    ]

    for nombre, tipo in columnas_matba:
        try:
            conn.execute(f"ALTER TABLE matba ADD COLUMN {nombre} {tipo}")
            print(f"Migración aplicada: matba.{nombre}")
        except:
            pass

    # ==========================
    # SILOS — columnas de extraccion
    # ==========================

    for col in ["fecha_inicio_extraccion", "fecha_extraccion"]:
        try:
            conn.execute(f"ALTER TABLE silos ADD COLUMN {col} TEXT")
            conn.commit()
            print(f"Migración aplicada: silos.{col}")
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass

    # ==========================
    # VACIADO — crear tabla
    # ==========================

    if es_postgres:
        sql_vaciado = """
            CREATE TABLE IF NOT EXISTS vaciado (
                id SERIAL PRIMARY KEY,
                numero_qr TEXT NOT NULL,
                empresa_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                kg REAL,
                humedad REAL,
                factor REAL,
                tas INTEGER,
                insectos INTEGER DEFAULT 0,
                destino TEXT,
                sub_destino TEXT,
                nro_camion TEXT,
                patente TEXT,
                obs TEXT,
                FOREIGN KEY (empresa_id) REFERENCES empresas(id)
            )
        """
    else:
        sql_vaciado = """
            CREATE TABLE IF NOT EXISTS vaciado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_qr TEXT NOT NULL,
                empresa_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                kg REAL,
                humedad REAL,
                factor REAL,
                tas INTEGER,
                insectos INTEGER DEFAULT 0,
                destino TEXT,
                sub_destino TEXT,
                nro_camion TEXT,
                patente TEXT,
                obs TEXT,
                FOREIGN KEY (empresa_id) REFERENCES empresas(id)
            )
        """

    try:
        conn.execute(sql_vaciado)
        conn.commit()
        print("Migración aplicada: tabla vaciado")
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        print(f"vaciado ya existe o error: {e}")

    # ==========================
    # VACIADO — agregar columna patente
    # ==========================

    try:
        conn.execute("ALTER TABLE vaciado ADD COLUMN patente TEXT")
        conn.commit()
        print("Migración aplicada: vaciado.patente")
    except:
        try:
            conn.rollback()
        except:
            pass

    # ==========================
    # VACIADO — quitar NOT NULL de destino
    # (solo SQLite: recrear tabla si tiene constraint)
    # ==========================

    if not es_postgres:
        try:
            # Intentar insertar NULL en destino para ver si hay constraint
            conn.execute("INSERT INTO vaciado (numero_qr, empresa_id, fecha, destino) VALUES ('__test__', -1, '__test__', NULL)")
            # Si llega acá, no hay NOT NULL → borrar la fila de prueba
            conn.execute("DELETE FROM vaciado WHERE numero_qr = '__test__' AND empresa_id = -1")
        except:
            try:
                conn.rollback()
            except:
                pass
            # Hay NOT NULL en destino → recrear tabla
            try:
                print("Recreando tabla vaciado (quitando NOT NULL de destino)...")
                conn.execute("""
                    CREATE TABLE vaciado_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        numero_qr TEXT NOT NULL,
                        empresa_id INTEGER NOT NULL,
                        fecha TEXT NOT NULL,
                        kg REAL,
                        humedad REAL,
                        factor REAL,
                        tas INTEGER,
                        insectos INTEGER DEFAULT 0,
                        destino TEXT,
                        sub_destino TEXT,
                        nro_camion TEXT,
                        patente TEXT,
                        obs TEXT,
                        FOREIGN KEY (empresa_id) REFERENCES empresas(id)
                    )
                """)
                conn.execute("""
                    INSERT INTO vaciado_new
                        (id, numero_qr, empresa_id, fecha, kg, humedad, factor, tas,
                         insectos, destino, sub_destino, nro_camion, patente, obs)
                    SELECT id, numero_qr, empresa_id, fecha, kg, humedad, factor, tas,
                         insectos, destino, sub_destino, nro_camion, patente, obs
                    FROM vaciado
                """)
                conn.execute("DROP TABLE vaciado")
                conn.execute("ALTER TABLE vaciado_new RENAME TO vaciado")
                print("Migración aplicada: destino ahora es nullable")
            except Exception as e:
                try:
                    conn.rollback()
                except:
                    pass
                print(f"Error recreando tabla vaciado: {e}")
    else:
        # PostgreSQL: ALTER COLUMN es más simple
        try:
            conn.execute("ALTER TABLE vaciado ALTER COLUMN destino DROP NOT NULL")
            print("Migración aplicada: destino ahora es nullable (Postgres)")
        except:
            try:
                conn.rollback()
            except:
                pass

    # ==========================
    # VACIADO — columnas de calidad
    # ==========================
    columnas_vaciado = [
        ("temperatura", "REAL"),
        ("materia_extrana", "REAL"),
        ("danados", "REAL"),
        ("quebrados", "REAL"),
        ("ph", "REAL"),
        ("chamico", "REAL"),
        ("materia_grasa", "REAL"),
        ("acidez", "REAL"),
        ("proteinas", "REAL"),
        ("granos_picados", "REAL"),
        ("olor", "REAL"),
        ("moho", "REAL"),
    ]
    for nombre, tipo in columnas_vaciado:
        try:
            conn.execute(f"ALTER TABLE vaciado ADD COLUMN {nombre} {tipo}")
            conn.commit()
            print(f"Migración aplicada: vaciado.{nombre}")
        except:
            try:
                conn.rollback()
            except:
                pass

    # ==========================
    # VACIADO — columnas completado y nro_camion
    # ==========================
    for col_v, def_v in [("completado", "INTEGER DEFAULT 0"), ("nro_camion", "INTEGER DEFAULT 0")]:
        try:
            conn.execute(f"ALTER TABLE vaciado ADD COLUMN {col_v} {def_v}")
            conn.commit()
            print(f"Migración aplicada: vaciado.{col_v}")
        except:
            try:
                conn.rollback()
            except:
                pass

    conn.commit()
    conn.close()
