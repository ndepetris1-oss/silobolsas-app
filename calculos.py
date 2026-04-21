
# ======================================================
# UTILIDADES TAS
# ======================================================

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
    if not usa_grado:
        return None
    return grado if grado is not None else "F/E"


# ======================================================
# MAÍZ
# ======================================================

def grado_maiz(d):
    if d.get("ph") is not None and d["ph"] < 69:
        return None

    if (
        d.get("danados", 0) > 8
        or d.get("quebrados", 0) > 5
        or d.get("materia_extrana", 0) > 2
    ):
        return None

    if (
        d.get("danados", 0) > 5
        or d.get("quebrados", 0) > 3
        or d.get("materia_extrana", 0) > 1.5
    ):
        return 3

    if (
        d.get("danados", 0) > 3
        or d.get("quebrados", 0) > 2
        or d.get("materia_extrana", 0) > 1
    ):
        return 2

    return 1


def factor_maiz(d):
    f = 1.0

    if d.get("danados", 0) > 8:
        f -= (d["danados"] - 8) * 0.01

    if d.get("quebrados", 0) > 5:
        f -= (d["quebrados"] - 5) * 0.0025

    if d.get("materia_extrana", 0) > 2:
        f -= (d["materia_extrana"] - 2) * 0.01

    if d.get("ph") is not None and d["ph"] < 69:
        f -= (69 - d["ph"]) * 0.01

    # ===== ARBITRAJES DIRECTOS =====
    olor = d.get("olor") or 0
    moho = d.get("moho") or 0
    f -= (olor + moho) / 100

    return round(max(f, 0), 4)


# ======================================================
# TRIGO
# ======================================================

def grado_trigo(d):
    if d.get("ph") is not None and d["ph"] < 73:
        return None

    if (
        d.get("materia_extrana", 0) > 1.5
        or d.get("danados", 0) > 3
        or d.get("quebrados", 0) > 2
    ):
        return None

    if (
        d.get("materia_extrana", 0) > 0.8
        or d.get("danados", 0) > 2
        or d.get("quebrados", 0) > 1.2
    ):
        return 3

    if (
        d.get("materia_extrana", 0) > 0.2
        or d.get("danados", 0) > 1
        or d.get("quebrados", 0) > 0.5
    ):
        return 2

    return 1


def factor_trigo(d):
    f = 1.0

    grado = grado_trigo(d)

    # ==============================
    # TOLERANCIAS SEGÚN GRADO
    # ==============================

    tolerancias = {
        1: {
            "materia_extrana": 0.20,
            "danados": 1.00,
            "granos_carbon": 0.10,
            "panza_blanca": 15,
            "quebrados": 0.50,
        },
        2: {
            "materia_extrana": 0.80,
            "danados": 2.00,
            "granos_carbon": 0.20,
            "panza_blanca": 25,
            "quebrados": 1.20,
        },
        3: {
            "materia_extrana": 1.50,
            "danados": 3.00,
            "granos_carbon": 0.30,
            "panza_blanca": 40,
            "quebrados": 2.00,
        }
    }

    if grado in tolerancias:
        tol = tolerancias[grado]

        for campo, limite in tol.items():
            valor = d.get(campo)
            if valor is not None and valor > limite:
                f -= (valor - limite) * 0.01

    # ==============================
    # ARBITRAJES DIRECTOS
    # ==============================

    f -= (d.get("olor") or 0) / 100
    f -= (d.get("punta_sombreada") or 0) / 100
    f -= (d.get("revolcado_tierra") or 0) / 100
    f -= (d.get("punta_negra") or 0) / 100

    # ==================================
    # PROTEÍNA (TRAMOS ACUMULATIVOS)
    # ==================================

    prote = d.get("proteinas")
    ph = d.get("ph")

    if prote is not None and ph is not None and ph >= 75:

        if prote < 11:

            descuento = 0

            # Tramo 11 → 10 (2% por punto)
            if prote < 10:
                descuento += 1 * 0.02
                tramo_2 = 10 - prote
            else:
                tramo_2 = 11 - prote

            if prote >= 10:
                descuento += (11 - prote) * 0.02

            # Tramo 10 → 9 (3% por punto)
            if prote < 10:
                if prote < 9:
                    descuento += 1 * 0.03
                    tramo_3 = 9 - prote
                else:
                    descuento += (10 - prote) * 0.03

            # Tramo < 9 (4% por punto)
            if prote < 9:
                descuento += (9 - prote) * 0.04

            f -= descuento

        elif prote > 11:
            # Bonificación simple proporcional
            f += (prote - 11) * 0.02

    return round(max(f, 0), 4)
