import psycopg2

DATABASE_URL = "postgresql://silobolsas:nkiC8dNebSzuS32boInsBzqDFcqelPcO@dpg-d6lecq15pdvs73ddubbg-a.oregon-postgres.render.com/silobolsas"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT id, nombre FROM empresas WHERE activa = 1")
empresas = cur.fetchall()

for empresa_id, nombre in empresas:
    cur.execute(
        "SELECT id FROM mercado WHERE empresa_id = %s AND cereal = 'Sorgo'",
        (empresa_id,)
    )
    existe = cur.fetchone()

    if not existe:
        cur.execute(
            "INSERT INTO mercado (empresa_id, cereal) VALUES (%s, %s)",
            (empresa_id, "Sorgo")
        )
        print(f"✅ Sorgo agregado a empresa: {nombre} (id={empresa_id})")
    else:
        print(f"⚠ {nombre} ya tiene Sorgo")

conn.commit()
cur.close()
conn.close()
print("\n✅ Listo")
