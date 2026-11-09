from __future__ import annotations

import math
import re
import warnings
from pathlib import Path

import numpy as np

from .aeronave_vlm import avisos_de_ignoradas, superficies
from .faixas import TeoriaDeFaixas
from .parasita import parasita
from .perfil import Perfil
from .polares import BancoPolares, Polar
from .vlm import VLM

BANCO_PADRAO = Path(__file__).resolve().parents[3].parent / "data" / "polares.npz"
_cache: dict[str, BancoPolares] = {}

def banco(caminho: str | Path | None = None) -> BancoPolares:
    c = str(caminho or BANCO_PADRAO)
    if c not in _cache:
        _cache[c] = BancoPolares.carregar_npz(c)
    return _cache[c]

def _norm(s: str) -> str:
    s = Path(str(s).replace("\\", "/")).name
    s = re.sub(r"\.dat$", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _alpha_l0(p: Polar) -> float:
    cl = p.cl[-1]
    i = np.where(np.diff(np.sign(cl)) != 0)[0]
    if len(i) == 0:
        return float("nan")
    k = i[0]
    return float(p.alpha[k] - cl[k] * (p.alpha[k + 1] - p.alpha[k]) / (cl[k + 1] - cl[k]))

def escolhe(spec: str, perfil: Perfil, b: BancoPolares, ncrit: int = 4) -> tuple[Polar, str, str]:
    nomes = list(b.polares)
    por_norm: dict[str, dict[int, str]] = {}
    for n in nomes:
        base, _, k = n.rpartition("@n")
        por_norm.setdefault(_norm(base), {})[int(k)] = n
    alvo = por_norm.get(_norm(spec))
    if alvo:
        k = ncrit if ncrit in alvo else next(iter(alvo))
        nota = "" if k == ncrit else f"so existe com Ncrit {k} no banco"
        return b[alvo[k]], "banco", nota
    a0 = np.degrees(perfil.alpha_sustentacao_nula())
    cand = sorted((abs(_alpha_l0(b[n]) - a0), n) for n in nomes
                  if n.endswith(f"@n{ncrit}") and np.isfinite(_alpha_l0(b[n])))
    perto = [c for c in cand if c[0] <= 1.0] or cand[:3]
    cl = lambda n: float(b[n].cl[-1].max())
    perto.sort(key=lambda c: cl(c[1]))
    n = perto[len(perto) // 2][1]
    faixa = f"{cl(perto[0][1]):.2f} a {cl(perto[-1][1]):.2f}"
    return b[n], "aproximado", (f"'{spec}' nao esta no banco: usei {n.split('@')[0]} (mediana de {len(perto)} perfis com angulo de "
                                f"sustentacao nula parecido, {a0:.1f}°; cl_max 2D entre {faixa})")

def polares_da_aeronave(vlm: VLM, ncrit: int = 4, caminho=None) -> tuple[dict, list[dict]]:
    b = banco(caminho)
    polares, info = {}, []
    for s in vlm.superficies:
        if abs(s.diedro) > 60.0:
            continue
        pol, origem, nota = escolhe(s.perfil.nome, s.perfil, b, ncrit)
        if s.perfil_ponta is not None:
            nota = (nota + "; " if nota else "") + f"ponta com {s.perfil_ponta.nome}, mas a conta usa o perfil da raiz em toda a asa"
        polares[s.nome] = pol
        info.append({"superficie": s.nome, "perfil": s.perfil.nome, "polar": pol.nome, "origem": origem, "nota": nota})
    return polares, info

def atitude_de_solo(esq: dict) -> float | None:
    pts = [(float(e["posicao"][0]), float(e["posicao"][2]) - float(e["diametro"]) / 2)
           for e in esq.get("elementos", []) if e.get("tipo") == "roda"]
    if len(pts) < 2:
        return None
    a, b = min(pts), max(pts)
    if b[0] - a[0] < 1e-3:
        return None
    return -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))

def altura_do_solo(esq: dict, alpha: float, x_ref: float, z_ref: float = 0.0) -> float | None:
    pts = [(float(e["posicao"][0]), float(e["posicao"][2]) - float(e["diametro"]) / 2)
           for e in esq.get("elementos", []) if e.get("tipo") == "roda"]
    if not pts:
        return None
    al = math.radians(alpha)
    zs = [z_ref - (x - x_ref) * math.sin(al) + (z - z_ref) * math.cos(al) for x, z in pts]
    return z_ref - min(zs)

ALTURAS_SOLO = (0.3, 0.6, 1.2)
H_LIVRE = 5.0

def _tabela_solo(esq: dict, x_cg: float, h0: float, alpha: float, V: float, rho: float) -> list[dict]:
    sup = superficies(esq)
    pts = []
    for hh in (h0, *[x for x in ALTURAS_SOLO if x > h0 + 1e-9]):
        q = VLM.arfada(sup, alpha, hh, x_ref=x_cg).resolver(0.0, V=V, rho=rho)[0]
        pts.append({"h": float(hh), "CL": float(q.CL), "CDi": float(q.CDi), "K": float(q.CDi / q.CL ** 2) if abs(q.CL) > 1e-6 else 0.0})
    q = VLM(sup, x_ref=x_cg).resolver(alpha, V=V, rho=rho)[0]
    pts.append({"h": H_LIVRE, "CL": float(q.CL), "CDi": float(q.CDi), "K": float(q.CDi / q.CL ** 2) if abs(q.CL) > 1e-6 else 0.0})
    return pts

