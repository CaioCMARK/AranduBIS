from __future__ import annotations

import copy
import math
import re
import time

from .. import regra as R
from ..formula import ErroDeFormula, avaliar as _avalia, compilar

class ProblemaInvalido(ValueError):
    pass

_PASSO = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[(-?\d+)\]")

def _caminho(alvo: str):
    partes = alvo.split(".")
    if len(partes) < 2:
        raise ProblemaInvalido(f"alvo “{alvo}”: use elemento.campo, por exemplo asa.secoes[1].corda")
    passos = []
    for p in partes[1:]:
        pos = 0
        for m in _PASSO.finditer(p):
            if m.start() != pos:
                raise ProblemaInvalido(f"alvo “{alvo}”: nao entendi “{p}”")
            passos.append(m.group(1) if m.group(1) is not None else int(m.group(2))); pos = m.end()
        if pos != len(p):
            raise ProblemaInvalido(f"alvo “{alvo}”: nao entendi “{p}”")
    return partes[0], passos

def poe(esq: dict, alvo: str, valor):
    nome, passos = _caminho(alvo)
    no = next((e for e in esq.get("elementos", []) if e.get("nome") == nome), None)
    if no is None:
        raise ProblemaInvalido(f"alvo “{alvo}”: o modelo nao tem o elemento “{nome}”")
    for k in passos[:-1]:
        try:
            no = no[k]
        except (KeyError, IndexError, TypeError):
            raise ProblemaInvalido(f"alvo “{alvo}”: “{k}” nao existe no modelo") from None
    ult = passos[-1]
    try:
        if isinstance(ult, int):
            no[ult] = valor
        elif isinstance(no, dict):
            no[ult] = valor
        else:
            raise TypeError
    except (IndexError, TypeError):
        raise ProblemaInvalido(f"alvo “{alvo}”: “{ult}” nao existe no modelo") from None

def le(esq: dict, alvo: str):
    nome, passos = _caminho(alvo)
    no = next((e for e in esq.get("elementos", []) if e.get("nome") == nome), None)
    if no is None:
        raise ProblemaInvalido(f"alvo “{alvo}”: o modelo nao tem o elemento “{nome}”")
    for k in passos:
        try:
            no = no[k]
        except (KeyError, IndexError, TypeError):
            raise ProblemaInvalido(f"alvo “{alvo}”: “{k}” nao existe no modelo") from None
    return no

def _f(txt, ctx, onde):
    try:
        return float(_avalia(compilar(str(txt), onde), ctx, onde))
    except ErroDeFormula as e:
        raise ProblemaInvalido(str(e).split("\n")[0]) from None
    except (ZeroDivisionError, OverflowError, ValueError) as e:
        raise ProblemaInvalido(f"{onde}: {e}") from None

def valores_padrao(prob: dict) -> dict:
    return {v["nome"]: float(v.get("padrao", 0.5 * (v["minimo"] + v["maximo"]))) for v in prob.get("variaveis", [])}

def confere(prob: dict) -> list[str]:
    p, nomes = [], set()
    for v in prob.get("variaveis", []):
        n = v.get("nome")
        if not n or n in nomes:
            p.append(f"variavel “{n}”: nome vazio ou repetido")
        nomes.add(n)
        if v.get("valores"):
            if not (0 <= v.get("minimo", 0) <= v.get("maximo", len(v["valores"]) - 1) <= len(v["valores"]) - 1):
                p.append(f"variavel “{n}”: a faixa precisa caber nos indices 0 a {len(v['valores']) - 1} da lista")
        elif not (float(v.get("minimo", 0)) < float(v.get("maximo", 0))):
            p.append(f"variavel “{n}”: minimo precisa ser menor que maximo")
    if not prob.get("variaveis"):
        p.append("O problema nao tem variaveis.")
    try:
        monta(prob, valores_padrao(prob))
    except ProblemaInvalido as e:
        p.append(str(e))
    if prob.get("regra"):
        p += R.conferir(R.normaliza(prob["regra"]))
    return p