# ======================================================
# SORGO
# ======================================================

def grado_sorgo(d):

    danados = d.get("danados") or 0
    materia_extrana = d.get("materia_extrana") or 0
    quebrados = d.get("quebrados") or 0
    granos_picados = d.get("granos_picados") or 0

    if (
        danados > 6
        or materia_extrana > 4
        or quebrados > 7
        or granos_picados > 1
    ):
        return None

    if (
        danados > 4
        or materia_extrana > 3
        or quebrados > 5
    ):
        return 3

    if (
        danados > 2
        or materia_extrana > 2
        or quebrados > 3
    ):
        return 2

    return 1

def factor_sorgo(d):

    f = 1.0

    danados = d.get("danados") or 0
    materia_extrana = d.get("materia_extrana") or 0
    quebrados = d.get("quebrados") or 0
    granos_picados = d.get("granos_picados") or 0
    olor = d.get("olor") or 0
    moho = d.get("moho") or 0
    chamico = d.get("chamico") or 0

    # =========================
    # DESCUENTO POR EXCEDENTE
    # =========================

    # Límites grado 3
    LIM_DANADOS = 6
    LIM_MEXT = 4
    LIM_QUEBRADOS = 7
    LIM_PICADOS = 1

    if danados > LIM_DANADOS:
        f -= (danados - LIM_DANADOS) * 0.01

    if materia_extrana > LIM_MEXT:
        f -= (materia_extrana - LIM_MEXT) * 0.01

    if quebrados > LIM_QUEBRADOS:
        f -= (quebrados - LIM_QUEBRADOS) * 0.005

    if granos_picados > LIM_PICADOS:
        f -= (granos_picados - LIM_PICADOS) * 0.01

    # =========================
    # OLOR
    # =========================
    f -= olor / 100

    # =========================
    # MOHO
    # =========================
    f -= moho / 100

    # =========================
    # CHAMICO (con tolerancia 2 semillas)
    # =========================

    if chamico >= 3:
        if 3 <= chamico <= 10:
            f -= 0.03
        elif 11 <= chamico <= 20:
            f -= 0.05
        elif 21 <= chamico <= 50:
            f -= 0.10
        elif 51 <= chamico <= 65:
            f -= 0.15
        elif 66 <= chamico <= 80:
            f -= 0.20
        elif 81 <= chamico <= 100:
            f -= 0.25
        elif chamico > 100:
            f -= 0.30

    return max(f, 0)

# ======================================================
# SOJA (SIN GRADO)
# ======================================================

def factor_soja(d):
    f = 1.0

    if d.get("materia_extrana", 0) > 1:
        tramo1 = min(d["materia_extrana"], 3) - 1
        f -= tramo1 * 0.01

    if d.get("materia_extrana", 0) > 3:
        f -= (d["materia_extrana"] - 3) * 0.015

    if d.get("danados", 0) > 5:
        f -= (d["danados"] - 5) * 0.01

    # ===== ARBITRAJES DIRECTOS =====
    olor = d.get("olor") or 0
    moho = d.get("moho") or 0
    f -= (olor + moho) / 100

    return round(max(f, 0), 4)


# ======================================================
# GIRASOL / COLZA (SIN GRADO)
# ======================================================

