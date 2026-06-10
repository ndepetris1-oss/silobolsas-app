from db import get_db

conn = get_db()

print("=== Cereales en mercado ===")
rows = conn.execute("SELECT empresa_id, cereal FROM mercado ORDER BY empresa_id, cereal").fetchall()
for r in rows:
    print(f"  Empresa {r['empresa_id']}: {r['cereal']}")

print("\n=== Agregando Sorgo si falta ===")
empresas = conn.execute("SELECT id, nombre FROM empresas").fetchall()
for e in empresas:
    existe = conn.execute(
        "SELECT id FROM mercado WHERE empresa_id=? AND cereal=?",
        (e["id"], "Sorgo")
    ).fetchone()
    if not existe:
        conn.execute(
            "INSERT INTO mercado (empresa_id, cereal) VALUES (?,?)",
            (e["id"], "Sorgo")
        )
        print(f"✅ Sorgo agregado a empresa: {e['nombre']} (id={e['id']})")
    else:
        print(f"⚠ {e['nombre']} ya tiene Sorgo")

conn.commit()
conn.close()
print("\n✅ Listo")