def monta(prob: dict, x: dict) -> tuple[dict, dict]:
    ctx = {}
    for v in prob.get("variaveis", []):
        val = float(x.get(v["nome"], v.get("padrao", 0.5 * (v["minimo"] + v["maximo"]))))
        val = min(max(val, float(v["minimo"])), float(v["maximo"]))
        ctx[v["nome"]] = float(round(val)) if v.get("valores") else val
    for g in prob.get("grandezas", []):
        ctx[g["nome"]] = _f(g["formula"], ctx, f"grandeza {g['nome']}")
    esq = copy.deepcopy(prob["base"])
    if prob.get("retira"):
        esq["elementos"] = [e for e in esq.get("elementos", []) if e.get("nome") not in set(prob["retira"])]
    for lg in prob.get("ligacoes", []):
        if lg.get("estica"):
            _estica(esq, lg["estica"], ctx)
            continue
        if lg.get("escala_y"):
            _escala_y(esq, lg["escala_y"], ctx)
            continue
        alvos = lg.get("alvos") or [lg["alvo"]]
        val = _f(lg["formula"], ctx, f"ligacao {alvos[0]}")
        if lg.get("valores"):
            i = int(round(val))
            if not 0 <= i < len(lg["valores"]):
                raise ProblemaInvalido(f"ligacao {alvos[0]}: indice {i} fora da lista de {len(lg['valores'])} valores")
            val = lg["valores"][i]
        for a in alvos:
            poe(esq, a, val)
    return esq, ctx

_CHAVES_Y = ("y",)
_CHAVES_PAR = ("xc_y", "ate_xc_y")

def _escala_no(no, k: float) -> None:
    if isinstance(no, dict):
        for ch, v in no.items():
            if ch in _CHAVES_Y and isinstance(v, (int, float)):
                no[ch] = v * k
            elif ch in _CHAVES_Y and isinstance(v, list) and all(isinstance(u, (int, float)) for u in v):
                no[ch] = [u * k for u in v]
            elif ch in _CHAVES_PAR and isinstance(v, list):
                for p in v:
                    p[0] = p[0] * k
            elif isinstance(v, (dict, list)):
                _escala_no(v, k)
    elif isinstance(no, list):
        for v in no:
            if isinstance(v, (dict, list)):
                _escala_no(v, k)

def _escala_y(esq: dict, cfg: dict, ctx: dict) -> None:
    k = _f(cfg["fator"], ctx, "escala_y.fator")
    if k <= 0:
        raise ProblemaInvalido("escala_y: fator precisa ser positivo")
    for nome in cfg["elementos"]:
        el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome), None)
        if el is None:
            raise ProblemaInvalido(f"escala_y: o modelo nao tem o elemento {nome!r}")
        for parte in ("secoes", "estrutura", "controles"):
            if el.get(parte) is not None:
                _escala_no(el[parte], k)

def _estica(esq: dict, cfg: dict, ctx: dict) -> None:
    i = {"x": 0, "y": 1, "z": 2}[cfg.get("eixo", "x")]
    de = float(cfg["de"]); fim = _f(cfg["fim"], ctx, "estica.fim")
    for nome in cfg["elementos"]:
        el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome), None)
        if el is None or not el.get("nos"):
            raise ProblemaInvalido(f"estica: elemento {nome!r} sem nos (precisa ser uma trelica)")
        f_ = max(n[i] for n in el["nos"])
        if f_ <= de:
            raise ProblemaInvalido(f"estica: {nome!r} nao tem nos alem de {de:g}")
        k = (fim - de) / (f_ - de)
        if k <= 0:
            raise ProblemaInvalido(f"estica: fim {fim:g} antes do inicio {de:g}")
        for n in el["nos"]:
            if n[i] > de:
                n[i] = de + (n[i] - de) * k

def _afina_geometria(esq: dict, malha: dict | None) -> None:
    if not malha:
        return
    for el in esq.get("elementos", []):
        if el.get("tipo") != "asa":
            continue
        if malha.get("n_perfil") and el.get("n_perfil"):
            el["n_perfil"] = min(int(el["n_perfil"]), int(malha["n_perfil"]))
        if malha.get("n_por_baia") and isinstance(el.get("entelagem"), dict):
            el["entelagem"]["n_por_baia"] = min(int(el["entelagem"].get("n_por_baia", 6)), int(malha["n_por_baia"]))

def _restricoes(lista, ctx):
    out, viol = [], 0.0
    for c in lista:
        onde = f"restricao {c['nome']}"
        try:
            v = _f(c["formula"], ctx, onde); lim = _f(c.get("limite", 0), ctx, onde + " (limite)")
            folga = (lim - v) if c.get("tipo", "max") == "max" else (v - lim)
            vi = max(0.0, -folga) / max(abs(lim), 1e-9); viol += vi
            out.append({"nome": c["nome"], "valor": v, "limite": lim, "tipo": c.get("tipo", "max"), "folga": folga, "violacao": vi, "ok": folga >= 0, "erro": None})
        except ProblemaInvalido as e:
            viol += 1.0
            out.append({"nome": c["nome"], "valor": None, "limite": None, "tipo": c.get("tipo", "max"), "folga": None, "violacao": 1.0, "ok": False, "erro": str(e)})
    return out, viol