def factor_girasol(d):
    f = 1.0

    def to_float(x):
        try:
            return float(x)
        except:
            return None

    # =========================
    # MATERIA GRASA
    # =========================
    grasa = to_float(d.get("materia_grasa"))

    if grasa is not None:
        diferencia = grasa - 42
        f += diferencia * 0.02

    # =========================
    # ACIDEZ
    # =========================
    acidez = to_float(d.get("acidez"))

    if acidez is not None and acidez > 1.5:
        f -= (acidez - 1.5) * 0.025

    # =========================
    # MATERIA EXTRAÑA
    # =========================
    me = to_float(d.get("materia_extrana"))

    if me is not None and me > 0:
        if me <= 3:
            f -= me * 0.01
        else:
            f -= 3 * 0.01
            f -= (me - 3) * 0.015

    # =========================
    # CHAMICO
    # =========================
    chamico = to_float(d.get("chamico"))

    if chamico is not None and chamico > 0.25:
        f -= (chamico - 0.25) * 0.001

    # =========================
    # ARBITRAJES
    # =========================
    olor = to_float(d.get("olor")) or 0
    moho = to_float(d.get("moho")) or 0

    f -= olor / 100
    f -= moho / 100

    return round(max(f, 0), 4)

# ======================================================
# UTILIDADES TAS
# ======================================================

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
    if not usa_grado:
        return None
    return grado if grado is not None else "F/E"

# ======================================================
# TAS – TABLAS
# ======================================================

TAS_MAIZ = {
    24: {40: 1, 35: 2, 30: 2, 25: 4, 20: 8, 15: 16, 10: 26, 5: 50},
    22: {40: 3, 35: 3, 30: 4, 25: 7, 20: 12, 15: 22, 10: 35, 5: 90},
    20: {40: 4, 35: 5, 30: 7, 25: 12, 20: 22, 15: 39, 10: 60, 5: 150},
    18: {40: 9, 35: 11, 30: 15, 25: 28, 20: 49, 15: 85, 10: 140, 5: 350},
    16: {40: 17, 35: 17, 30: 23, 25: 45, 20: 80, 15: 160, 10: 265, 5: 650},
    14: {40: 27, 35: 32, 30: 48, 25: 90, 20: 170, 15: 320, 10: 500, 5: 1000},
}

TAS_TRIGO = {
    40: {24: 1, 22: 1, 20: 2, 18: 2, 16: 3, 14: 4},
    35: {24: 1, 22: 4, 20: 10, 18: 13, 16: 17, 14: 25},
    30: {24: 1, 22: 5, 20: 11, 18: 15, 16: 21, 14: 30},
    25: {24: 1, 22: 7, 20: 12, 18: 18, 16: 35, 14: 40},
    20: {24: 3, 22: 8, 20: 13, 18: 30, 16: 54, 14: 80},
    15: {24: 8, 22: 10, 20: 20, 18: 41, 16: 56, 14: 105},
    10: {24: 10, 22: 15, 20: 29, 18: 50, 16: 100, 14: 200},
    5: {24: 13, 22: 20, 20: 36, 18: 73, 16: 180, 14: 250},
}

TAS_SOJA = {
    24: {40: 1, 35: 1, 30: 1, 25: 1, 20: 3, 15: 8, 10: 10, 5: 13},
    22: {40: 1, 35: 4, 30: 5, 25: 7, 20: 8, 15: 10, 10: 15, 5: 20},
    20: {40: 2, 35: 10, 30: 11, 25: 12, 20: 13, 15: 20, 10: 29, 5: 36},
    18: {40: 2, 35: 13, 30: 15, 25: 18, 20: 30, 15: 41, 10: 50, 5: 73},
    16: {40: 3, 35: 17, 30: 21, 25: 36, 20: 54, 15: 56, 10: 100, 5: 180},
    14: {40: 4, 35: 25, 30: 30, 25: 40, 20: 80, 15: 105, 10: 200, 5: 250},
}

TAS_COLZA_GIRASOL = {
    17.0: {25: 4, 20: 4, 15: 6, 10: 11, 5: 20},
    15.6: {25: 4, 20: 6, 15: 6, 10: 11, 5: 28},
    13.7: {25: 4, 20: 6, 15: 11, 10: 20, 5: 46},
    12.3: {25: 8, 20: 6, 15: 18, 10: 25, 5: 109},
    10.6: {25: 11, 20: 18, 15: 42, 10: 42, 5: 238},
    8.9: {25: 23, 20: 48, 15: 116, 10: 279, 5: 300},
    6.7: {25: 29, 20: 180, 15: 300, 10: 300, 5: 300},
}


