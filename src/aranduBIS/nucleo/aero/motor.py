from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

@dataclass(frozen=True)
class Motor:

    Kv: float
    R: float
    I0: float
    nome: str = ""
    I_max: float | None = None
    massa: float | None = None
    fonte: str = ""
    V_ref_I0: float | None = None

    def __post_init__(self) -> None:
        if self.Kv <= 0 or self.R <= 0 or self.I0 < 0:
            raise ValueError("Kv e R devem ser positivos, I0 nao-negativo")

    @property
    def Kt(self) -> float:
        return 60.0 / (2.0 * np.pi * self.Kv)

U8_LITE_KV190 = Motor(Kv=190.0, R=0.048, I0=1.3, nome="T-Motor U8 Lite KV190",
                      I_max=43.7, massa=240.0, V_ref_I0=18.0,
                      fonte="catalogo T-Motor (NAO reconferido em 2026-09-10)")

SII_5525_170 = Motor(Kv=170.0, R=0.042, I0=0.78, nome="Scorpion SII-5525-170",
                     I_max=70.0, massa=708.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)
SII_5525_195 = Motor(Kv=195.0, R=0.034, I0=0.88, nome="Scorpion SII-5525-195",
                     I_max=80.0, massa=708.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)
SII_5525_210 = Motor(Kv=210.0, R=0.026, I0=1.11, nome="Scorpion SII-5525-210",
                     I_max=90.0, massa=708.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)
SII_4035_250 = Motor(Kv=250.0, R=0.037, I0=0.69, nome="Scorpion SII-4035-250",
                     I_max=65.0, massa=450.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)
SII_4025_330 = Motor(Kv=330.0, R=0.037, I0=0.74, nome="Scorpion SII-4025-330",
                     I_max=75.0, massa=353.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)
SII_4035_330 = Motor(Kv=330.0, R=0.031, I0=1.41, nome="Scorpion SII-4035-330",
                     I_max=65.0, massa=435.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-09-10",
                     V_ref_I0=10.0)

SII_4035_380 = Motor(Kv=380.0, R=0.025, I0=1.52, nome="Scorpion SII-4035-380",
                     I_max=70.0, massa=435.0,
                     fonte="scorpionsystem.com, Motor Data, 2026-10-18",
                     V_ref_I0=10.0)

CATALOGO = {
    m.nome: m for m in (U8_LITE_KV190, SII_5525_170, SII_5525_195,
                        SII_5525_210, SII_4035_250, SII_4025_330,
                        SII_4035_330, SII_4035_380)
}

@dataclass(frozen=True)
class Esc:

    k_chaveamento: float = 0.0365
    R_conducao: float = 0.005

    def rendimento(self, P_motor: float, I_motor: float) -> float:
        if P_motor <= 0:
            return 1.0
        perda = self.k_chaveamento * P_motor + I_motor ** 2 * self.R_conducao
        return P_motor / (P_motor + perda)

@dataclass(frozen=True)
class Fidelidade:

    T_enrol_C: float = 25.0
    beta_vazio: float = 1.0
    V_ref_padrao: float = 10.0
    esc: Esc | None = None

    @property
    def desligada(self) -> bool:
        return (self.T_enrol_C == 25.0 and self.beta_vazio == 1.0
                and self.esc is None)

def fidelidade_da_oficina(realista: bool = True) -> Fidelidade:
    if not realista:
        return Fidelidade()
    lido = lambda k, d: d

    return Fidelidade(
        T_enrol_C=lido("motor_temp_enrolamento_C", 70.0),
        beta_vazio=lido("motor_expoente_perdas_vazio", 1.5),
        esc=Esc(k_chaveamento=lido("esc_perda_chaveamento", 0.0365),
                R_conducao=lido("esc_resistencia_ohm", 0.005)))

def _I0_efetivo(motor: Motor, rpm: float, fid: Fidelidade | None) -> float:
    if fid is None or fid.beta_vazio == 1.0 or motor.I0 == 0.0 or rpm <= 0:
        return motor.I0
    v_ref = motor.V_ref_I0 if motor.V_ref_I0 else fid.V_ref_padrao
    rpm_ref = v_ref * motor.Kv
    return motor.I0 * (rpm / rpm_ref) ** (fid.beta_vazio - 1.0)

def _R_efetiva(motor: Motor, fid: Fidelidade | None) -> float:
    if fid is None or fid.T_enrol_C == 25.0:
        return motor.R
    resistencia_motor_quente = lambda R, T: R * (1.0 + 0.00393 * (T - 25.0))

    return resistencia_motor_quente(motor.R, fid.T_enrol_C)

@dataclass
class Operacao:
    rpm: float
    Q: float
    I: float
    V: float
    P_eletrica: float
    P_eixo: float

    @property
    def rendimento(self) -> float:
        return self.P_eixo / self.P_eletrica if self.P_eletrica > 0 else 0.0

    def __repr__(self) -> str:
        return (f"<Motor {self.rpm:.0f} rpm, {self.I:.1f} A, {self.V:.1f} V, "
                f"{self.P_eletrica:.0f} W el, {self.P_eixo:.0f} W eixo, "
                f"eta={self.rendimento:.3f}>")

def operar(motor: Motor, rpm: float, Q: float,
           fid: Fidelidade | None = None) -> Operacao:
    if rpm < 0 or Q < 0:
        raise ValueError("rpm e Q devem ser nao-negativos")
    I = Q / motor.Kt + _I0_efetivo(motor, rpm, fid)
    V = rpm / motor.Kv + I * _R_efetiva(motor, fid)
    return Operacao(rpm=rpm, Q=Q, I=I, V=V, P_eletrica=V * I,
                    P_eixo=Q * rpm * 2.0 * np.pi / 60.0)

def rpm_no_limite(motor: Motor, torque_da_helice, P_limite_bateria: float,
                  eta_esc: float = 0.96, lo: float = 500.0,
                  hi: float = 12000.0,
                  fid: Fidelidade | None = None) -> Operacao | None:
    if not (0 < eta_esc <= 1):
        raise ValueError("eta_esc deve estar em (0, 1]")
    alvo = P_limite_bateria * eta_esc
    esc = fid.esc if fid is not None else None

    def f(rpm: float) -> float:
        op = operar(motor, rpm, max(torque_da_helice(rpm), 0.0), fid)
        if esc is None:
            return op.P_eletrica - alvo
        return op.P_eletrica / esc.rendimento(op.P_eletrica, op.I) - P_limite_bateria

    try:
        if f(lo) * f(hi) > 0:
            return None
        rpm = brentq(f, lo, hi, xtol=0.5, maxiter=80)
    except (ValueError, RuntimeError):
        return None
    return operar(motor, rpm, max(torque_da_helice(rpm), 0.0), fid)
