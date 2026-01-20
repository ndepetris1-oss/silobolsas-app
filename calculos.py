# ======================================================
# CALCULOS COMERCIALES – SILO BOLSA
# ======================================================


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

    if d["danados"] > 8:
        f -= (d["danados"] - 8) * 0.01

    if d["quebrados"] > 5:
        f -= (d["quebrados"] - 5) * 0.0025

    if d["materia_extrana"] > 2:
        f -= (d["materia_extrana"] - 2) * 0.01

    if d.get("ph") is not None and d["ph"] < 69:
        f -= (69 - d["ph"]) * 0.01

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

    if d.get("ph") is not None and d["ph"] < 73:
        f -= (73 - d["ph"]) * 0.02

    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# SOJA
# ======================================================

def factor_soja(d):
    f = 1.0

    if d["materia_extrana"] > 1:
        tramo1 = min(d["materia_extrana"], 3) - 1
        f -= tramo1 * 0.01
    if d["materia_extrana"] > 3:
        f -= (d["materia_extrana"] - 3) * 0.015

    if d["danados"] > 5:
        f -= (d["danados"] - 5) * 0.01

    q = d["quebrados"]
    if q > 20:
        if q <= 25:
            f -= (q - 20) * 0.0025
        elif q <= 30:
            f -= (5 * 0.0025) + (q - 25) * 0.005
        else:
            f -= (5 * 0.0025) + (5 * 0.005) + (q - 30) * 0.0075

    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# GIRASOL
# ======================================================

def factor_girasol(d):
    f = 1.0

    if d.get("grasa") is not None:
        f += (d["grasa"] - 42) * 0.02

    if d["materia_extrana"] > 0:
        tramo1 = min(d["materia_extrana"], 3)
        f -= tramo1 * 0.01
    if d["materia_extrana"] > 3:
        f -= (d["materia_extrana"] - 3) * 0.015

    semillas = d.get("chamico", 0)
    if semillas > 0:
        f -= semillas * 0.0012

    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100

    return round(max(f, 0), 4)


# ======================================================
# TAS – MAÍZ / TRIGO
# ======================================================

TAS_MAIZ = {
    40:{24:1,22:3,20:4,18:9,16:17,14:27},
    35:{24:2,22:3,20:5,18:11,16:19,14:32},
    30:{24:2,22:4,20:7,18:15,16:23,14:48},
    25:{24:4,22:7,20:12,18:28,16:45,14:90},
    20:{24:8,22:12,20:22,18:49,16:80,14:170},
    15:{24:16,22:22,20:39,18:85,16:160,14:320},
    10:{24:26,22:35,20:60,18:140,16:265,14:500},
    5:{24:50,22:90,20:150,18:350,16:650,14:1000}
}

TAS_TRIGO = {
    40:{24:1,22:1,20:2,18:2,16:3,14:4},
    35:{24:1,22:4,20:10,18:13,16:17,14:25},
    30:{24:1,22:5,20:11,18:15,16:21,14:30},
    25:{24:1,22:7,20:12,18:18,16:35,14:40},
    20:{24:3,22:8,20:13,18:30,16:54,14:80},
    15:{24:8,22:10,20:20,18:41,16:56,14:105},
    10:{24:10,22:15,20:29,18:50,16:100,14:200},
    5:{24:13,22:20,20:36,18:73,16:180,14:250}
}


def _calcular_tas(tabla, temp, hum):
    if temp is None or hum is None:
        return None
    t = min(tabla.keys(), key=lambda x: abs(x - temp))
    h = min(tabla[t].keys(), key=lambda x: abs(x - hum))
    return tabla[t][h]


def tas_maiz(d):
    return _calcular_tas(TAS_MAIZ, d["temperatura"], d["humedad"])


def tas_trigo(d):
    return _calcular_tas(TAS_TRIGO, d["temperatura"], d["humedad"])