# ======================================================
# TAS – FUNCIONES
# ======================================================

def tas_maiz(d):
    return _tas_tabla_hum_temp(TAS_MAIZ, d.get("temperatura"), d.get("humedad"))

def tas_sorgo(d):
    # TEMPORAL: usar tabla de maíz
    return _tas_tabla_hum_temp(TAS_MAIZ, d.get("temperatura"), d.get("humedad"))


def tas_trigo(d):
    return _tas_tabla_temp_hum(TAS_TRIGO, d.get("temperatura"), d.get("humedad"))


def tas_soja(d):
    return _tas_tabla_hum_temp(TAS_SOJA, d.get("temperatura"), d.get("humedad"))


def tas_colza_girasol(d):
    return _tas_tabla_hum_temp(TAS_COLZA_GIRASOL, d.get("temperatura"), d.get("humedad"))


# ======================================================
# SELECTOR FINAL
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

    elif cereal == "Sorgo":
        g = grado_sorgo(d)
        grado = normalizar_grado(g, usa_grado=True)
        factor = factor_sorgo(d)
        tas = tas_sorgo(d)

    else:
        raise ValueError(f"Cereal no soportado: {cereal}")

    return {
        "grado": grado,
        "factor": factor,
        "tas": tas,
    }
    
# ======================================================
# MERMA MAÍZ – TABLA OFICIAL
# ======================================================

MERMA_MAIZ = {
    14.6: 1.27, 14.7: 1.39, 14.8: 1.50, 14.9: 1.62, 15.0: 1.73,
    15.1: 1.85, 15.2: 1.97, 15.3: 2.08, 15.4: 2.20, 15.5: 2.31,
    15.6: 2.43, 15.7: 2.54, 15.8: 2.66, 15.9: 2.77, 16.0: 2.89,
    16.1: 3.01, 16.2: 3.12, 16.3: 3.24, 16.4: 3.35, 16.5: 3.47,
    16.6: 3.58, 16.7: 3.70, 16.8: 3.82, 16.9: 3.93, 17.0: 4.05,
    17.1: 4.16, 17.2: 4.28, 17.3: 4.39, 17.4: 4.51, 17.5: 4.62,
    17.6: 4.74, 17.7: 4.86, 17.8: 4.97, 17.9: 5.09, 18.0: 5.20,
    18.1: 5.32, 18.2: 5.43, 18.3: 5.55, 18.4: 5.66, 18.5: 5.78,
    18.6: 5.90, 18.7: 6.01, 18.8: 6.13, 18.9: 6.24, 19.0: 6.36,
    19.1: 6.47, 19.2: 6.59, 19.3: 6.71, 19.4: 6.82, 19.5: 6.94,
    19.6: 7.05, 19.7: 7.17, 19.8: 7.28, 19.9: 7.40, 20.0: 7.51,
    20.1: 7.63, 20.2: 7.75, 20.3: 7.86, 20.4: 7.98, 20.5: 8.09,
    20.6: 8.21, 20.7: 8.32, 20.8: 8.44, 20.9: 8.55, 21.0: 8.67,
    21.1: 8.79, 21.2: 8.90, 21.3: 9.02, 21.4: 9.13, 21.5: 9.25,
    21.6: 9.36, 21.7: 9.48, 21.8: 9.60, 21.9: 9.71, 22.0: 9.83,
    22.1: 9.94, 22.2: 10.06, 22.3: 10.17, 22.4: 10.29, 22.5: 10.40,
    22.6: 10.52, 22.7: 10.64, 22.8: 10.75, 22.9: 10.87, 23.0: 10.98,
    23.1: 11.10, 23.2: 11.21, 23.3: 11.33, 23.4: 11.45, 23.5: 11.56,
    23.6: 11.68, 23.7: 11.79, 23.8: 11.91, 23.9: 12.02, 24.0: 12.14,
    24.1: 12.25, 24.2: 12.37, 24.3: 12.49, 24.4: 12.60, 24.5: 12.72,
    24.6: 12.83, 24.7: 12.95, 24.8: 13.06, 24.9: 13.18, 25.0: 13.29,
}
# ======================================================
# MERMA SOJA – TABLA OFICIAL
# ======================================================

