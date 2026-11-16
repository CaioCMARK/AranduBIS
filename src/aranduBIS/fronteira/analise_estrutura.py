from __future__ import annotations

import json
import math
import numpy as np
from ..nucleo import referencias as R
from ..nucleo.modelador import aeronave_geometria as AG
from .analise_comum import ErroDeAnalise, _erro, _knockdown, _num, _vd

_CL_MAX: dict = {}

_CARGAS: dict = {}

def cargas(p: dict) -> dict:
    chave = json.dumps(p, sort_keys=True, default=str)
    if chave not in _CARGAS:
        r = _cargas(p)
        if "erro" in r:
            return r
        if len(_CARGAS) > 4:
            _CARGAS.clear()
        _CARGAS[chave] = r
    return _CARGAS[chave]

def _aileron_par(p: dict):
    a = p.get("aileron")
    if not isinstance(a, dict) or a.get("ativo") is False:
        return None
    out = {}
    for k in ("massa_kg", "x_cg", "r_giro", "f_b", "zeta"):
        if a.get(k) not in (None, ""):
            v = float(a[k])
            if k in ("massa_kg", "r_giro") and v <= 0:
                raise ErroDeAnalise(f"aileron.{k} precisa ser positivo")
            if k == "f_b" and v < 0:
                raise ErroDeAnalise("aileron.f_b nao pode ser negativa")
            out[k] = v
    return out

def _com_longarina(e: dict) -> bool:
    return e.get("tipo") == "asa" and bool((e.get("estrutura") or {}).get("longarinas"))

def _sem_longarina(esq: dict) -> list[str]:
    n = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and e.get("estrutura") and not _com_longarina(e)]
    return [f"Sem longarina declarada, fora desta analise: {', '.join(n)}."] if n else []

def asa(p: dict) -> dict:
    from ..nucleo.estrutura.asa import verifica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            if not any(s["nome"] == e["nome"] for s in c["casos"][0]["superficies"]):
                continue
            saidas.append(verifica(esq, e["nome"], c["casos"], mats=p.get("materiais"), fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                                   qualidade_balsa=_num(p, "qualidade_balsa", 1.0, positivo=True),
                                   qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True)))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        pior = min(saidas, key=lambda s: s["critico"]["margem"])
        return {"asas": saidas, "critico": dict(pior["critico"], asa=pior["nome"]), "vn": c["vn"], "massa_kg": c["massa_kg"],
                "avisos": avisos + c["avisos"] + [a for s in saidas for a in s["avisos"]] + _sem_longarina(esq)}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def massa_estrutural(p: dict) -> dict:
    from ..nucleo.estrutura.massa import balanco
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return balanco(p.get("esquema") or {}, _num(p, "mtow_kg", positivo=True) if p.get("mtow_kg") is not None else None)
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def trem(p: dict) -> dict:
    from ..nucleo.estrutura.trem import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        r = analisa(esq, massa_kg=_num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else None,
                    x_cg=_num(p, "x_cg") if p.get("x_cg") is not None else None, fator_pouso=_num(p, "fator_pouso", R.FATOR_POUSO, positivo=True),
                    atrito_pouso=_num(p, "atrito_pouso", 0.3), fator_taxi_y=_num(p, "fator_taxi_y", R.FATOR_TAXI_Y), fator_taxi_z=_num(p, "fator_taxi_z", R.FATOR_TAXI_Z, positivo=True),
                    fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                    raio_inercia=_num(p, "raio_inercia", 0.25, positivo=True), raio_solda=_num(p, "raio_solda", 0.0), mats=p.get("materiais"), qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True))
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, StopIteration) as e:
        return {"erro": _erro(e)}

_REF_AERO: dict = {}

_FE_TREM: dict = {}

