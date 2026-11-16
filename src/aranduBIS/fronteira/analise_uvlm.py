from __future__ import annotations

import math
from pathlib import Path
import numpy as np
from ..nucleo import referencias as R
from ..nucleo import discretizacao as D
from .analise_comum import ErroDeAnalise, _erro, _num

def uvlm(p: dict) -> dict:
    import time
    import warnings
    from ..nucleo.aero import rll as RL
    from ..nucleo.aero import uvlm as U
    from ..nucleo.aero.aeronave_vlm import superficies
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        if p.get("V") is None:
            raise ErroDeAnalise("Informe a velocidade (ou a Vc na vista Cargas).")
        V = _num(p, "V", positivo=True)
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        alpha = _num(p, "alpha", 0.0)
        caso = p.get("caso", "degrau")
        if caso not in ("degrau", "rajada_degrau", "rajada_1cos", "mergulho", "arfagem"):
            raise ErroDeAnalise("Caso desconhecido: use degrau, rajada_degrau, rajada_1cos, mergulho ou arfagem.")
        esteira = p.get("esteira") or ("livre" if p.get("esteira_livre") else "rigida")
        if esteira not in ("rigida", "livre", "particulas"):
            raise ErroDeAnalise("Esteira: use rigida, livre ou particulas.")
        gira = bool(p.get("helice_girante"))
        avisos_pre = []
        solo_on = bool(p.get("solo"))
        subida = _num(p, "subida", 0.0) if solo_on else 0.0
        if solo_on and subida != 0 and esteira == "rigida":
            avisos_pre.append("Efeito solo com a altura mudando: a esteira rígida não acompanha o chão se movendo, então virou livre.")
            esteira = "livre"
        if gira and esteira != "particulas":
            avisos_pre.append("Hélice girante: a esteira dela é de partículas, então a da asa também virou partículas.")
            esteira = "particulas"
        livre = esteira != "rigida"
        manual = p.get("discretizacao") == "manual"
        H_cordas = _num(p, "H_cordas", 25.0, positivo=True) if caso == "rajada_1cos" else None
        f = _num(p, "f", 5.0, positivo=True) if caso in ("mergulho", "arfagem") else None
        with warnings.catch_warnings(), D.silencio():
            warnings.simplefilter("ignore")
            pre = U.VLM(superficies(esq, n_span=8, n_chord=2))
        c_pre = pre.c_ref
        auto = U.discretizacao_auto(caso, k=(math.pi * f * c_pre / V) if f else None, H_cordas=H_cordas, esteira_livre=livre, esteira=esteira)
        if solo_on and subida != 0:
            auto["espera_cordas"] = (8.0, "a partida impulsiva assenta (Wagner ≈ 95 %) antes de a altura começar a mudar")
        if gira:
            auto.update(RL.discretizacao_auto())
            centro_h = _centro_helice(esq)
            x_fim = float(pre.aneis[..., 0].max())
            if caso == "degrau":
                n_c = int(max(8, math.ceil(max(0.0, x_fim - float(centro_h[0])) / c_pre + 3)))
                auto["cordas"] = (n_c, f"hélice girante: o sopro leva {max(0.0, x_fim - float(centro_h[0])) / c_pre:.1f} cordas "
                                       "para passar pela última superfície; + 3 cordas, no mínimo 8 (Wagner a ~90 %)")
        escolha = []

        def campo(chave, rotulo, inteiro=True):
            va, motivo = auto.get(chave, (None, ""))
            if manual and p.get(chave) is not None:
                x = _num(p, chave, positivo=True)
                x = int(round(x)) if inteiro else x
                escolha.append({"campo": chave, "rotulo": rotulo, "valor": x, "origem": "manual", "auto": va, "motivo": motivo})
                return x
            escolha.append({"campo": chave, "rotulo": rotulo, "valor": va, "origem": "auto", "auto": va, "motivo": motivo})
            return va

        ns = campo("n_span", "Painéis na envergadura")
        nc = campo("n_chord", "Painéis na corda")
        nc_auto = escolha[-1]["origem"] == "auto"
        with warnings.catch_warnings(), D.silencio():
            warnings.simplefilter("ignore")
            faixas = U.VLM(superficies(esq, n_span=ns, n_chord=1)).N
        por_corda = campo("passos_por_corda", "Passos por corda")
        if caso in ("mergulho", "arfagem"):
            ciclos = campo("ciclos", "Ciclos", inteiro=False)
            cordas = None
        else:
            cordas = campo("cordas", "Duração (cordas)", inteiro=False)
        if esteira == "particulas":
            fil_aneis = campo("fileiras_aneis", "Fileiras de anéis antes das partículas")
            idade_fusao = campo("idade_fusao", "Idade da 1ª fusão de partículas (passos)")
            sobre = campo("sobreposicao", "Núcleo das partículas (× V·dt)", inteiro=False)
            max_fil, fil_livres = None, None
        else:
            max_fil = campo("max_fileiras", "Fileiras de esteira (antes da cauda)")
            fil_livres = campo("fileiras_livres", "Fileiras que enrolam") if livre else None
        nucleo = campo("nucleo", "Núcleo dos vórtices (× corda)", inteiro=False)
        if gira:
            nome_h, cat_h, pa_h, perfil_h, _ = _helice_catalogo(p)
            rpm = _num(p, "rpm", 4000.0, positivo=True)
            sentido = -1 if p.get("sentido") in (-1, "-1", "anti") else 1
            dpsi = campo("dpsi", "Giro da hélice por subpasso (graus)", inteiro=False)
            n_el = campo("n_el", "Elementos por pá")
            rolagem = campo("voltas_rolagem", "Enrolamento da esteira da hélice (voltas)", inteiro=False)
            Om = 2 * math.pi * rpm / 60.0
            comp_h = max(x_fim + 0.5 * pre.b_ref - float(centro_h[0]), 4 * pa_h.R)
        nuc_part = p.get("nucleo_particula") if (manual and p.get("nucleo_particula") in ("gaussiano", "winckelmans")) else "gaussiano"

        def passos_de(ppc):
            return int(math.ceil(ciclos * math.pi / (math.pi * f * c_pre / V) * ppc)) if cordas is None else int(math.ceil(cordas * ppc))

        def custo(nc_):
            if gira:
                dt_ = c_pre / (por_corda * V)
                n_sub = max(1, int(round(dt_ * Om / math.radians(dpsi))))
                dts = dt_ / n_sub
                return D.custo_rll(nc_ * faixas, faixas, passos_de(por_corda), n_sub, pa_h.B, n_el,
                                   rolagem * 2 * math.pi / (Om * dts), int(math.ceil(comp_h / (V * dts))), fil_aneis, idade_fusao)
            if esteira == "particulas":
                return D.custo_vpm(nc_ * faixas, faixas, passos_de(por_corda), fil_aneis, idade_fusao)
            return D.custo_uvlm(nc_ * faixas, faixas, passos_de(por_corda), max_fil, livre, fil_livres)
        if solo_on:
            custo_sem_solo = custo

            def custo(nc_):
                c_ = dict(custo_sem_solo(nc_))
                c_["segundos"] *= 2.0; c_["interacoes"] *= 2.0
                return c_
        est = custo(nc)
        if nc_auto and est["segundos"] > D.orcamento_s() and nc > 4:
            nc0 = nc
            while nc > 4 and custo(nc)["segundos"] > D.orcamento_s():
                nc -= 1
            escolha[1]["valor"] = nc
            escolha[1]["motivo"] += f"; reduzido de {nc0} para {nc} para caber no orçamento de {D.orcamento_s():.0f} s"
            est = custo(nc)
        try:
            D.confere_orcamento(est, "Marcha do UVLM" + (" com a hélice girante" if gira else ""), forcar=bool(p.get("forcar")))
        except ValueError as e:
            if not gira:
                raise
            raise ErroDeAnalise(f"{e} Com a hélice girante o custo vem do tempo físico × rpm / giro por subpasso, com "
                                f"~{est['particulas']} partículas no fim: duração mais curta ou giro de 20° (modo manual; o "
                                "sopro sai ~14 % fraco) cortam o tempo.") from None
        with warnings.catch_warnings(record=True) as avisos_malha:
            warnings.simplefilter("always")
            sup = superficies(esq, n_span=ns, n_chord=nc)
            base = U.VLM(sup)
        c = base.c_ref
        dt = c / (por_corda * V)
        n_passos = int(math.ceil(cordas * por_corda)) if cordas else 0
        x_le = float(base.aneis[..., 0].min())
        x_ref = _num(p, "x_ref", x_le + 0.25 * c) if p.get("x_ref") is not None else x_le + 0.25 * c
        altura_fn = None
        if solo_on:
            from ..nucleo.aero import limites as LI
            if p.get("altura_solo") is not None:
                h0 = _num(p, "altura_solo", positivo=True); origem_h = "informada"
            else:
                h0 = LI.altura_do_solo(esq, alpha, x_ref)
                if h0 is None or h0 <= 0:
                    raise ErroDeAnalise("Efeito solo: informe a altura do solo (o modelo não tem rodas para medir).")
                origem_h = "pelas rodas"
            esp = campo("espera_cordas", "Espera antes de mudar a altura (cordas)", inteiro=False) if subida != 0 else 0.0
            t_esp = esp * c / V

            def altura_fn(t, h0=h0, vs=subida, t_esp=t_esp):
                return h0 + vs * max(0.0, t - t_esp)
            if subida == 0:
                altura_fn = h0
        mov = raj = None
        alpha_corrida = alpha
        ref = {}
        CLa = (base.resolver([1.0], V=V, rho=rho)[0].CL - base.resolver([0.0], V=V, rho=rho)[0].CL) * 180 / math.pi
        if caso == "degrau":
            pass
        elif caso in ("rajada_degrau", "rajada_1cos"):
            w0 = _num(p, "w0", 2.0)
            if caso == "rajada_degrau":
                raj = U.rajada_degrau(w0, V, x_le)
            else:
                H = H_cordas * c
                raj = U.rajada_1_cos(w0, H, V, x_le)
                if cordas < H_cordas:
                    avisos_pre.append(f"A duração ({cordas:g} cordas) acaba antes da rajada passar ({H_cordas:g} cordas).")
        else:
            amp = _num(p, "amplitude", 0.02 if caso == "mergulho" else 2.0, positivo=True)
            n_passos = int(math.ceil(ciclos / (f * dt)))
            mov = U.movimento_mergulho(amp, f) if caso == "mergulho" else U.movimento_arfagem(amp, f, x_ref, V)
        avisos = list(avisos_pre)
        if solo_on and subida != 0 and n_passos * dt <= t_esp:
            avisos.append(f"A duração ({n_passos * dt:.3f} s) acaba antes de a altura começar a mudar ({t_esp:.3f} s de espera).")
        if gira:
            t_sopro = (x_fim - float(centro_h[0])) / V
            dur = n_passos * dt
            if dur < t_sopro:
                avisos.append(f"A duração ({dur:.3f} s) acaba antes do sopro da hélice passar pela última superfície "
                              f"(~{t_sopro:.3f} s): aumente a duração para ver o regime.")
        if caso in ("mergulho", "arfagem"):
            k_red = math.pi * f * c / V
            err = 1.2 * k_red / nc
            if err > 0.05:
                avisos.append(f"Frequência reduzida k = {k_red:.2f} com {nc} painéis na corda: a amplitude do CL deve sair "
                              f"uns {100 * err:.0f} % acima da teoria (erro ≈ 1,2 k / n_chord). {math.ceil(24 * k_red)} painéis dão 5 %.")
        t0 = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if gira:
                u = RL.UVLMHelice(sup, V, [{"pa": pa_h, "centro": centro_h, "rpm": rpm, "sentido": sentido, "n_el": n_el}],
                                  alpha_graus=alpha_corrida, rho=rho, dt=dt, x_ref=x_ref, movimento=mov, rajada=raj,
                                  nucleo=nucleo, fileiras_aneis=fil_aneis, idade_fusao=idade_fusao, sobreposicao=sobre,
                                  nucleo_particula=nuc_part, dpsi_graus=dpsi, voltas_rolagem=rolagem,
                                  comprimento_esteira=comp_h, solo=altura_fn)
            elif esteira == "particulas":
                u = U.UVLMParticulas(sup, V=V, alpha_graus=alpha_corrida, rho=rho, dt=dt, x_ref=x_ref, movimento=mov, rajada=raj,
                                     nucleo=nucleo, fileiras_aneis=fil_aneis, idade_fusao=idade_fusao, sobreposicao=sobre,
                                     nucleo_particula=nuc_part, solo=altura_fn)
            else:
                u = U.UVLM(sup, V=V, alpha_graus=alpha_corrida, rho=rho, dt=dt, esteira_livre=livre, x_ref=x_ref,
                           movimento=mov, rajada=raj,
                           max_fileiras=max_fil, fileiras_livres=fil_livres, nucleo=nucleo, solo=altura_fn)
            inst = p.get("_instantaneos")
            if inst is None and p.get("instantaneos"):
                inst = []
            alvo = 150 if p.get("_instantaneos") is not None else 60
            h = u.roda(n_passos, a_cada=(n_passos / alvo if gira else max(1, math.ceil(n_passos / alvo))) if inst is not None else None,
                       guarda=inst)
            if inst is not None:
                p["_aneis_corpo"] = u.R.copy()
        t = np.array(h.t); s = 2 * V * t / c
        CL0 = base.resolver([alpha], V=V, rho=rho)[0].CL
        CL_livre = CL0
        if solo_on:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                def cl_solo(h, a):
                    return U.VLM(sup, x_ref=x_ref, altura_solo=h).resolver([a], V=V, rho=rho)[0].CL
                CL0 = cl_solo(h0, alpha)
                if subida != 0:
                    ts = np.linspace(t[0], t[-1], 13)
                    qs = [cl_solo(altura_fn(ti), alpha - math.degrees(math.atan2(subida if ti > t_esp else 0.0, V))) for ti in ts]
                    qs_t = np.interp(t, ts, qs)
        if caso == "degrau" and solo_on and subida != 0:
            ref = {"nome": "quase estático: VLM com solo em h(t) e α − γ, × Wagner", "y": (qs_t * U.wagner(s)).tolist()}
        elif caso == "degrau":
            ref = {"nome": "Wagner × CL estacionário" + (" com solo" if solo_on else ""), "y": (CL0 * U.wagner(s)).tolist()}
        elif caso == "rajada_degrau":
            ref = {"nome": "Küssner × CLα w0/V", "y": (CL0 + CLa * (w0 / V) * U.kussner(s)).tolist()}
        elif caso == "mergulho":
            w = 2 * math.pi * f; k = w * c / (2 * V); C = complex(U.theodorsen(k))
            hd = amp * w * np.cos(w * t); hdd = -amp * w * w * np.sin(w * t)
            circ = -(C.real * hd - C.imag * amp * w * np.sin(w * t)) / V
            ref = {"nome": "Theodorsen (faixa 2D × CLα 3D/2π)", "y": (CL0 + CLa * circ + CLa / (2 * math.pi) * math.pi * (c / 2) * (-hdd) / V ** 2).tolist(), "k": k}
        Rw, Gw = u.aneis_da_esteira()
        lado = []
        for si in u.te:
            nos = np.array(si["nos"])
            if si.get("cortada"):
                nos = nos[:-1]
            j = [0, nos.shape[1] // 2, nos.shape[1] - 1]
            lado.append({"nome": si["nome"], "x": nos[:, j, 0].T.tolist(), "z": nos[:, j, 2].T.tolist(), "y": nos[0, j, 1].tolist()})
        dec = max(1, len(t) // 400)
        extra = {"V": V, "esteira": esteira}
        if p.get("instantaneos") and p.get("_instantaneos") is None and inst:
            extra["quadros"] = _compacta_quadros(inst, u.R)
        if esteira == "particulas":
            X, A = u.part.X, u.part.A
            w = np.linalg.norm(A, axis=1)
            k = np.argsort(-w)[:4000] if len(w) > 4000 else np.arange(len(w))
            extra["particulas"] = {"x": X[k, 0].tolist(), "y": X[k, 1].tolist(), "z": X[k, 2].tolist(), "w": w[k].tolist(),
                                   "n": int(len(w)), "vorticidade_total": u.part.vorticidade_total().tolist(),
                                   "sigma_medio": float(u.part.S.mean()) if len(w) else None}
        if gira:
            from ..nucleo.aero import bemt as BM
            hh = u.hist_helice[0]
            hl = u.helices[0]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ref_h = BM.analisa(pa_h, V, rpm, rho, n_est=D.helice_n_est())
            dec_h = max(1, len(hh["t"]) // 400)
            n_ult = max(1, int(round(2 * math.pi / (Om * dt))))
            extra["helice"] = {"nome": nome_h, "perfil": perfil_h, "rpm": rpm, "sentido": sentido, "D": pa_h.D,
                               "centro": centro_h.tolist(), "n_sub": u.n_sub, "dpsi": math.degrees(Om * u.dt_sub),
                               "t": hh["t"][::dec_h], "T": hh["T"][::dec_h], "P": hh["P"][::dec_h],
                               "T_media": float(np.mean(hl.hist["T"][-n_ult * u.n_sub:])),
                               "P_media": float(np.mean(hl.hist["P"][-n_ult * u.n_sub:])),
                               "T_bemt": ref_h.T, "P_bemt": ref_h.P, "J": ref_h.J,
                               "particulas": int(np.sum(u.part.fila >= RL.ID_HELICE)),
                               "comprimento_esteira": u.comprimento_esteira}
        if caso.startswith("rajada"):
            extra["w0"] = w0
        if caso in ("mergulho", "arfagem"):
            extra["k"] = math.pi * f * c / V
        for e in escolha:
            if e["campo"] == "n_span" and e["valor"] is None:
                e["valor"] = ", ".join(f"{q.nome} {q.n_span}" for q in sup)
        extra["estimativa_s"] = est["segundos"]
        if solo_on:
            hs = [altura_fn(ti) for ti in t] if callable(altura_fn) else [h0] * len(t)
            extra["solo"] = {"h0": h0, "origem": origem_h, "subida": subida, "espera_s": t_esp, "CL_livre": CL_livre,
                             "CL_solo": CL0, "h": hs[::dec], "b": float(base.b_ref)}
        return {**extra, "discretizacao": escolha, "modo_discretizacao": "manual" if manual else "auto", "caso": caso, "t": t[::dec].tolist(), "s": s[::dec].tolist(), "CL": h.CL[::dec], "CD": h.CD[::dec], "Cm": h.Cm[::dec],
                "ref": ({k: (v[::dec] if isinstance(v, list) else v) for k, v in ref.items()} if ref else None),
                "CL_estacionario": CL0, "CL_alpha": CLa, "c_ref": c, "S_ref": base.S_ref, "dt": dt, "passos": n_passos,
                "paineis": base.N, "aneis_esteira": int(len(Gw)), "esteira_lado": lado, "esteira_livre": livre, "x_ref": x_ref,
                "tempo_s": time.time() - t0,
                "avisos": sorted({str(a.message) for a in avisos_malha}) + avisos}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def _compacta_quadros(inst: list, R_corpo, max_part: int = 3000, max_fileiras: int = 30) -> dict:
    wtodos = [q["w"] for q in inst if "w" in q and len(q["w"])]
    wref = float(np.percentile(np.concatenate(wtodos), 99)) if wtodos else 1.0
    quadros = []
    for q in inst:
        d = {"t": round(float(q["t"]), 5), "CL": round(float(q["CL"]), 5), "aneis": []}
        for a in q["aneis"]:
            a = np.asarray(a)
            if a.shape[0] > max_fileiras + 1:
                a = a[np.unique(np.r_[np.linspace(0, a.shape[0] - 1, max_fileiras + 1).round().astype(int)])]
            d["aneis"].append({"n": [int(a.shape[0]), int(a.shape[1])], "p": np.round(a.reshape(-1), 3).tolist()})
        if q.get("pas"):
            d["pas"] = [np.round(np.asarray(a).reshape(-1), 4).tolist() for a in q["pas"]]
        if q.get("solo"):
            d["solo"] = {k: np.round(v, 4).tolist() for k, v in q["solo"].items()}
        if "X" in q and len(q["X"]):
            k = np.unique(np.linspace(0, len(q["X"]) - 1, min(len(q["X"]), max_part)).round().astype(int))
            w = np.clip(np.log10(np.maximum(q["w"][k] / wref, 1e-3)) / 3 + 1, 0, 1)
            d["X"] = np.round(q["X"][k].reshape(-1), 3).tolist()
            d["w"] = (w * 255).round().astype(int).tolist()
            d["n_part"] = int(len(q["X"]))
        quadros.append(d)
    return {"corpo": np.round(np.asarray(R_corpo).reshape(-1), 4).tolist(), "quadros": quadros}

def uvlm_video(p: dict) -> tuple[bytes, str]:
    from ..nucleo import anima
    q = dict(p)
    q["_instantaneos"] = []
    r = uvlm(q)
    if "erro" in r:
        raise ErroDeAnalise(r["erro"])
    nomes = {"degrau": "partida impulsiva", "rajada_degrau": "rajada degrau", "rajada_1cos": "rajada 1-cos",
             "mergulho": "mergulho harmônico", "arfagem": "arfagem harmônica"}
    est = {"rigida": "esteira rígida", "livre": "esteira livre de anéis", "particulas": "esteira de partículas de vórtice"}
    nome = (p.get("esquema") or {}).get("nome", "")
    titulo = f"{nome} · {nomes.get(r['caso'], r['caso'])} · {est.get(r['esteira'], '')} · V = {r['V']:.1f} m/s"
    if r.get("helice"):
        hh = r["helice"]
        titulo += f" · hélice {hh['nome']} a {hh['rpm']:.0f} rpm"
    if r.get("solo"):
        ss = r["solo"]
        titulo += f" · solo a {ss['h0']:.2f} m" + (f", subindo {ss['subida']:.1f} m/s" if ss["subida"] > 0 else
                                                     f", descendo {-ss['subida']:.1f} m/s" if ss["subida"] < 0 else "")
    return anima.esteira(q["_instantaneos"], q["_aneis_corpo"], titulo=titulo, codec=p.get("codec", "h264"),
                         largura=int(p.get("largura", 1280)))

def _helice_catalogo(p: dict):
    from ..nucleo.aero import bemt as BM
    from ..nucleo.aero.apc import catalogo
    from ..nucleo.aero.polares import BancoPolares, estender_viterna
    nome = str(p.get("helice") or "22x10E")
    h = catalogo().get(nome)
    if h is None:
        raise ErroDeAnalise(f"Hélice {nome} fora do catálogo APC Thin Electric.")
    banco = BancoPolares.carregar_npz(Path(__file__).resolve().parents[3] / "data" / "polares.npz")
    chave = str(p.get("perfil") or "CLARK_Y_AIRFOIL@n7")
    if chave not in banco:
        raise ErroDeAnalise(f"Perfil {chave} não está no banco de polares.")
    pol = estender_viterna(banco[chave])
    return nome, h, BM.apc_tipica(h.D_pol, h.passo_pol, pol), chave, pol

def _centro_helice(esq: dict):
    el = next((e for e in esq.get("elementos", []) if "helic" in str(e.get("nome", "")).lower()), None)
    if el is not None:
        return np.asarray(el.get("posicao", [0, 0, 0]), float)
    xs = [e.get("posicao", [0, 0, 0])[0] for e in esq.get("elementos", []) if e.get("tipo") == "asa"]
    return np.array([min(xs) - 0.15 if xs else -0.3, 0.0, 0.0])

def helice(p: dict) -> dict:
    import warnings
    from ..nucleo.aero import bemt as BM
    from ..nucleo.aero.aeronave_vlm import superficies
    from ..nucleo.aero.vlm import VLM
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    try:
        nome, h, pa, chave, pol = _helice_catalogo(p)
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        rpm = _num(p, "rpm", 4000.0, positivo=True)
        V = _num(p, "V", 12.0)
        alpha = _num(p, "alpha", 4.0)
        sentido = -1 if p.get("sentido") in (-1, "-1", "anti") else 1
        n_est = D.helice_n_est()
        n = rpm / 60.0
        J_max = 1.2 * h.passo_pol / h.D_pol
        Js = np.linspace(0.0, J_max, 31)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            curva = BM.curva(pa, rpm, Js, rho, n_est=n_est)
            ct_apc, cp_apc = h.coeficientes(Js, rpm)
            op = BM.analisa(pa, V, rpm, rho, n_est=n_est)
        avisos = ["Geometria da pá: forma média das APC Thin Electric (corda típica, passo constante pelo nome). "
                  "Com a geometria medida (UIUC) a previsão melhora; a curva da APC é cálculo do fabricante, não ensaio."]
        if np.any(op.Re < pol.re[0]) or np.any(op.Re > pol.re[-1]):
            avisos.append(f"Reynolds na pá de {op.Re.min():.0f} a {op.Re.max():.0f}; as polares de {chave} vão de "
                          f"{pol.re[0]:.0f} a {pol.re[-1]:.0f}: fora disso usa a borda da grade.")
        if not all(c.convergiu for c in curva):
            avisos.append("Em algum J a solução não achou o ângulo de entrada em parte da pá (freio ou moinho): essas faixas ficaram fora.")
        out = {"helice": nome, "D": pa.D, "passo_pol": h.passo_pol, "perfil": chave, "rpm": rpm, "V": V, "rho": rho,
               "curva": {"J": Js.tolist(), "CT": [c.CT for c in curva], "CP": [c.CP for c in curva], "eta": [c.eta for c in curva],
                         "CT_apc": np.asarray(ct_apc).tolist(), "CP_apc": np.asarray(cp_apc).tolist(),
                         "eta_apc": [float(j * t / q) if q > 1e-9 and t > 0 else 0.0 for j, t, q in zip(Js, ct_apc, cp_apc)]},
               "ponto": {"J": op.J, "T": op.T, "Q": op.Q, "P": op.P, "eta": op.eta, "CT": op.CT, "CP": op.CP,
                         "r_R": (op.r / pa.R).tolist(), "dT": op.dT.tolist(), "alpha": op.alpha.tolist(), "Re": op.Re.tolist(),
                         "v_a": op.v_a.tolist(), "v_t": op.v_t.tolist(), "F": op.F.tolist(),
                         "eta_ideal": BM.eficiencia_ideal(op.T, V, pa.D, rho) if V > 0 and op.T > 0 else None},
               "geometria": {"r_R": pa.r_R.tolist(), "c_R": pa.c_R.tolist(), "beta": pa.beta_graus.tolist()}, "avisos": avisos}
        esq = p.get("esquema") or {}
        if esq.get("elementos") and V > 0:
            centro = _centro_helice(esq)
            sopro = BM.sopro_de(op, centro, (1.0, 0.0, 0.0), sentido)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                v = VLM(superficies(esq))
                vl = sopro.velocidade(v.cps)
                sem = v.resolver([alpha], V=V, rho=rho, guardar_campos=True)[0]
                com = v.resolver([alpha], V=V, rho=rho, v_local=vl, guardar_campos=True)[0]
            afetadas = [nm for nm, f in v._fatias.items()
                        if np.abs(vl[f["inicio"]:f["inicio"] + f["n"]]).max() > 0.01 * V]
            out["sopro"] = {"centro": centro.tolist(),
                            "CL_sem": sem.CL, "CL_com": com.CL, "CDi_sem": sem.CDi, "CDi_com": com.CDi, "Cm_sem": sem.Cm, "Cm_com": com.Cm,
                            "superficies": [{"nome": nm, "y": sem.y_faixa[nm].tolist(), "cl_sem": sem.cl_faixa[nm].tolist(),
                                             "cl_com": com.cl_faixa[nm].tolist()} for nm in v._fatias if nm in sem.cl_faixa],
                            "afetadas": afetadas, "v_max": float(np.abs(vl).max())}
            if not afetadas:
                avisos.append("O sopro não alcança nenhuma superfície sustentadora (hélice atrás delas ou fora do alinhamento): "
                              "só a indução de montante, pequena.")
        return out
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}