MERMA_SOJA = {
    13.6: 0.69, 13.7: 0.80, 13.8: 0.92, 13.9: 1.03, 14.0: 1.15,
    14.1: 1.26, 14.2: 1.38, 14.3: 1.49, 14.4: 1.61, 14.5: 1.72,
    14.6: 1.84, 14.7: 1.95, 14.8: 2.07, 14.9: 2.18, 15.0: 2.30,
    15.1: 2.41, 15.2: 2.53, 15.3: 2.64, 15.4: 2.76, 15.5: 2.87,
    15.6: 2.99, 15.7: 3.10, 15.8: 3.22, 15.9: 3.33, 16.0: 3.45,
    16.1: 3.56, 16.2: 3.68, 16.3: 3.79, 16.4: 3.91, 16.5: 4.02,
    16.6: 4.14, 16.7: 4.25, 16.8: 4.37, 16.9: 4.48, 17.0: 4.60,
    17.1: 4.71, 17.2: 4.83, 17.3: 4.94, 17.4: 5.06, 17.5: 5.17,
    17.6: 5.29, 17.7: 5.40, 17.8: 5.52, 17.9: 5.63, 18.0: 5.75,
    18.1: 5.86, 18.2: 5.98, 18.3: 6.09, 18.4: 6.21, 18.5: 6.32,
    18.6: 6.44, 18.7: 6.55, 18.8: 6.67, 18.9: 6.78, 19.0: 6.90,
    19.1: 7.01, 19.2: 7.13, 19.3: 7.24, 19.4: 7.36, 19.5: 7.47,
    19.6: 7.59, 19.7: 7.70, 19.8: 7.82, 19.9: 7.93, 20.0: 8.05,
    20.1: 8.16, 20.2: 8.28, 20.3: 8.39, 20.4: 8.51, 20.5: 8.62,
    20.6: 8.74, 20.7: 8.85, 20.8: 8.97, 20.9: 9.08, 21.0: 9.20,
    21.1: 9.31, 21.2: 9.43, 21.3: 9.54, 21.4: 9.66, 21.5: 9.77,
    21.6: 9.89, 21.7: 10.00, 21.8: 10.11, 21.9: 10.23, 22.0: 10.34,
    22.1: 10.46, 22.2: 10.57, 22.3: 10.69, 22.4: 10.80, 22.5: 10.92,
    22.6: 11.03, 22.7: 11.15, 22.8: 11.26, 22.9: 11.38, 23.0: 11.49,
    23.1: 11.61, 23.2: 11.72, 23.3: 11.84, 23.4: 11.95, 23.5: 12.07,
    23.6: 12.18, 23.7: 12.30, 23.8: 12.41, 23.9: 12.53, 24.0: 12.64,
    24.1: 12.76, 24.2: 12.87, 24.3: 12.99, 24.4: 13.10, 24.5: 13.22,
    24.6: 13.33, 24.7: 13.45, 24.8: 13.56,
}
# ======================================================
# MERMA TRIGO – TABLA OFICIAL
# ======================================================