def pouso_dinamico(p: dict) -> dict:
    from ..nucleo.aero.equilibrio import monta
    from ..nucleo.aero.estabilidade import derivadas
    from ..nucleo.estrutura import pouso_dinamico as PD
    from ..nucleo.estrutura import trem as TR
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        c = cargas({k: v for k, v in p.items() if k in ("esquema", "rho", "Vc", "Vd", "massa_kg", "x_cg", "CL_max", "ncrit", "n_max", "n_min", "U_c", "U_d", "fator_seguranca", "cl_min_rel")})
        if "erro" in c:
            return c
        massa = float(c["massa_kg"])
        mc = AG.massa_e_cg(AG.constroi(esq))
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        z_cg = float(cg[2]) if cg else 0.0
        rho, Vc = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), _num(p, "Vc", positivo=True)
        chave = (json.dumps(esq, sort_keys=True, default=str), round(x_cg, 6), round(Vc, 3), round(rho, 4))
        if chave not in _REF_AERO:
            if len(_REF_AERO) > 6:
                _REF_AERO.clear()
            vlm = monta(esq, x_cg, z_cg)
            d = derivadas(vlm, 3.0, V=Vc, rho=rho, laterais=False)
            _REF_AERO[chave] = {"S": float(vlm.S_ref), "c": float(vlm.c_ref), "CLa": float(d.CL_alpha), "Cma": float(d.Cm_alpha)}
        ref = _REF_AERO[chave]
        fator_pouso, atrito = _num(p, "fator_pouso", R.FATOR_POUSO, positivo=True), _num(p, "atrito_pouso", 0.3)
        kw = dict(fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                  raio_inercia=_num(p, "raio_inercia", 0.25, positivo=True), raio_solda=_num(p, "raio_solda", 0.0), mats=p.get("materiais"),
                  qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True))
        chave_fe = (chave[0], round(massa, 4), fator_pouso, atrito, json.dumps({k: v for k, v in kw.items() if k != "mats"}, sort_keys=True), json.dumps(kw["mats"], sort_keys=True, default=str))
        if chave_fe not in _FE_TREM:
            if len(_FE_TREM) > 4:
                _FE_TREM.clear()
            _FE_TREM[chave_fe] = TR.analisa(esq, massa_kg=massa, x_cg=x_cg, fator_pouso=fator_pouso, atrito_pouso=atrito, **kw)
        opc = lambda k, pad=None, pos=False: _num(p, k, pad, positivo=pos) if p.get(k) is not None else pad
        r = PD.analisa(esq, massa_kg=massa, x_cg=x_cg, Iyy=opc("Iyy", None, True), S=ref["S"], c_med=ref["c"], CL_alpha=ref["CLa"], Cm_alpha=ref["Cma"],
                       CL_max=float(c["vn"]["CL_max"]), Vs=float(c["vn"]["Vs"]), rho=rho, V_toque_rel=_num(p, "V_toque_rel", 1.15, positivo=True),
                       vel_descida=_num(p, "vel_descida", 1.0, positivo=True), atitude_2p_extra=_num(p, "atitude_2p_extra", 6.0),
                       sustentacao_toque_rel=_num(p, "sustentacao_toque_rel", 1.0), Cm_q=_num(p, "Cm_q", -8.0), CD=_num(p, "CD", 0.12),
                       mu_rolamento=_num(p, "mu_rolamento", R.MU_ROLAGEM), k_pneu_principal=_num(p, "k_pneu_principal", 30000.0, positivo=True),
                       k_pneu_bequilha=_num(p, "k_pneu_bequilha", 30000.0, positivo=True), k_perna_principal=opc("k_perna_principal", None, True),
                       k_perna_bequilha=opc("k_perna_bequilha", None, True), zeta=_num(p, "zeta", 0.15), curso_trem_mm=_num(p, "curso_trem_mm", 0.0),
                       perfil_pista=str(p.get("perfil_pista") or "irregular"), altura_pista_mm=_num(p, "altura_pista_mm", 5.0), comprimento_pista_m=_num(p, "comprimento_pista_m", 0.3, positivo=True),
                       V_taxi_rel=_num(p, "V_taxi_rel", 0.8, positivo=True), sustentacao_taxi_rel=_num(p, "sustentacao_taxi_rel", 0.0), fator_pouso_projeto=fator_pouso,
                       aplica_fe=bool(p.get("aplica_fe")), atrito_pouso=atrito, fe_estatico=_FE_TREM[chave_fe], **kw)
        r["ref_aero"] = ref
        r["origem_massa"] = c["origem_massa"]
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, StopIteration) as e:
        return {"erro": _erro(e)}