def cl_max(esq: dict, x_cg: float, V: float = 12.0, rho: float = 1.1, ncrit: int = 4,
           a_max: float = 24.0, passo: float = 1.0, caminho=None,
           alpha_solo: float | None = None, CdA_proprio: float | None = None,
           altura: float | None = None, com_solo: bool = True) -> dict:
    vlm = VLM(superficies(esq), x_ref=float(x_cg))
    polares, info = polares_da_aeronave(vlm, ncrit, caminho)
    avisos = avisos_de_ignoradas(esq) + [i["nota"] for i in info if i["nota"]]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tf = TeoriaDeFaixas(vlm, polares, rho=rho)
        curva, melhor, quedas = [], None, 0
        for a in np.arange(0.0, a_max + passo / 2, passo):
            q = tf.resolver(float(a), V)
            curva.append(q)
            if melhor is None or q.CL > melhor.CL:
                melhor, quedas = q, 0
            elif q.CL < melhor.CL * 0.98:
                quedas += 1
                if quedas >= 2:
                    break
            else:
                quedas = 0
        r, clm, a_est = melhor, melhor.CL, melhor.alpha
        origem_solo = "voce"
        if alpha_solo is None:
            alpha_solo = atitude_de_solo(esq)
            origem_solo = "geometria" if alpha_solo is not None else "padrao 0"
            alpha_solo = 0.0 if alpha_solo is None else alpha_solo
        rl = tf.resolver(float(alpha_solo), V)
        h = altura if altura is not None else altura_do_solo(esq, alpha_solo, float(x_cg))
        origem_h = "voce" if altura is not None else "rodas"
        rs, solo_tab, usou_solo = rl, None, False
        if com_solo and h is not None and h > 0:
            usou_solo = True
            vs = VLM(superficies(esq), x_ref=float(x_cg), altura_solo=float(h))
            rs = TeoriaDeFaixas(vs, polares, rho=rho).resolver(float(alpha_solo), V)
            solo_tab = _tabela_solo(esq, float(x_cg), float(h), float(alpha_solo), V, rho)
    avisos += sorted({str(x.message).split(" Acima")[0] for x in w if "ESTOL" in str(x.message)})
    if not r.convergiu:
        avisos.append(f"a iteracao nao fechou no pico ({r.motivo}): CL_max com incerteza maior")
    if a_est >= a_max - passo:
        avisos.append(f"nao houve queda de CL ate {a_max:.0f}°: CL_max e um limite inferior")
    par = parasita(esq, vlm.S_ref, V, rho)
    CD_par = par["CD"] if CdA_proprio is None else CdA_proprio / vlm.S_ref
    avisos.append("Arrasto parasita estimado por componentes (Hoerner/Raymer), nao medido: o tunel do IPT mediu CD minimo bem acima do da asa limpa." if CdA_proprio is None
                  else f"Arrasto parasita fixado por voce: CdA = {CdA_proprio:g} m2.")
    if h is None and com_solo:
        avisos.append("Sem rodas no modelo e sem altura informada: efeito solo NAO considerado (CD de corrida pessimista).")
    if not rs.convergiu:
        avisos.append("a iteracao nao fechou no angulo de solo: CL e CD de corrida com incerteza maior")
    ref = next(s.nome for s in vlm.superficies if s.de_referencia)
    inicio = r.inicio_do_estol(ref)
    semi = vlm.b_ref / 2
    avisos.append("CL_max da asa inteira por teoria de faixas: nao foi conferido com ensaio de asa completa.")
    avisos = list(dict.fromkeys(avisos))
    return {"CL_max": float(clm), "alpha_estol": float(a_est), "V": V, "rho": rho, "ncrit": ncrit,
            "fracao_estolada": float(r.fracao_estolada(ref)),
            "inicio_estol_y": None if inicio is None else float(inicio),
            "inicio_estol_rel": None if inicio is None else float(inicio / semi),
            "convergiu": bool(r.convergiu), "CDp": float(r.CDp),
            "curva": {"alpha": [float(q.alpha) for q in curva], "CL": [float(q.CL) for q in curva], "CD": [float(q.CD + CD_par) for q in curva]},
            "solo": {"usado": usou_solo, "h": None if h is None else float(h), "origem": origem_h if h is not None else "",
                     "livre": {"CL": float(rl.CL), "CD": float(rl.CD + CD_par)}, "tabela": solo_tab},
            "corrida": {"alpha": float(alpha_solo), "origem": origem_solo, "CL": float(rs.CL), "CDi": float(rs.CDi), "CDp": float(rs.CDp),
                        "CD_parasita": float(CD_par), "CD": float(rs.CD + CD_par), "S_ref": float(vlm.S_ref)},
            "parasita": par, "polares": info, "avisos": avisos}