MERMA_TRIGO = {
    14.1: 0.69, 14.2: 0.81, 14.3: 0.92, 14.4: 1.04, 14.5: 1.16,
    14.6: 1.27, 14.7: 1.39, 14.8: 1.50, 14.9: 1.62, 15.0: 1.73,
    15.1: 1.85, 15.2: 1.97, 15.3: 2.08, 15.4: 2.20, 15.5: 2.31,
    15.6: 2.43, 15.7: 2.54, 15.8: 2.66, 15.9: 2.77, 16.0: 2.89,
    16.1: 3.01, 16.2: 3.12, 16.3: 3.24, 16.4: 3.35, 16.5: 3.47,
    16.6: 3.58, 16.7: 3.70, 16.8: 3.81, 16.9: 3.93, 17.0: 4.05,
    17.1: 4.16, 17.2: 4.28, 17.3: 4.39, 17.4: 4.51, 17.5: 4.62,
    17.6: 4.74, 17.7: 4.86, 17.8: 4.97, 17.9: 5.09, 18.0: 5.20,
    18.1: 5.32, 18.2: 5.43, 18.3: 5.55, 18.4: 5.66, 18.5: 5.78,
    18.6: 5.90, 18.7: 6.01, 18.8: 6.13, 18.9: 6.24, 19.0: 6.36,
    19.1: 6.47, 19.2: 6.59, 19.3: 6.71, 19.4: 6.82, 19.5: 6.94,
    19.6: 7.05, 19.7: 7.17, 19.8: 7.28, 19.9: 7.40, 20.0: 7.51,
    20.1: 7.63, 20.2: 7.75, 20.3: 7.86, 20.4: 7.98, 20.5: 8.09,
    20.6: 8.21, 20.7: 8.32, 20.8: 8.44, 20.9: 8.55, 21.0: 8.67,
    21.1: 8.79, 21.2: 8.90, 21.3: 9.02, 21.4: 9.13, 21.5: 9.25,
    21.6: 9.36, 21.7: 9.48, 21.8: 9.60, 21.9: 9.71, 22.0: 9.83,
    22.1: 9.94, 22.2: 10.06, 22.3: 10.17, 22.4: 10.29, 22.5: 10.40,
    22.6: 10.52, 22.7: 10.64, 22.8: 10.75, 22.9: 10.87, 23.0: 10.98,
    23.1: 11.10, 23.2: 11.21, 23.3: 11.33, 23.4: 11.45, 23.5: 11.56,
    23.6: 11.68, 23.7: 11.79, 23.8: 11.91, 23.9: 12.02, 24.0: 12.14,
    24.1: 12.25, 24.2: 12.37, 24.3: 12.49, 24.4: 12.60, 24.5: 12.72,
    24.6: 12.83, 24.7: 12.95, 24.8: 13.06, 24.9: 13.18, 25.0: 13.29,
}
# ======================================================
# MERMA GIRASOL – TABLA OFICIAL
# ======================================================