def flambagem(p: dict) -> dict:
    from ..nucleo.estrutura.flambagem import verifica as fl

    a = asa(p)
    if "erro" in a:
        return a
    esq = p.get("esquema") or {}
    try:
        saidas = [dict(fl(esq, x["nome"], x, mats=p.get("materiais"), qualidade_balsa=_num(p, "qualidade_balsa", 1.0, positivo=True),
                          E_transv_GPa=_num(p, "balsa_E_transv", R.BALSA["ET_sobre_EL"] * R.BALSA["E"] / R.GPA, positivo=True), knockdown=_knockdown(p),
                          margem_alvo=_num(p, "margem_alvo_flambagem", 0.0)), fontes=x["fontes"]) for x in a["asas"]]
        pior = min(saidas, key=lambda s: s["pior_pele"]["margem_pele"] if s["pior_pele"] else 1e9)
        return {"asas": saidas, "pior": pior["nome"], "critico": pior["pior_pele"], "vn": a["vn"], "avisos": a["avisos"]}
    except (ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def _succao_media(xe_c: float) -> float:
    import math
    xe = min(max(xe_c, 1e-4), 1.0)
    return 2.0 / (math.pi * xe) * (math.sqrt(xe * (1 - xe)) + math.asin(math.sqrt(xe)))

def chapeado_fe(p: dict) -> dict:
    from ..nucleo.estrutura import asa as AS
    from ..nucleo.estrutura.flambagem import verifica as fl, _fator_imperfeicao, _geom, sigma_cr_curvo, sigma_cr_ortotropica
    from ..nucleo.estrutura.materiais import propriedades
    from ..nucleo.fe import chapeado_ccx as CC

    try:
        CC.executavel()
    except CC.SemCalculix as e:
        return {"erro": str(e)}
    a = asa(p)
    if "erro" in a:
        return a
    esq = p.get("esquema") or {}
    try:
        com = [x for x in a["asas"] if ((AS._elemento(esq, x["nome"]).get("estrutura") or {}).get("chapeado"))]
        if not com:
            return {"erro": "Nenhuma asa com chapeado declarado."}
        nome = p.get("asa") if p.get("asa") in [x["nome"] for x in com] else None
        E_tr = _num(p, "balsa_E_transv", R.BALSA["ET_sobre_EL"] * R.BALSA["E"] / R.GPA, positivo=True) * 1e9
        qb = _num(p, "qualidade_balsa", 1.0, positivo=True)
        cand = []
        for x in com:
            if nome and x["nome"] != nome:
                continue
            f = fl(esq, x["nome"], x, mats=p.get("materiais"), qualidade_balsa=qb, E_transv_GPa=E_tr / 1e9, knockdown=_knockdown(p))
            for pn in f["paineis"]:
                if "margem_pele" in pn and pn["sigma_pele_MPa"] > 0:
                    cand.append((x, pn))
        if not cand:
            return {"erro": "Nenhuma baia de chapeado em compressao."}
        if p.get("baia"):
            y0, y1 = (float(v) for v in p["baia"])
            x, pn = min(cand, key=lambda c: abs(c[1]["y0"] - y0) + abs(c[1]["y1"] - y1))
        else:
            x, pn = min(cand, key=lambda c: c[1]["margem_pele"])
        y0, y1, ym = pn["y0"], pn["y1"], 0.5 * (pn["y0"] + pn["y1"])
        el = AS._elemento(esq, x["nome"])
        yy = np.array(x["y"])
        k_caso = max(range(len(x["casos"])), key=lambda k: float(np.interp(ym, yy, x["casos"][k]["tensao_MPa"]["pele_comp"])))
        sigma = float(np.interp(ym, yy, x["casos"][k_caso]["tensao_MPa"]["pele_comp"])) * 1e6
        c = cargas(p)
        caso = next(k for k in c["casos"] if k["nome"] == x["casos"][k_caso]["caso"])
        sup = next(s for s in caso["superficies"] if s["nome"] == x["nome"])
        L = sup["lados"].get("dir") or sup["lados"].get("esq")
        l_m = abs(float(np.interp(ym, np.abs(L["y"]), L["sustentacao_por_m"])))
        sec_el, xs, Z = AS._perfis(el, esq)
        q = AG._secao_em(sec_el, ym); corda = float(q[3])
        xe = AS._fim_do_chapeado(el["estrutura"]["chapeado"], ym)
        sf = float(a["asas"][0]["fator_seguranca"])
        dp = _num(p, "dp_Pa", None) if p.get("dp_Pa") is not None else sf * 0.5 * _succao_media(xe) * l_m / corda
        m = {k: propriedades(k, esq, p.get("materiais")) for k in sorted({"balsa", "tubo_carbono", "spruce"})}
        i, t = AG._no_vao(sec_el, ym)
        zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
        zln = AS.secao(el["estrutura"], xs, zs, zi, corda, ym, m)["zna"]
        r = CC.analisa_baia(esq, x["nome"], y0, y1, sigma, dp, imperf_t=_num(p, "imperfeicao_t", 0.5), z_LN=zln, E_transv=E_tr,
                            mats=p.get("materiais"), qualidade_balsa=qb)
        mb = propriedades("balsa", esq, p.get("materiais"), qb)
        cc, arco, area, Rr = _geom(sec_el, xs, Z, el, el["estrutura"], ym)
        ts = float(el["estrutura"]["chapeado"].get("espessura", 0.001))
        an_curvo = sigma_cr_curvo(mb["E"], E_tr, mb["G"], mb["nu"], ts, y1 - y0, arco, Rr, 1.0)
        r.update({"asa": x["nome"], "caso": caso["nome"], "corda": corda, "sustentacao_por_m": l_m, "fator_seguranca": sf, "z_LN": zln,
                  "analitico": {"sigma_cr_curvo_MPa": an_curvo / 1e6, "sigma_cr_plano_MPa": sigma_cr_ortotropica(mb["E"], E_tr, mb["G"], mb["nu"], ts, y1 - y0, arco) / 1e6,
                                "knockdown_sp8007": _fator_imperfeicao(None, Rr, ts), "margem_estimada": pn["margem_pele"]},
                  "margem_fe": (r["sigma_flambagem_MPa"] / (sigma / 1e6) - 1.0) if r.get("sigma_flambagem_MPa") else None})
        r["avisos"] = ["Baia isolada entre duas nervuras tidas como rigidas no proprio plano; a tensao de flexao vem da analise de viga e a "
                       "pressao e a da placa plana na regiao do chapeado, metade no extradorso (hipotese). Flambagem com imperfeicao: "
                       "o criterio e a pele sair uma espessura do lugar."]
        return r
    except (ValueError, FileNotFoundError, KeyError, StopIteration, RuntimeError) as e:
        return {"erro": _erro(e)}

def torcao(p: dict) -> dict:
    from ..nucleo.estrutura.torcao import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        saidas = []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            saidas.append(analisa(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                                  Vd=_vd(p), fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                                  x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                  eficiencia=_num(p, "eficiencia_comando", 0.85, positivo=True), calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True),
                                  ea_desloc_c=_num(p, "ea_desloc_c", 0.0), calib_EI=_num(p, "calib_EI", 1.0, positivo=True)))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        com_vr = [s for s in saidas if s["VR"] is not None]
        pior = min(com_vr, key=lambda s: s["VR"]) if com_vr else saidas[0]
        return {"asas": saidas, "pior": pior["nome"], "VR": pior["VR"], "V_requerida": pior["V_requerida"], "margem_VR": pior["margem_VR"],
                "avisos": sorted({a for s in saidas for a in s["avisos"]}) + _sem_longarina(esq)}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def torcao_fe(p: dict) -> dict:
    from ..nucleo.estrutura.asa_fe import verifica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            achados = [(k, next((s for s in caso["superficies"] if s["nome"] == e["nome"]), None)) for k, caso in enumerate(c["casos"])]
            achados = [(k, s) for k, s in achados if s is not None]
            if not achados:
                continue
            k, sup = max(achados, key=lambda t: abs(t[1]["fletor_raiz"]))
            lado = sup["lados"].get("dir") or sup["lados"].get("esq")
            r = verifica(esq, e["nome"], lado, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                         Vd=_vd(p), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                         cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True), calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True),
                         ea_desloc_c=_num(p, "ea_desloc_c", 0.0), calib_EI=_num(p, "calib_EI", 1.0, positivo=True))
            r["caso"] = c["casos"][k]["nome"]
            saidas.append(r)
            avisos += r["avisos"]
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        return {"asas": saidas, "vn": c["vn"], "massa_kg": c["massa_kg"], "avisos": sorted(set(avisos + c["avisos"]))}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def juncao(p: dict) -> dict:
    from ..nucleo.estrutura import juncao as JN
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        tipos = tuple(p.get("tipos") or ("solda", "parafuso:x", "rotula"))
        for e in esq.get("elementos", []):
            if not _com_longarina(e) or (p.get("asa") and e["nome"] != p["asa"]):
                continue
            achados = [(k, next((s for s in caso["superficies"] if s["nome"] == e["nome"]), None)) for k, caso in enumerate(c["casos"])]
            achados = [(k, s) for k, s in achados if s is not None]
            if not achados:
                continue
            k, sup = max(achados, key=lambda t: abs(t[1]["fletor_raiz"]))
            lado = sup["lados"].get("dir") or sup["lados"].get("esq")
            try:
                r = JN.analisa(esq, e["nome"], lado, mats=p.get("materiais"), tipos=tipos, x_apoio=_num(p, "x_apoio", 0.30),
                               raio_ligacao=_num(p, "raio_ligacao", 0.06, positivo=True), fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                               K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True), Vd=_vd(p), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                               calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True))
            except ValueError as x:
                avisos.append(f"{e['nome']}: {_erro(x)}")
                continue
            r["caso"] = c["casos"][k]["nome"]
            saidas.append(r)
            avisos += r["avisos"]
        if not saidas:
            return {"erro": "Nenhuma asa com longarina pôde ser ligada à treliça. " + " ".join(avisos)} if avisos else {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        return {"asas": saidas, "avisos": list(dict.fromkeys(avisos))}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def _massa_real(p: dict) -> dict | None:
    m = p.get("massa_real")
    if not m or not m.get("usar"):
        return None
    adic = []
    for a in m.get("adicionais") or []:
        b = {"nome": str(a.get("nome") or "adicional")}
        if a.get("asa"):
            b["asa"] = str(a["asa"])
        for k in ("massa_kg", "y_m", "y_fim_m", "x_c", "largura_c", "gramatura_g_m2", "de_xc", "ate_xc"):
            if a.get(k) not in (None, ""):
                b[k] = _num(a, k)
        if "massa_kg" not in b and "gramatura_g_m2" not in b:
            continue
        adic.append(b)
    med = {}
    for asa, d in (m.get("medidas") or {}).items():
        med[asa] = {k: _num(d, k, positivo=True) for k in ("massa_medida_kg", "x_cg_medido_c", "y_cg_medido_m") if d.get(k) not in (None, "")}
    return {"usar": True, "adicionais": adic, "medidas": med}

def massa_asa(p: dict) -> dict:
    from ..nucleo.estrutura.flutter import dados_de_vibracao, itens_de_massa, modos_de_vibracao
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        mr = _massa_real(p) or {"usar": True, "adicionais": []}
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        itens = itens_de_massa(esq)
        saidas = []
        decl = {e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "ponto"}
        pontos = [q for q in itens if q["nome"] in decl and abs(q["cg"][1]) > 0.05]
        for nome in asas:
            d = dados_de_vibracao(esq, nome, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p),
                                  x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                  calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                  ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens,
                                  massa_real=mr)
            ref = dados_de_vibracao(esq, nome, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p),
                                    x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                    calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                    ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens)
            pf = d["perfil_massa"]

            def freq(dd):
                c = dd["c"]
                xa = dd["x_alfa_c"] * c
                m = dd["m_lin"]
                return modos_de_vibracao(dd["y"], dd["EI"], dd["GJ"], m, m * xa, m * ((dd["r_giro_c"] * c) ** 2 + xa ** 2), 6)
            fr, f0 = freq(d), freq(ref)
            pf.update({"nome": nome, "f_hz": fr["f_hz"], "natureza": fr["natureza"], "f_hz_hipotese_antiga": f0["f_hz"], "natureza_hipotese_antiga": f0["natureza"],
                       "massa_hipotese_antiga_kg": ref["M"], "x_cg_c_hipotese_antiga": ref["xcg"]})
            saidas.append(pf)
        aviso = []
        if pontos:
            aviso.append("Massas pontuais do modelo fora do eixo (servo, motor na asa?): " + ", ".join(f"{q['nome']} ({q['massa']:.3f} kg em y = {q['cg'][1]:+.2f} m)" for q in pontos)
                         + ". Nao entram sozinhas: declare-as como adicionais da asa certa.")
        return {"asas": saidas, "avisos": aviso}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def flutter(p: dict) -> dict:
    from ..nucleo.estrutura.flutter import analisa_flutter, itens_de_massa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        saidas = []
        itens = itens_de_massa(esq) if any(e.get("tipo") == "asa" and e.get("estrutura") for e in esq.get("elementos", [])) else None
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            saidas.append(analisa_flutter(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                                          Vd=_vd(p), fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                                          x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                          calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                                          massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                                          x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                                          r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), zeta_s=_num(p, "zeta_s", 0.0),
                                          calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                          V_max_rel=_num(p, "V_max_rel", 3.0, positivo=True), n_modos=int(_num(p, "n_modos", positivo=True)) if p.get("n_modos") else None, itens=itens,
                                          massa_real=_massa_real(p), aileron=_aileron_par(p), varre=bool(p.get("varre_aileron")) and p.get("asa_varredura") in (None, e["nome"])))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        com = [s for s in saidas if s["VF"] is not None]
        pior = min(com, key=lambda s: s["VF"]) if com else saidas[0]
        return {"asas": saidas, "pior": pior["nome"], "VF": pior["VF"], "V_requerida": pior["V_requerida"], "margem_VF": pior["margem_VF"],
                "avisos": sorted({a for s in saidas for a in s["avisos"]})}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def flutter_tempo(p: dict) -> dict:
    import time
    from ..nucleo.estrutura.flutter import itens_de_massa
    from ..nucleo.estrutura.flutter_tempo import analisa_no_tempo
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    esq = p.get("esquema") or {}
    try:
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        nome = p.get("asa") if p.get("asa") in asas else asas[0]
        itens = itens_de_massa(esq)
        t0 = time.time()
        extra = {}
        if p.get("fatores"):
            extra["fatores"] = tuple(float(x) for x in p["fatores"])
        if p.get("n_ciclos"):
            extra["n_ciclos"] = _num(p, "n_ciclos", positivo=True)
        r = analisa_no_tempo(esq, nome, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p), **extra,
                             aileron=_aileron_par(p), zeta_s=_num(p, "zeta_s", 0.0),
                             n_modos=int(_num(p, "n_modos", positivo=True)) if p.get("n_modos") else None,
                             forcar=bool(p.get("forcar")), mats=p.get("materiais"),
                             fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                             x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                             calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                             ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                             massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                             x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                             r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), itens=itens, massa_real=_massa_real(p))
        r["tempo_s"] = time.time() - t0
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def aeroelastica(p: dict) -> dict:
    from ..nucleo.estrutura.aeroelastica_estatica import estatica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        A = AG.constroi(esq)
        mc = AG.massa_e_cg(A)
        massa = _num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else mc["massa_kg"]
        if not massa or massa <= 0:
            return {"erro": "Sem massa: este modelo ainda nao tem pecas com massa. Abra o exemplo de biplano (botao Primeiros passos), declare a estrutura das asas na etapa 1 (aba Estrutura) ou informe a massa."}
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        r = estatica(esq, V=_num(p, "V", positivo=True), n=_num(p, "n", 1.0, positivo=True), massa_kg=massa, x_cg=x_cg,
                     z_cg=float(cg[2]) if cg else 0.0, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), mats=p.get("materiais"),
                     calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                     ea_desloc_c=_num(p, "ea_desloc_c", 0.0), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                     cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True))
        r["origem_massa"] = "informada" if p.get("massa_kg") is not None else "massas do modelo"
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def calibracao(p: dict) -> dict:
    from ..nucleo.estrutura.calibracao import calibra
    from ..nucleo.estrutura.flutter import itens_de_massa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        nome = p.get("asa") or asas[0]
        if nome not in asas:
            return {"erro": f"A asa {nome!r} nao tem estrutura declarada."}
        r = calibra(esq, nome, p.get("observacoes") or {}, ajusta=tuple(p.get("ajusta") or ("EI", "GJ")), mats=p.get("materiais"),
                    rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                    cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True), ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                    massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                    x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                    r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), itens=itens_de_massa(esq), massa_real=_massa_real(p))
        r["asas"] = asas
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def cauda(p: dict) -> dict:
    from ..nucleo.estrutura.cauda import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        aviso = []
        c = cargas(p) if p.get("com_cargas", True) else {"erro": "nao pedidas"}
        if "erro" in c:
            casos, peso = None, _num(p, "peso_N", 0.0)
            aviso.append("Sem as cargas do V-n (" + str(c["erro"]) + "): o caso de trim da empenagem ficou em zero.")
        else:
            casos, peso = c["casos"], c["massa_kg"] * 9.80665
        r = analisa(esq, casos, peso_N=peso, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vc=_num(p, "Vc", positivo=True),
                    Vd=_vd(p), U_c=_num(p, "U_c", R.RAJADA_VC_MS, positivo=True),
                    fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), x_apoio=_num(p, "x_apoio", 0.30),
                    CL_max_h=_num(p, "CL_max_h", 0.8, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                    tailstrike_peso=_num(p, "tailstrike_peso", 0.0), mats=p.get("materiais"),
                    qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True),
                    juntas={k: _num(p, "junta_" + k, None) for k in ("tau_cola_MPa", "comprimento_cola_de", "Kt", "d_parafuso_mm", "tau_parafuso_MPa", "esmagamento_MPa") if p.get("junta_" + k) is not None})
        r["avisos"] = aviso + r["avisos"]
        r["peso_N"] = peso
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def vibracao(p: dict) -> dict:
    from ..nucleo.aero import propulsao as PR
    from ..nucleo.estrutura import vibracao as VB
    from ..nucleo.estrutura.flutter import dados_de_vibracao, itens_de_massa, modos_de_vibracao
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        aviso = []
        rpm_v = None
        rpm_min, rpm_max = _num(p, "rpm_min", 3000.0, positivo=True), _num(p, "rpm_max", 9000.0, positivo=True)
        if p.get("motor") and p.get("helice"):
            try:
                cur = PR.curva(str(p["motor"]), str(p["helice"]), P_w=_num(p, "P_w", 600.0, positivo=True), rho=_num(p, "rho", 1.1, positivo=True),
                               V_max=_num(p, "V_max", 30.0, positivo=True), realista=bool(p.get("realista", True)))
            except ValueError as e:
                return {"erro": _erro(e)}
            if "erro" in cur:
                return cur
            rpm_v = {"V": cur["V"], "rpm": cur["rpm"]}
            rpm_min, rpm_max = float(min(cur["rpm"])), float(max(cur["rpm"]))
            aviso.append(f"Faixa de rotacao da curva do motor com a helice: {rpm_min:.0f} a {rpm_max:.0f} rpm (de parado ate {_num(p, 'V_max', 30.0):g} m/s).")
        externos = []
        if p.get("incluir_asas", True):
            mr = _massa_real(p) or {"usar": True, "adicionais": []}
            itens = itens_de_massa(esq)
            for e in esq.get("elementos", []):
                if e.get("tipo") != "asa" or not e.get("estrutura"):
                    continue
                try:
                    d = dados_de_vibracao(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", 1.1, positivo=True), Vd=_num(p, "Vd", 15.9, positivo=True),
                                          x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                          calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                          ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens, massa_real=mr)
                except ValueError as ex:
                    aviso.append(f"“{e['nome']}” ficou fora dos modos externos: {_erro(ex)}.")
                    continue
                c = d["c"]; xa = d["x_alfa_c"] * c; m_ = d["m_lin"]
                fr = modos_de_vibracao(d["y"], d["EI"], d["GJ"], m_, m_ * xa, m_ * ((d["r_giro_c"] * c) ** 2 + xa ** 2), 3)
                for k, (f, nat) in enumerate(zip(fr["f_hz"], fr["natureza"])):
                    externos.append({"nome": f"{e['nome']} {k + 1} ({'flexao' if nat == 'flexao' else 'torcao'})", "f_hz": float(f), "natureza": nat})
        pos_motor = p.get("pos_motor")
        if pos_motor is not None and (not isinstance(pos_motor, (list, tuple)) or len(pos_motor) != 3):
            return {"erro": "“pos_motor” precisa ser [x, y, z] em metros."}
        adic = [a for a in (p.get("adicionais") or []) if isinstance(a, dict)]
        r = VB.analisa(esq, massa_empenagem_h_kg=_num(p, "massa_empenagem_h_kg", 0.0), massa_deriva_kg=_num(p, "massa_deriva_kg", 0.0),
                       massa_motor_kg=_num(p, "massa_motor_kg", 0.0), pos_motor=pos_motor, adicionais=adic, rpm_min=rpm_min, rpm_max=rpm_max,
                       n_pas=int(_num(p, "n_pas", 2.0, positivo=True)), ordens_extra=[_num({"k": k}, "k", positivo=True) for k in (p.get("ordens_extra") or [])],
                       margem_min=_num(p, "margem_min", 0.20, positivo=True), x_apoio=_num(p, "x_apoio", 0.30), mats=p.get("materiais"),
                       qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True), raio_motor=_num(p, "raio_motor", 0.15, positivo=True),
                       n_modos=int(_num(p, "n_modos", 8.0, positivo=True)), suporte_motor=p.get("suporte_motor") or None, modos_externos=externos, rpm_v=rpm_v)
        r["avisos"] = aviso + r["avisos"]
        r["rpm_v"] = rpm_v
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def _cargas(p: dict) -> dict:
    from ..nucleo.aero.equilibrio import monta
    from ..nucleo.aero.estabilidade import derivadas
    from ..nucleo.aero.limites import cl_max as cl_max_aeronave
    from ..nucleo.estrutura.cargas import casos_de_carga
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        Vc = _num(p, "Vc", positivo=True)
        Vd = _vd(p)
        if Vd <= Vc:
            return {"erro": "Vd precisa ser maior que Vc."}
        A = AG.constroi(esq)
        mc = AG.massa_e_cg(A)
        massa = _num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else mc["massa_kg"]
        if not massa or massa <= 0:
            return {"erro": "Sem massa: este modelo ainda nao tem pecas com massa. Abra o exemplo de biplano (botao Primeiros passos), declare a estrutura das asas na etapa 1 (aba Estrutura) ou informe a massa."}
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        z_cg = float(cg[2]) if cg else 0.0
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        vlm = monta(esq, x_cg, z_cg)
        d = derivadas(vlm, 3.0, V=Vc, rho=rho, laterais=False)
        avisos = []
        if p.get("CL_max") is not None:
            clm, origem = _num(p, "CL_max", positivo=True), "voce"
        else:
            ncrit = int(_num(p, "ncrit", 4.0, positivo=True))
            chave = (json.dumps(esq, sort_keys=True, default=str), round(x_cg, 6), round(Vc, 3), round(rho, 4), ncrit)
            if chave not in _CL_MAX:
                if len(_CL_MAX) > 8:
                    _CL_MAX.clear()
                _CL_MAX[chave] = float(cl_max_aeronave(esq, x_cg, V=Vc, rho=rho, ncrit=ncrit, com_solo=False)["CL_max"])
            clm, origem = _CL_MAX[chave], "teoria de faixas (polares do banco)"
        sai = casos_de_carga(esq, x_cg, z_cg, massa, rho, clm, float(d.CL_alpha), float(vlm.c_ref), float(vlm.S_ref), Vc, Vd,
                             n_max=None if p.get("n_max") is None else _num(p, "n_max", positivo=True),
                             n_min=None if p.get("n_min") is None else _num(p, "n_min"),
                             U_c=_num(p, "U_c", R.RAJADA_VC_MS, positivo=True), U_d=_num(p, "U_d", R.RAJADA_VD_MS, positivo=True),
                             fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                             cl_min_rel=_num(p, "cl_min_rel", 0.5, positivo=True))
        for c in sai["casos"]:
            if c["CL"] > clm * 1.001:
                avisos.append(f"{c['nome']}: o CL pedido ({c['CL']:.2f}) passa do CL maximo ({clm:.2f}): a aeronave estola antes; "
                              "a carga real e menor que a calculada.")
        sai["avisos"] = avisos + sai["avisos"]
        sai.update(massa_kg=massa, origem_CL_max=origem, origem_massa="informada" if p.get("massa_kg") is not None else "massas do modelo")
        return sai
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}
