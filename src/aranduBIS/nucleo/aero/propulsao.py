from __future__ import annotations

import numpy as np

from .apc import catalogo as catalogo_helices
from .motor import CATALOGO as MOTORES, Esc, Fidelidade, operar, rpm_no_limite

def fidelidade(realista: bool) -> Fidelidade | None:
    return Fidelidade(T_enrol_C=70.0, beta_vazio=1.5, esc=Esc()) if realista else None

def lista() -> dict:
    return {"motores": [{"nome": m.nome, "Kv": m.Kv, "R": m.R, "I0": m.I0, "I_max": m.I_max, "massa_g": m.massa, "fonte": m.fonte}
                        for m in MOTORES.values()],
            "helices": [{"nome": h.nome, "D_pol": h.D_pol, "passo_pol": h.passo_pol,
                         "rpm_max": float(h.rpm[-1])} for h in catalogo_helices().values()]}

def curva(motor: str, helice: str, P_w: float = 600.0, rho: float = 1.1, V_max: float = 30.0,
          n: int = 16, realista: bool = True) -> dict:
    m = MOTORES.get(motor)
    h = catalogo_helices().get(helice)
    if m is None:
        raise ValueError(f"motor desconhecido: {motor}")
    if h is None:
        raise ValueError(f"helice desconhecida: {helice}")
    fid = fidelidade(realista)
    eta_esc = 0.96
    V = np.linspace(0.0, V_max, n)
    sai = {"V": [], "T": [], "rpm": [], "I": [], "U": [], "eta_prop": []}
    avisos: list[str] = []
    for v in V:
        torque = lambda rpm, _v=float(v): h.tracao_e_torque(_v, rpm, rho)[1]
        op = rpm_no_limite(m, torque, P_w, eta_esc=eta_esc, lo=float(h.rpm[0]), hi=float(h.rpm[-1]), fid=fid)
        if op is None:
            continue
        t, _ = h.tracao_e_torque(float(v), op.rpm, rho)
        sai["V"].append(float(v)); sai["T"].append(float(t)); sai["rpm"].append(float(op.rpm))
        sai["I"].append(float(op.I)); sai["U"].append(float(op.V))
        sai["eta_prop"].append(float(t * v / op.P_eixo) if op.P_eixo > 0 else 0.0)
    if not sai["V"] or sai["V"][0] != 0.0:
        return {"erro": f"sem equilibrio motor-helice a {P_w:.0f} W (parada): a potencia nao e alcancavel nessa faixa de rotacao"}
    if m.I_max and max(sai["I"]) > m.I_max:
        avisos.append(f"corrente de pico {max(sai['I']):.0f} A passa da corrente maxima do motor ({m.I_max:g} A)")
    if sai["rpm"][0] >= h.rpm[-1] - 1:
        avisos.append("a rotacao bate no limite da tabela da APC: a tracao real pode ser menor")
    if len(sai["V"]) < n:
        avisos.append(f"sem solucao acima de {sai['V'][-1]:.0f} m/s (fim da tabela da helice)")
    avisos.append("Tabela da APC e calculo do fabricante, nao ensaio; o motor usa Kv, R e I0 de catalogo.")
    avisos.append(f"Tensao pedida na parada: {sai['U'][0]:.1f} V sob {sai['I'][0]:.0f} A: o pack precisa dar isso sem cair.")
    sai.update({"motor": m.nome, "helice": h.nome, "P_w": P_w, "rho": rho, "realista": realista,
                "T0": sai["T"][0], "rpm0": sai["rpm"][0], "avisos": avisos})
    return sai