MERMA_GIRASOL = {
    11.1: 0.67, 11.2: 0.78, 11.3: 0.89, 11.4: 1.01, 11.5: 1.12,
    11.6: 1.23, 11.7: 1.34, 11.8: 1.45, 11.9: 1.56, 12.0: 1.68,
    12.1: 1.79, 12.2: 1.90, 12.3: 2.01, 12.4: 2.12, 12.5: 2.23,
    12.6: 2.35, 12.7: 2.46, 12.8: 2.57, 12.9: 2.68, 13.0: 2.79,
    13.1: 2.91, 13.2: 3.02, 13.3: 3.13, 13.4: 3.24, 13.5: 3.35,
    13.6: 3.46, 13.7: 3.58, 13.8: 3.69, 13.9: 3.80, 14.0: 3.91,
    14.1: 4.02, 14.2: 4.13, 14.3: 4.25, 14.4: 4.36, 14.5: 4.47,
    14.6: 4.58, 14.7: 4.69, 14.8: 4.80, 14.9: 4.92, 15.0: 5.03,
    15.1: 5.14, 15.2: 5.25, 15.3: 5.36, 15.4: 5.47, 15.5: 5.59,
    15.6: 5.70, 15.7: 5.81, 15.8: 5.92, 15.9: 6.03, 16.0: 6.15,
    16.1: 6.26, 16.2: 6.37, 16.3: 6.48, 16.4: 6.59, 16.5: 6.70,
    16.6: 6.82, 16.7: 6.93, 16.8: 7.04, 16.9: 7.15, 17.0: 7.26,
    17.1: 7.37, 17.2: 7.49, 17.3: 7.60, 17.4: 7.71, 17.5: 7.82,
    17.6: 7.93, 17.7: 8.04, 17.8: 8.16, 17.9: 8.27, 18.0: 8.38,
    18.1: 8.49, 18.2: 8.60, 18.3: 8.72, 18.4: 8.83, 18.5: 8.94,
    18.6: 9.05, 18.7: 9.16, 18.8: 9.27, 18.9: 9.39, 19.0: 9.50,
    19.1: 9.61, 19.2: 9.72, 19.3: 9.83, 19.4: 9.94, 19.5: 10.06,
    19.6: 10.17, 19.7: 10.28, 19.8: 10.39, 19.9: 10.50, 20.0: 10.61,
    20.1: 10.73, 20.2: 10.84, 20.3: 10.95, 20.4: 11.06, 20.5: 11.17,
    20.6: 11.28, 20.7: 11.40, 20.8: 11.51, 20.9: 11.62, 21.0: 11.73,
    21.1: 11.84, 21.2: 11.96, 21.3: 12.07, 21.4: 12.18, 21.5: 12.29,
    21.6: 12.40, 21.7: 12.51, 21.8: 12.63, 21.9: 12.74, 22.0: 12.85,
    22.1: 12.96, 22.2: 13.07, 22.3: 13.18, 22.4: 13.30, 22.5: 13.41,
    22.6: 13.52, 22.7: 13.63, 22.8: 13.74, 22.9: 13.85, 23.0: 13.97,
    23.1: 14.08, 23.2: 14.19, 23.3: 14.30, 23.4: 14.41, 23.5: 14.53,
    23.6: 14.64, 23.7: 14.75, 23.8: 14.86, 23.9: 14.97, 24.0: 15.08,
    24.1: 15.20, 24.2: 15.31, 24.3: 15.42, 24.4: 15.53, 24.5: 15.64,
    24.6: 15.75, 24.7: 15.87, 24.8: 15.98, 24.9: 16.09, 25.0: 16.20,
}
MERMA_SORGO = {
    15.1: 1.85, 15.2: 1.97, 15.3: 2.08, 15.4: 2.20, 15.5: 2.31,
    15.6: 2.43, 15.7: 2.54, 15.8: 2.66, 15.9: 2.77, 16.0: 2.89,
    16.1: 3.01, 16.2: 3.12, 16.3: 3.24, 16.4: 3.35, 16.5: 3.47,
    16.6: 3.58, 16.7: 3.70, 16.8: 3.82, 16.9: 3.93, 17.0: 4.05,
    17.1: 4.16, 17.2: 4.28, 17.3: 4.39, 17.4: 4.51, 17.5: 4.62,
    17.6: 4.74, 17.7: 4.86, 17.8: 4.97, 17.9: 5.09, 18.0: 5.20,
    18.1: 5.32, 18.2: 5.43, 18.3: 5.55, 18.4: 5.66, 18.5: 5.78,
    18.6: 5.90, 18.7: 6.01, 18.8: 6.13, 18.9: 6.24, 19.0: 6.36,
    19.1: 6.47, 19.2: 6.59, 19.3: 6.71, 19.4: 6.82, 19.5: 6.94,
    19.6: 7.05, 19.7: 7.17, 19.8: 7.28, 19.9: 7.40, 20.0: 7.51,
    20.1: 7.63, 20.2: 7.75, 20.3: 7.86, 20.4: 7.98, 20.5: 8.09,
    20.6: 8.21, 20.7: 8.32, 20.8: 8.44, 20.9: 8.55, 21.0: 8.67,
    21.1: 8.79, 21.2: 8.90, 21.3: 9.02, 21.4: 9.13, 21.5: 9.25,
    21.6: 9.36, 21.7: 9.48, 21.8: 9.60, 21.9: 9.71, 22.0: 9.83,
    22.1: 9.94, 22.2: 10.06, 22.3: 10.17, 22.4: 10.29, 22.5: 10.40,
    22.6: 10.52, 22.7: 10.64, 22.8: 10.75, 22.9: 10.87, 23.0: 10.98,
    23.1: 11.10, 23.2: 11.21, 23.3: 11.33, 23.4: 11.45, 23.5: 11.56,
    23.6: 11.68, 23.7: 11.79, 23.8: 11.91, 23.9: 12.02, 24.0: 12.14,
    24.1: 12.25, 24.2: 12.37, 24.3: 12.49, 24.4: 12.60, 24.5: 12.72,
    24.6: 12.83, 24.7: 12.95, 24.8: 13.06, 24.9: 13.18, 25.0: 13.29,
}
def merma_sorgo(humedad):

    if humedad is None:
        return 0
    
    humedad = float(humedad)

    if humedad <= 15.0:
        return 0

    h = round(humedad, 1)

    if h not in MERMA_SORGO:
        h = min(MERMA_SORGO.keys(), key=lambda x: abs(x - h))

    merma = MERMA_SORGO[h]

    # manipuleo fijo
    merma += 0.25

    return round(merma, 2)