def avalia(prob: dict, x: dict) -> dict:
    from .. import decolagem as DC, medidas as MD
    from ..aero import limites as LM, propulsao as PR
    from ..aero.equilibrio import longitudinal
    from ..modelador import aeronave_geometria as AG

    t0 = time.perf_counter()
    an = prob.get("analise") or {}
    import warnings
    warnings.filterwarnings("ignore", message=".*pede n_span.*")
    res = {"x": dict(x), "objetivo": None, "pontuacao": None, "viavel": False, "violacao": 10.0, "falha": None, "restricoes": [], "resultados": {}, "avisos": []}
    q = res["resultados"]
    etapa = "variaveis e ligacoes"
    try:
        esq, ctx = monta(prob, x)
        res["x"] = {v["nome"]: ctx[v["nome"]] for v in prob.get("variaveis", [])}
        q.update({k: v for k, v in ctx.items() if k not in res["x"]})

        etapa = "geometria e massa"
        if prob.get("massas"):
            from . import dimensiona as DM
            pecas = DM.insere_massas(esq, prob["massas"], ctx)
            q["massas_sistema_kg"] = float(sum(m["kg"] for m in pecas)); q["custo_pecas"] = float(sum(m["custo"] for m in pecas))
            q["pecas"] = pecas
        _afina_geometria(esq, an.get("malha"))
        A = AG.constroi(esq)
        mc = AG.massa_e_cg(A)
        if not mc["massa_kg"] or not mc["cg_m"]:
            raise ProblemaInvalido("o modelo nao tem massa declarada: sem peso vazio nao ha pontuacao")
        q["PV"] = float(mc["massa_kg"]); q["x_cg_vazio"] = float(mc["cg_m"][0]); q["z_cg"] = float(mc["cg_m"][2])
        m = MD.medidas(esq, excluir=tuple(an.get("excluir_das_medidas", ())), cone_altura=an.get("cone_altura"), A=A)
        q.update({k: m[k] for k in ("envergadura", "comprimento", "altura", "n_superficies")})
        if m.get("raio_cone") is not None:
            q["raio_cone"] = m["raio_cone"]

        etapa = "estabilidade"
        rho, V = float(an.get("rho", 1.1)), float(an.get("V", 12.0))
        if an.get("x_cg") is not None:
            x_cg = _f(an["x_cg"], {**ctx, **q}, "analise.x_cg")
        elif an.get("carga_ref_kg"):
            mc_, xc_ = float(an["carga_ref_kg"]), float(an.get("carga_x", q["x_cg_vazio"]))
            x_cg = (q["PV"] * q["x_cg_vazio"] + mc_ * xc_) / (q["PV"] + mc_)
        else:
            x_cg = q["x_cg_vazio"]
        q["x_cg"] = x_cg
        malha = an.get("malha") or {}
        ns, nc = (int(malha["n_span"]) if malha.get("n_span") else None), int(malha.get("n_chord", 4))
        lo = longitudinal(esq, x_cg, V=V, rho=rho, z_cg=q["z_cg"], n_span=ns, n_chord=nc)
        q.update({"S_ref": lo["S_ref"], "c_ref": lo["c_ref"], "margem_estatica": lo["margem_estatica"], "ponto_neutro": lo["ponto_neutro"], "CL_alpha": lo["CL_alpha"]})

        etapa = "sustentacao e arrasto"
        cl = LM.cl_max(esq, x_cg, V=V, rho=rho, ncrit=int(an.get("ncrit", 4)), passo=float(an.get("passo_alpha", 1.0)),
                       alpha_solo=an.get("alpha_solo"), CdA_proprio=an.get("CdA"), n_span=ns, n_chord=nc)
        k = cl["corrida"]
        q.update({"CL_max": cl["CL_max"], "alpha_estol": cl["alpha_estol"], "CL_corrida": k["CL"], "CD_corrida": k["CD"]})

        if prob.get("dimensionamento"):
            etapa = "dimensionamento estrutural"
            from . import dimensiona as DM
            from ..estrutura.cargas import casos_de_carga
            pc = {**DM.PADRAO_CARGAS, **(an.get("cargas") or {})}
            mproj = _f(an.get("massa_projeto", 20.0), {**ctx, **q}, "analise.massa_projeto") if isinstance(an.get("massa_projeto", 20.0), str) else float(an.get("massa_projeto", 20.0))
            cc = casos_de_carga(esq, x_cg, q["z_cg"], mproj, rho, cl["CL_max"], lo["CL_alpha"], lo["c_ref"], lo["S_ref"], float(pc["Vc"]), float(pc["Vd"]),
                                n_max=float(pc["n_max"]), n_min=float(pc["n_min"]), U_c=float(pc["U_c"]), U_d=float(pc["U_d"]),
                                fator_seguranca=float(pc["fator_seguranca"]), n_span=ns, n_chord=nc)
            dd = DM.dimensiona(esq, prob["dimensionamento"], cc["casos"], ctx, float(pc["fator_seguranca"]))
            q["dimensionamento"] = dd
            q["margem_estrutural"] = min(d["margem"] for d in dd)
            for d in dd:
                q["dim_" + d["nome"]] = d["valor"]
            A = AG.constroi(esq); mc = AG.massa_e_cg(A)
            q["PV"] = float(mc["massa_kg"]); q["x_cg_vazio"] = float(mc["cg_m"][0]); q["z_cg"] = float(mc["cg_m"][2])
            q["massa_projeto"] = float(mproj)

        etapa = "tracao"
        pot = float(an.get("potencia_W", 600.0)); q["potencia"] = pot
        if an.get("motor") and an.get("helice"):
            tr = PR.curva(str(an["motor"]), str(an["helice"]), P_w=pot, rho=rho, celulas=an.get("celulas"))
            if "erro" in tr:
                raise ProblemaInvalido(tr["erro"])
            vt, tt = tuple(tr["V"]), tuple(tr["T"])
        else:
            vt, tt = (0.0, float(an.get("V0", 28.0))), (float(an.get("T0", 45.0)), 0.0)
        q["T0"] = float(tt[0])

        etapa = "decolagem"
        t = cl["solo"]["tabela"] if cl["solo"]["usado"] else None
        ae = DC.Aeronave(S=k["S_ref"], CL_max=cl["CL_max"], CL_corrida=k["CL"], CD_corrida=k["CD"], tracao_v=vt, tracao_n=tt,
                         solo_h=tuple(r["h"] for r in t) if t else (), solo_K=tuple(r["K"] for r in t) if t else (), h0=float(cl["solo"]["h"] or 0.0) if t else 0.0)
        campos = {c: float(an[c]) for c in ("pista_m", "obstaculo_m", "altitude_densidade_m", "mu", "d_alpha_rotacao", "taxa_rotacao", "margem_rotacao") if c in an}
        mm = DC.massa_maxima(ae, DC.Condicoes(**campos))
        q["massa_decolagem"] = float(mm["massa_kg"] or 0.0)
        q["CP_bruta"] = max(0.0, q["massa_decolagem"] - q["PV"])
        q["carga_alar"] = q["massa_decolagem"] / k["S_ref"] if k["S_ref"] > 0 else 0.0

        etapa = "regra"
        viol, rest = 0.0, []
        if prob.get("regra"):
            reg = R.normaliza(prob["regra"])
            entradas = {e["nome"] for e in reg["entradas"]}
            vals = {k_: v for k_, v in {**(prob.get("cenario") or {}), **q}.items() if k_ in entradas}
            out = R.avaliar(reg, vals)
            q["pontuacao"] = float(out["total"])
            for g in out["grandezas"]:
                if g["valor"] is not None and g["nome"] not in q:
                    q[g["nome"]] = g["valor"]
            rest = [dict(c, origem="regra") for c in out["restricoes"]]
            viol = float(out["violacao"])
            res["avisos"] += out["problemas"]
        r2, v2 = _restricoes(prob.get("restricoes", []), {**ctx, **q})
        rest += [dict(c, origem="projeto") for c in r2]; viol += v2
        res["restricoes"], res["violacao"], res["viavel"] = rest, viol, all(c["ok"] for c in rest)
        res["pontuacao"] = q.get("pontuacao")
        res["objetivo"] = _f(prob.get("objetivo", "pontuacao"), {**ctx, **q}, "objetivo")
    except (ProblemaInvalido, AG.GeometriaInvalida, ValueError, FileNotFoundError, KeyError, ZeroDivisionError, FloatingPointError) as e:
        res["falha"] = {"etapa": etapa, "motivo": str(e).split("\n")[0]}
        ordem = ["variaveis e ligacoes", "geometria e massa", "estabilidade", "sustentacao e arrasto", "dimensionamento estrutural", "tracao", "decolagem", "regra"]
        res["violacao"] = 10.0 + (len(ordem) - ordem.index(etapa))
    res["tempo_s"] = time.perf_counter() - t0
    for k_, v in list(q.items()):
        if isinstance(v, float) and not math.isfinite(v):
            q[k_] = None
    return res
