# ======================================================
# CALCULOS COMERCIALES – SILO BOLSA
# ======================================================

# ======================================================
# UTILIDADES GENERALES
# ======================================================

def _tas_tabla(tabla, temp, hum):
    if temp is None or hum is None:
        return None
    t = min(tabla.keys(), key=lambda x: abs(x - temp))
    h = min(tabla[t].keys(), key=lambda x: abs(x - hum))
    return tabla[t][h]


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
# AVENA / CENTENO (mismo esquema comercial)
# ======================================================

def grado_avena(d):
    if d["danados"] > 6 or d["quebrados"] > 7:
        return None
    if d["danados"] > 4 or d["quebrados"] > 5:
        return 3
    if d["danados"] > 2 or d["quebrados"] > 3:
        return 2
    return 1


def factor_avena(d):
    f = 1.0
    f -= d.get("danados", 0) * 0.01
    f -= d.get("quebrados", 0) * 0.005
    f -= d.get("olor", 0) / 100
    return round(max(f, 0), 4)


def grado_centeno(d):
    if d["danados"] > 6 or d["quebrados"] > 7:
        return None
    if d["danados"] > 4 or d["quebrados"] > 5:
        return 3
    if d["danados"] > 2 or d["quebrados"] > 3:
        return 2
    return 1


def factor_centeno(d):
    return factor_trigo(d)


# ======================================================
# CEBADA
# ======================================================

def cumple_cebada_cervecera(d):
    return (
        d.get("germinacion", 100) >= 95 and
        d["materia_extrana"] <= 1.0 and
        d["danados"] <= 1.5 and
        d["quebrados"] <= 4.0 and
        d["humedad"] <= 12.5
    )


def grado_cebada_cervecera(d):
    return 1


def factor_cebada_cervecera(d):
    f = 1.0
    if d["humedad"] > 12:
        f -= (d["humedad"] - 12) * 0.012
    return round(max(f, 0), 4)


def grado_cebada_forrajera(d):
    if d["danados"] > 3 or d["quebrados"] > 8:
        return 3
    if d["danados"] > 2 or d["quebrados"] > 6:
        return 2
    return 1


def factor_cebada_forrajera(d):
    f = 1.0
    f -= d.get("danados", 0) * 0.01
    f -= d.get("quebrados", 0) * 0.005
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
        f -= (q - 20) * 0.0025
    f -= d.get("olor", 0) / 100
    f -= d.get("moho", 0) / 100
    return round(max(f, 0), 4)


# ======================================================
# GIRASOL / COLZA
# ======================================================

def factor_girasol(d):
    f = 1.0
    if d["materia_extrana"] > 0:
        f -= d["materia_extrana"] * 0.01
    semillas = d.get("chamico", 0)
    if semillas:
        f -= semillas * 0.0012
    return round(max(f, 0), 4)


# ======================================================
# TAS – TABLAS
# ======================================================

TAS_CEREALES_INVIERNO = {
    40:{24:1,22:1,20:2,18:2,16:3,14:4},
    35:{24:1,22:4,20:10,18:13,16:17,14:25},
    30:{24:1,22:5,20:11,18:15,16:21,14:30},
    25:{24:1,22:7,20:12,18:18,16:35,14:40},
    20:{24:3,22:8,20:13,18:30,16:54,14:80},
    15:{24:8,22:10,20:20,18:41,16:56,14:105},
    10:{24:10,22:15,20:29,18:50,16:100,14:200},
    5:{24:13,22:20,20:36,18:73,16:180,14:250}
}

TAS_SOJA = {
    24:{40:1,35:1,30:1,25:1,20:3,15:8,10:10,5:13},
    22:{40:1,35:4,30:5,25:7,20:8,15:10,10:15,5:20},
    20:{40:2,35:10,30:11,25:12,20:13,15:20,10:29,5:36},
    18:{40:2,35:13,30:15,25:18,20:30,15:41,10:50,5:73},
    16:{40:3,35:17,30:21,25:36,20:54,15:56,10:100,5:180},
    14:{40:4,35:25,30:30,25:40,20:80,15:105,10:200,5:250},
}

TAS_COLZA_GIRASOL = {
    17.0:{25:4,20:4,15:6,10:11,5:20},
    15.6:{25:4,20:6,15:6,10:11,5:28},
    13.7:{25:4,20:6,15:11,10:20,5:46},
    12.3:{25:8,20:6,15:18,10:25,5:109},
    10.6:{25:11,20:18,15:42,10:42,5:238},
    8.9:{25:23,20:48,15:116,10:279,5:300},
    6.7:{25:29,20:180,15:300,10:300,5:300},
}


def tas_cereales_invierno(d):
    return _tas_tabla(TAS_CEREALES_INVIERNO, d["temperatura"], d["humedad"])


def tas_soja(d):
    return _tas_tabla(TAS_SOJA, d["temperatura"], d["humedad"])


def tas_colza_girasol(d):
    return _tas_tabla(TAS_COLZA_GIRASOL, d["temperatura"], d["humedad"])