def merma_maiz(humedad):
    """
    Devuelve merma oficial de maíz
    + 0.25% fijo por manipuleo
    """

    if humedad is None:
        return 0

    humedad = float(humedad)   # 👈 AGREGAR ESTO

    if humedad <= 14.5:
        return 0

    # Redondeo al decimal más cercano
    h = round(humedad, 1)

    if h not in MERMA_MAIZ:
        # si está fuera de tabla usamos el valor más cercano
        h = min(MERMA_MAIZ.keys(), key=lambda x: abs(x - h))

    merma = MERMA_MAIZ[h]

    # sumar manipuleo fijo
    merma += 0.25

    return round(merma, 2)
def merma_soja(humedad):
    """
    Devuelve merma oficial de soja
    + 0.25% fijo por manipuleo
    """

    if humedad is None:
        return 0
    
    humedad = float(humedad)

    if humedad <= 13.5:
        return 0

    h = round(humedad, 1)

    if h not in MERMA_SOJA:
        h = min(MERMA_SOJA.keys(), key=lambda x: abs(x - h))

    merma = MERMA_SOJA[h]

    # sumar manipuleo fijo
    merma += 0.25

    return round(merma, 2)
def merma_trigo(humedad):
    """
    Devuelve merma oficial de trigo
    + 0.10% fijo por manipuleo
    """

    if humedad is None:
        return 0
    
    humedad = float(humedad)

    if humedad <= 14.0:
        return 0

    h = round(humedad, 1)

    if h not in MERMA_TRIGO:
        h = min(MERMA_TRIGO.keys(), key=lambda x: abs(x - h))

    merma = MERMA_TRIGO[h]

    # sumar manipuleo fijo
    merma += 0.10

    return round(merma, 2)
def merma_girasol(humedad):
    """
    Devuelve merma oficial de girasol
    + 0.20% fijo por manipuleo
    """

    if humedad is None:
        return 0
    
    humedad = float(humedad)

    if humedad <= 11.0:
        return 0

    h = round(humedad, 1)

    if h not in MERMA_GIRASOL:
        h = min(MERMA_GIRASOL.keys(), key=lambda x: abs(x - h))

    merma = MERMA_GIRASOL[h]

    # sumar manipuleo fijo
    merma += 0.20

    return round(merma, 2)
def calcular_merma_humedad(cereal, humedad_prom):

    if cereal == "Maíz":
        return merma_maiz(humedad_prom)

    if cereal == "Soja":
        return merma_soja(humedad_prom)

    if cereal == "Trigo":
        return merma_trigo(humedad_prom)

    if cereal == "Girasol":
        return merma_girasol(humedad_prom)

    return 0
def mejor_matba(conn, cereal, factor):
    prefijos = {
        "Maíz": "CR",
        "Soja": "SR",
        "Trigo": "WR"
    }

    prefijo = prefijos.get(cereal)

    if not prefijo:
        return None

    rows = conn.execute("""
        SELECT posicion, precio, mes
        FROM matba
        WHERE posicion LIKE ?
    """, (f"{prefijo}%",)).fetchall()

    mejor = None
    mejor_precio = 0

    for r in rows:
        precio = float(r["precio"])
        neto = precio * factor

        if neto > mejor_precio:
            mejor_precio = neto
            mejor = {
                "posicion": r["posicion"],
                "mes": r["mes"],
                "precio": precio,
                "neto": round(neto,2)
            }

    return mejor