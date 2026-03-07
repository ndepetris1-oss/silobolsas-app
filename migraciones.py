from db import get_db

def ejecutar_migraciones():

    conn = get_db()

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

    conn.commit()
    conn.close()