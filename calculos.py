# ======================
# CALCULOS COMERCIALES – SILO BOLSA
# Criterio: castigo SOLO al superar límite de GRADO 3
# Olor / Moho: arbitraje directo
# ======================


# ======================================================
# MAÍZ
# ======================================================

def grado_maiz(d):
    if d.get("ph") is not None and d["ph"] < 69:
        return None
    if d["danados"] > 8 or d["quebrados"] > 5 or d["materia_extrana"] > 2:
        return None
    if d["danados"] > 5 or d["quebrados"] > 3 or d["materia_extrana"] > 1.5:
        return 3
    if d["danados"] > 3 or d["quebrados"] > 2 or d["materia_extrana"] > 1:
        return 2
    return 1


def factor_maiz(d):
    f = 1.0

    # Castigos SOLO si supera límite G3
    if d["danados"] > 8:
        f -= (d["danados"] - 8) * 0.01

    if d["quebrados"] > 5:
        f -= (d["quebrados"] - 5) * 0.0025

    if d["materia_extrana"] > 2:
        f -= (d["materia_extrana"] - 2) * 0.01

    # PH
    if d.get("ph") is not None and d["ph"] < 69:
        f -= (69 - d["ph"]) * 0.01

    # Arbitrajes
    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# TRIGO
# ======================================================

def grado_trigo(d):
    if d.get("ph") is not None and d["ph"] < 73:
        return None
    if d["materia_extrana"] > 1.5 or d["danados"] > 3 or d["quebrados"] > 2:
        return None
    if d["materia_extrana"] > 0.8 or d["danados"] > 2 or d["quebrados"] > 1.2:
        return 3
    if d["materia_extrana"] > 0.2 or d["danados"] > 1 or d["quebrados"] > 0.5:
        return 2
    return 1


def factor_trigo(d):
    f = 1.0

    if d["materia_extrana"] > 1.5:
        f -= (d["materia_extrana"] - 1.5) * 0.01

    if d["danados"] > 3:
        f -= (d["danados"] - 3) * 0.01

    if d["quebrados"] > 2:
        f -= (d["quebrados"] - 2) * 0.005

    # PH
    if d.get("ph") is not None and d["ph"] < 73:
        f -= (73 - d["ph"]) * 0.02

    # Arbitrajes
    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# SOJA
# ======================================================

def factor_soja(d):
    f = 1.0

    # Materia extraña (coeficiente escalonado)
    if d["materia_extrana"] > 1:
        tramo1 = min(d["materia_extrana"], 3) - 1
        f -= tramo1 * 0.01
    if d["materia_extrana"] > 3:
        tramo2 = d["materia_extrana"] - 3
        f -= tramo2 * 0.015

    # Dañados
    if d["danados"] > 5:
        f -= (d["danados"] - 5) * 0.01

    # Quebrados / partidos (coeficiente progresivo)
    q = d["quebrados"]
    if q > 20:
        if q <= 25:
            f -= (q - 20) * 0.0025
        elif q <= 30:
            f -= (5 * 0.0025) + (q - 25) * 0.005
        else:
            f -= (5 * 0.0025) + (5 * 0.005) + (q - 30) * 0.0075

    # Arbitrajes
    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# GIRASOL
# ======================================================

def factor_girasol(d):
    f = 1.0

    # Materia grasa
    if d.get("grasa") is not None:
        f += (d["grasa"] - 42) * 0.02

    # Materias extrañas
    if d["materia_extrana"] > 0:
        tramo1 = min(d["materia_extrana"], 3)
        f -= tramo1 * 0.01
    if d["materia_extrana"] > 3:
        f -= (d["materia_extrana"] - 3) * 0.015

    # Chamico (semillas cada 100 g)
    semillas = d.get("chamico", 0)
    if semillas > 0:
        f -= semillas * 0.0012  # 0.12 % por semilla

    # Arbitrajes
    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)
