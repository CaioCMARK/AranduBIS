from __future__ import annotations

FT = 0.3048
LB = 0.45359237
GPA, MPA = 1.0e9, 1.0e6

RAJADA_VC_MS = 50.0 * FT
RAJADA_VD_MS = 25.0 * FT
VD_SOBRE_VC = 1.25
FATOR_SEGURANCA = 1.5
N_MAX_TETO = 3.8
N_MIN_SOBRE_N_MAX = -0.4
FATOR_POUSO = 2.67
FATOR_TAXI_Z = 1.0
FATOR_TAXI_Y = 0.5

def fator_manobra_positivo(massa_kg: float | None = None) -> float:
    W_lb = max(float(massa_kg or 0.0), 0.0) / LB
    return min(2.1 + 24000.0 / (W_lb + 10000.0), N_MAX_TETO)

def fator_manobra_negativo(n_max: float) -> float:
    return N_MIN_SOBRE_N_MAX * float(n_max)

def velocidade_mergulho(Vc: float) -> float:
    return VD_SOBRE_VC * float(Vc)

RHO_NIVEL_MAR = 1.225

def densidade_isa(altitude_densidade_m: float) -> float:
    return RHO_NIVEL_MAR * (1.0 - 2.25577e-5 * float(altitude_densidade_m)) ** 4.25588

MU_ROLAGEM = 0.05

BALSA = {"E": 3.4 * GPA, "X": 19.3 * MPA, "XC": 14.9 * MPA, "S": 1.9 * MPA, "YC": 1.1 * MPA, "YT": 1.1 * MPA,
         "G_sobre_EL": 0.037, "ET_sobre_EL": 0.015, "ER_sobre_EL": 0.046, "nu_LT": 0.488}
CARBONO_UD = {"E": 126.0 * GPA, "E2": 11.0 * GPA, "G": 6.6 * GPA, "nu12": 0.28,
              "X": 1950.0 * MPA, "XC": 1480.0 * MPA, "S": 79.0 * MPA, "YT": 48.0 * MPA, "YC": 200.0 * MPA}
SPRUCE = {"E": 10.8 * GPA, "X": 70.0 * MPA, "XC": 38.7 * MPA, "S": 7.9 * MPA, "YC": 4.0 * MPA, "YT": 4.0 * MPA, "G_sobre_EL": 0.061, "nu_LT": 0.467,
          "densidade": 450.0}

def knockdown_sp8007(R_sobre_t: float) -> float:
    import math
    return 1.0 - 0.901 * (1.0 - math.exp(-math.sqrt(max(float(R_sobre_t), 1.0)) / 16.0))
