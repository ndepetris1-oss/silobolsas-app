# ======================================================
# CALCULOS COMERCIALES – SILO BOLSA
# ======================================================

# ======================================================
# UTILIDADES TAS
# ======================================================
def v(d, k):
    """Devuelve 0 si el valor es None"""
    return d.get(k) or 0
    
def _tas_tabla_temp_hum(tabla, temp, hum):
    """
    TABLA[TEMPERATURA][HUMEDAD]
    (Trigo)
    """
    if temp is None or hum is None:
        return None
    t = min(tabla.keys(), key=lambda x: abs(x - temp))
    h = min(tabla[t].keys(), key=lambda x: abs(x - hum))
    return tabla[t][h]


def _tas_tabla_hum_temp(tabla, temp, hum):
    """
    TABLA[HUMEDAD][TEMPERATURA]
    (Maíz, Soja, Girasol, Colza)
    """
    if temp is None or hum is None:
        return None
    h = min(tabla.keys(), key=lambda x: abs(x - hum))
    t = min(tabla[h].keys(), key=lambda x: abs(x - temp))
    return tabla[h][t]


def normalizar_grado(grado, usa_grado=True):
    """
    - Cereales con grado: None → 'F/E'
    - Cereales sin grado: siempre None
    """
    if not usa_grado:
        return None
    return grado if grado is not None else "F/E"


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
    return round(max(f, 0), 4)


# ======================================================
# SOJA (SIN GRADO)
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
    return round(max(f, 0), 4)


# ======================================================
# GIRASOL / COLZA (SIN GRADO)
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

TAS_MAIZ = {
    24:{40:1,35:2,30:2,25:4,20:8,15:16,10:26,5:50},
    22:{40:3,35:3,30:4,25:7,20:12,15:22,10:35,5:90},
    20:{40:4,35:5,30:7,25:12,20:22,15:39,10:60,5:150},
    18:{40:9,35:11,30:15,25:28,20:49,15:85,10:140,5:350},
    16:{40:17,35:17,30:23,25:45,20:80,15:160,10:265,5:650},
    14:{40:27,35:32,30:48,25:90,20:170,15:320,10:500,5:1000},
}

TAS_TRIGO = {
    40:{24:1,22:1,20:2,18:2,16:3,14:4},
    35:{24:1,22:4,20:10,18:13,16:17,14:25},
    30:{24:1,22:5,20:11,18:15,16:21,14:30},
    25:{24:1,22:7,20:12,18:18,16:35,14:40},
    20:{24:3,22:8,20:13,18:30,16:54,14:80},
    15:{24:8,22:10,20:20,18:41,16:56,14:105},
    10:{24:10,22:15,20:29,18:50,16:100,14:200},
    5:{24:13,22:20,20:36,18:73,16:180,14:250},
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


# ======================================================
# TAS – FUNCIONES
# ======================================================

def tas_maiz(d):
    return _tas_tabla_hum_temp(TAS_MAIZ, d["temperatura"], d["humedad"])


def tas_trigo(d):
    return _tas_tabla_temp_hum(TAS_TRIGO, d["temperatura"], d["humedad"])


def tas_soja(d):
    return _tas_tabla_hum_temp(TAS_SOJA, d["temperatura"], d["humedad"])


def tas_colza_girasol(d):
    return _tas_tabla_hum_temp(TAS_COLZA_GIRASOL, d["temperatura"], d["humedad"])


# ======================================================
# SELECTOR FINAL (LO QUE USA EL FORM)
# ======================================================

def calcular_comercial(cereal, d):

    if cereal == "Maíz":
        g = grado_maiz(d)
        grado = normalizar_grado(g, usa_grado=True)
        factor = factor_maiz(d)
        tas = tas_maiz(d)

    elif cereal == "Trigo":
        g = grado_trigo(d)
        grado = normalizar_grado(g, usa_grado=True)
        factor = factor_trigo(d)
        tas = tas_trigo(d)

    elif cereal == "Soja":
        grado = None
        factor = factor_soja(d)
        tas = tas_soja(d)

    elif cereal in ("Girasol", "Colza"):
        grado = None
        factor = factor_girasol(d)
        tas = tas_colza_girasol(d)

    else:
        raise ValueError(f"Cereal no soportado: {cereal}")

    return {
        "grado": grado,
        "factor": factor,
        "tas": tas
    }
