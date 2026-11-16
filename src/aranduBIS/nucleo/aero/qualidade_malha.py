from __future__ import annotations

import numpy as np


def _dist_ponto_segmento(P, A, B):
    AB = B - A
    L2 = np.einsum("ij,ij->i", AB, AB) + 1e-30
    AP = P[:, None, :] - A[None, :, :]
    t = np.clip(np.einsum("nmk,mk->nm", AP, AB) / L2[None, :], 0.0, 1.0)
    Q = A[None, :, :] + t[..., None] * AB[None, :, :]
    return np.linalg.norm(P[:, None, :] - Q, axis=2)


def confere(vlm) -> list[str]:
    av: list[str] = []
    f = vlm._fatias
    nomes = list(f)
    sup = {s.nome: s for s in vlm.superficies}
    for nome in nomes:
        d, s = f[nome], sup[nome]
        AR = s.planform.alongamento
        if AR < 1.0:
            av.append(f"{nome}: alongamento {AR:.2f} < 1. O VLM linear não tem a sustentação de vórtice de bordo "
                      "(Polhamus) nem o descolamento na ponta: o CL fica subestimado acima de ~10° e o estol não aparece.")
        dy = np.abs(d["d_env"])
        if len(dy) > 2:
            r = np.maximum(dy[1:] / np.maximum(dy[:-1], 1e-12), dy[:-1] / np.maximum(dy[1:], 1e-12))
            if r.max() > 5.0:
                k = int(np.argmax(r))
                av.append(f"{nome}: faixas vizinhas com largura {r.max():.1f}× diferente perto de y = {d['y'][k]:.3f} m "
                          "(quebra de seção muito curta ou estação duplicada). Salto de tamanho gera oscilação na carga; "
                          "una as estações ou aumente os painéis na envergadura.")
        i0, n, nc, ns = d["inicio"], d["n"], d["nc"], d["ns"]
        R = vlm.aneis[i0:i0 + n].reshape(nc, ns, 4, 3)
        frente = R[:, :, 1] - R[:, :, 0]
        lado = R[:, :, 3] - R[:, :, 0]
        cosang = np.abs(np.einsum("ijk,ijk->ij", frente, lado)) / (np.linalg.norm(frente, axis=2) * np.linalg.norm(lado, axis=2) + 1e-30)
        if cosang.max() > np.cos(np.radians(25.0)):
            av.append(f"{nome}: painéis muito distorcidos (ângulo entre os lados de {np.degrees(np.arccos(cosang.max())):.0f}°, "
                      "menos de 25°). Enflechamento ou afilamento extremos numa só faixa: divida a seção.")
    for a in nomes:
        da = f[a]
        P = vlm.cps[da["inicio"]:da["inicio"] + da["n"]]
        c_loc = np.repeat(da["c"][None, :], da["nc"], axis=0).ravel() / max(da["nc"], 1)
        for b in nomes:
            if a == b:
                continue
            db = f[b]
            Rb = vlm.aneis[db["inicio"]:db["inicio"] + db["n"]]
            A = np.concatenate([Rb[:, k] for k in range(4)] + [db["esteira"][:, 0], db["esteira"][:, 1]])
            B = np.concatenate([Rb[:, (k + 1) % 4] for k in range(4)] + [db["esteira"][:, 3], db["esteira"][:, 2]])
            dmin = _dist_ponto_segmento(P, A, B).min(axis=1)
            rel = dmin / np.maximum(c_loc, 1e-9)
            k = int(np.argmin(rel))
            perpend = abs(abs(np.cos(np.radians(sup[a].diedro))) - abs(np.cos(np.radians(sup[b].diedro)))) > 0.7
            if rel[k] < 0.25 and perpend:
                av.append(f"{a} nasce sobre {b} (junção em T ou em cruz): o ponto de controle mais próximo fica a "
                          f"{1000 * dmin[k]:.1f} mm de um vórtice de {b}. O efeito é local (a faixa da junção) e costuma "
                          "ser pequeno; para conferir, mude os painéis na envergadura e veja se a carga de "
                          f"{a} perto da junção muda."
                          + (" Aqui está praticamente em cima do vórtice (< 5 % do painel): a carga dessa faixa pode sair "
                             "absurda. Desloque a superfície meio painel ou faça as faixas das duas casarem na junção."
                             if rel[k] < 0.05 else ""))
            elif rel[k] < 0.25:
                av.append(f"{a}: ponto de controle a {1000 * dmin[k]:.1f} mm de um vórtice de {b} (menos de 1/4 do painel). "
                          "A velocidade induzida ali é quase singular: o resultado depende da malha. Causas comuns: a esteira "
                          f"de {b} passando rente a {a} (canard ou asa alinhados em altura), junção desalinhada (winglet) ou "
                          "superfícies sobrepostas. Desloque uma delas em z alguns milímetros ou case as malhas na junção.")
    pontas = {}
    for nome in nomes:
        d = f[nome]
        R = vlm.aneis[d["inicio"]:d["inicio"] + d["n"]].reshape(d["nc"], d["ns"], 4, 3)
        pontas[nome] = (R[:, 0, 0], R[:, -1, 1])
    for a in nomes:
        for b in nomes:
            if a >= b:
                continue
            for pa in pontas[a]:
                for pb in pontas[b]:
                    dd = np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=2).min(axis=1)
                    c_ref = max(float(np.max(f[a]["c"])), 1e-6)
                    if np.all(dd < 0.1 * c_ref) and dd.max() > 1e-4:
                        av.append(f"{a} e {b} se encostam numa junção mas os nós não coincidem (até {1000 * dd.max():.1f} mm): "
                                  "a circulação vaza pela fresta e aparece um vórtice falso na junção. Faça a ponta de uma "
                                  "começar exatamente na outra, com a mesma corda e o mesmo número de painéis na corda.")
    return av
