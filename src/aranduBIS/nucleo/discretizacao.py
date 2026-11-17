from __future__ import annotations

import contextvars
import math
import os
from contextlib import contextmanager

_fixados: contextvars.ContextVar[dict] = contextvars.ContextVar("disc_fixados", default={})
_usadas: contextvars.ContextVar[list | None] = contextvars.ContextVar("disc_usadas", default=None)
_avisos: contextvars.ContextVar[list | None] = contextvars.ContextVar("disc_avisos", default=None)
_vistos: contextvars.ContextVar[set | None] = contextvars.ContextVar("disc_vistos", default=None)


@contextmanager
def pedido(fixados: dict | None = None):
    t1 = _fixados.set({k: v for k, v in (fixados or {}).items() if v is not None})
    t2 = _usadas.set([])
    t3 = _avisos.set([])
    t4 = _vistos.set(set())
    try:
        yield
    finally:
        _fixados.reset(t1); _usadas.reset(t2); _avisos.reset(t3); _vistos.reset(t4)


@contextmanager
def silencio():
    t1, t2, t3 = _usadas.set(None), _avisos.set(None), _vistos.set(None)
    try:
        yield
    finally:
        _usadas.reset(t1); _avisos.reset(t2); _vistos.reset(t3)


def coletando() -> bool:
    return _avisos.get() is not None


def primeira_vez(chave) -> bool:
    v = _vistos.get()
    if v is None or chave in v:
        return False
    v.add(chave)
    return True


def fixados() -> dict:
    return dict(_fixados.get())


def no_processo(fix: dict) -> None:
    _fixados.set(dict(fix or {}))
    try:  # um processo por avaliacao: evita N processos x N threads do numba disputando os mesmos nucleos
        import numba
        numba.set_num_threads(1)
    except Exception:
        pass


def fixado(chave: str):
    return _fixados.get().get(chave)


def registra(area: str, rotulo: str, valor, origem: str, motivo: str) -> None:
    u = _usadas.get()
    if u is None:
        return
    item = {"area": area, "rotulo": rotulo, "valor": valor, "origem": origem, "motivo": motivo}
    if item not in u:
        u.append(item)


def avisa(texto: str) -> None:
    a = _avisos.get()
    if a is not None and texto not in a:
        a.append(texto)


def usadas() -> list:
    return list(_usadas.get() or [])


def avisos() -> list:
    return list(_avisos.get() or [])


def escolhe(chave: str, area: str, rotulo: str, auto_valor, motivo: str, tipo=int, minimo=None, maximo=None):
    v = fixado(chave)
    if v is not None:
        v = tipo(v)
        if minimo is not None and v < minimo or maximo is not None and v > maximo:
            avisa(f"{rotulo}: {v} fora da faixa usual ({minimo} a {maximo}); o automático seria {auto_valor}.")
        registra(area, rotulo, v, "usuario", f"fixado em Configurações (o automático seria {auto_valor}: {motivo})")
        return v
    registra(area, rotulo, auto_valor, "auto", motivo)
    return auto_valor


def vlm_n_span(nome: str, AR: float) -> int:
    from .aero.vlm import n_span_recomendado
    auto = n_span_recomendado(AR)
    motivo = (f"AR {AR:.1f}: " + ("≥ 4 → 24" if AR >= 4 else "≥ 1 → 48" if AR >= 1 else "< 1 → 96 ou mais")
              + " (o vórtice de ponta domina asa curta; poucas faixas superestimam o CLα)")
    return escolhe("vlm.n_span", "VLM", f"Painéis na envergadura ({nome})", auto, motivo, minimo=4, maximo=200)


def vlm_n_chord(arqueamento: float = 0.0, nome: str = "") -> int:
    if arqueamento < 0.01:
        auto, motivo = 4, "perfil simétrico ou quase: CLα converge com 4 (regra 1/4-3/4)"
    else:
        auto, motivo = 12, (f"perfil arqueado ({100 * arqueamento:.1f} % da corda): o CL de arqueamento converge como "
                            "0,55/n_chord (−14 % com 4, −7 % com 8); 12 dão ~5 %")
    rot = "Painéis na corda" + (f" ({nome})" if nome else "")
    return escolhe("vlm.n_chord", "VLM", rot, auto, motivo, minimo=1, maximo=40)


def estacoes_estrutura(y_max: float, nervuras_y=None) -> int:
    base = 41
    motivo = "40 intervalos: integração de cortante e fletor com erro ~ (Δy)² < 0,1 %"
    ys = sorted({abs(float(y)) for y in (nervuras_y or []) if y is not None})
    if len(ys) >= 2:
        passo = min(b - a for a, b in zip(ys, ys[1:]) if b - a > 1e-6) if any(b - a > 1e-6 for a, b in zip(ys, ys[1:])) else None
        if passo:
            n = int(math.ceil(2 * y_max / passo)) + 1
            if n > base:
                base = min(201, n)
                motivo = f"≥ 2 estações por baia de nervura (menor baia {1000 * passo:.0f} mm)"
    return escolhe("estrutura.n_estacoes", "Estrutura", "Estações na semi-envergadura", base, motivo, minimo=11, maximo=401)


def flutter_n_modos() -> int:
    return escolhe("flutter.n_modos", "Flutter", "Modos de vibração", 8,
                   "o p-k converge quando entram os modos até ~3× a frequência de flutter; 8 cobre 3 flexões, 2 torções e "
                   "o aileron", minimo=2, maximo=30)


def flutter_n_V() -> int:
    return escolhe("flutter.n_V", "Flutter", "Velocidades na varredura", 45,
                   "ΔV = 3 Vd / 45 ≈ 0,07 Vd: o cruzamento do amortecimento é interpolado entre dois pontos", minimo=10, maximo=400)


def chapeado_ns_pele(arco_m: float | None = None) -> int:
    auto, motivo = 32, "32 elementos S8R no contorno: ≥ 4 por meia-onda de flambagem do painel típico"
    if arco_m:
        alvo = 0.008
        n = int(min(100, max(20, math.ceil(arco_m / alvo))))
        auto, motivo = n, f"elemento de ~8 mm no contorno de {1000 * arco_m:.0f} mm (≥ 4 por meia-onda de flambagem)"
    return escolhe("chapeado.ns_pele", "Chapeado (CalculiX)", "Elementos no contorno da pele", auto, motivo, minimo=8, maximo=400)


def chapeado_ns_alma() -> int:
    return escolhe("chapeado.ns_alma", "Chapeado (CalculiX)", "Elementos na altura da alma", 4,
                   "alma curta e quase só em cisalhamento: 4 elementos quadráticos", minimo=1, maximo=40)


def casca_dy_max() -> float:
    return escolhe("casca.dy_max", "Asa em casca", "Maior elemento na envergadura (m)", 0.06,
                   "≈ 1/4 da corda típica de AeroDesign: a torção da caixa-D converge a 1 %", tipo=float, minimo=0.005, maximo=0.5)


def casca_n_corda() -> int:
    return escolhe("casca.n_corda", "Asa em casca", "Elementos na corda da caixa-D", 6,
                   "6 elementos no contorno da caixa-D: o fluxo de cisalhamento (Bredt) converge a 1 %", minimo=2, maximo=60)


def helice_n_est() -> int:
    return escolhe("helice.n_est", "Hélice (BEMT)", "Estações na pá", 40,
                   "40 faixas em cosseno (mais perto da ponta e do cubo): T e P mudam < 0,1 % dobrando", minimo=8, maximo=400)


INTERACOES_POR_S = float(os.environ.get("ARANDUBIS_INTERACOES_POR_S", 1.5e8))
SEQ_POR_S, CACHE_POR_S = INTERACOES_POR_S / 5, INTERACOES_POR_S * 7
ARQ_MAQUINA = None
_MAQUINA = None


def _assinatura() -> str:
    import platform
    try:
        import numba
        th = numba.config.NUMBA_NUM_THREADS
    except Exception:
        th = os.cpu_count()
    return f"{platform.processor() or platform.machine()}|{os.cpu_count()}|{th}"


def _nome_cpu() -> str:
    import platform
    try:
        if os.path.exists("/proc/cpuinfo"):
            for ln in open("/proc/cpuinfo", encoding="utf8", errors="ignore"):
                if ln.lower().startswith("model name"):
                    return ln.split(":", 1)[1].strip()
        if platform.system() == "Windows":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        if platform.system() == "Darwin":
            import subprocess
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True,
                                  timeout=2).stdout.strip()
    except Exception:
        pass
    return platform.processor() or platform.machine() or "processador desconhecido"


def mede_maquina() -> dict:
    import datetime
    import time
    import numpy as np
    from .aero.uvlm import _vel_grad_segmentos, _vel_segmentos
    from .aero.vpm import campo
    rng = np.random.default_rng(0)
    n, m = 1500, 600
    t_ = np.linspace(0, 1, n)
    X = np.c_[t_, 0.1 * np.cos(40 * t_), 0.1 * np.sin(40 * t_)] + 0.01 * rng.normal(size=(n, 3))
    A = 0.01 * rng.normal(size=(n, 3)); S = np.full(n, 0.03)
    Pa = rng.normal(size=(m, 3)) * np.array([0.3, 1.0, 0.02]); Pb = Pa + 0.05 * rng.normal(size=(m, 3)); G = rng.normal(size=m)
    P = rng.normal(size=(n, 3)) * np.array([0.5, 1.0, 0.05])
    campo(X[:50], X, A, S, "gaussiano", True); _vel_grad_segmentos(P[:50], Pa, Pb, G, 0.01)
    _vel_segmentos(P, Pa, Pb, G, 0.01)

    def melhor(f):
        b_ = math.inf
        for _ in range(3):
            t0 = time.perf_counter(); f(); b_ = min(b_, time.perf_counter() - t0)
        return b_
    t_pp = melhor(lambda: campo(X, X, A, S, "gaussiano", True))
    t_sg = melhor(lambda: _vel_grad_segmentos(P, Pa, Pb, G, 0.01))
    t_seg = melhor(lambda: _vel_segmentos(P, Pa, Pb, G, 0.01))
    return {"interacoes_por_s": n * m / t_seg, "particulas_por_s": n * n / t_pp, "segmento_grad_por_s": n * m / t_sg,
            "cpu": _nome_cpu(), "nucleos": os.cpu_count(), "assinatura": _assinatura(),
            "medido_em": datetime.date.today().isoformat()}


EFICIENCIA = 0.75


def segundos(seg: float = 0.0, pp: float = 0.0, sg: float = 0.0) -> float:
    m = maquina()
    v = m["interacoes_por_s"]
    return (seg / v + pp / m.get("particulas_por_s", v / 3) + sg / m.get("segmento_grad_por_s", v / 2)) / EFICIENCIA


def maquina(recalibrar: bool = False) -> dict:
    global _MAQUINA
    if "ARANDUBIS_INTERACOES_POR_S" in os.environ:
        return {"interacoes_por_s": INTERACOES_POR_S, "particulas_por_s": INTERACOES_POR_S / 3,
                "segmento_grad_por_s": INTERACOES_POR_S / 2, "cpu": "fixado por ARANDUBIS_INTERACOES_POR_S",
                "nucleos": os.cpu_count(), "assinatura": "", "medido_em": ""}
    if _MAQUINA is not None and not recalibrar:
        return _MAQUINA
    import json
    if not recalibrar and ARQ_MAQUINA is not None:
        try:
            d = json.loads(open(ARQ_MAQUINA, encoding="utf8").read())
            if d.get("assinatura") == _assinatura() and d.get("particulas_por_s", 0) > 0:
                _MAQUINA = d
                return d
        except (OSError, ValueError):
            pass
    try:
        d = mede_maquina()
    except Exception:
        d = {"interacoes_por_s": INTERACOES_POR_S, "cpu": _nome_cpu(), "nucleos": os.cpu_count(),
             "assinatura": _assinatura(), "medido_em": "", "falhou": True}
    _MAQUINA = d
    if ARQ_MAQUINA is not None and not d.get("falhou"):
        try:
            with open(ARQ_MAQUINA, "w", encoding="utf8") as f:
                f.write(json.dumps(d, ensure_ascii=False, indent=1))
        except OSError:
            pass
    return d


def descreve_maquina() -> str:
    m = maquina()
    return f"{m['cpu']}, {m['nucleos']} threads: {m['interacoes_por_s'] / 1e6:.0f} milhões de interações/s"


def orcamento_s() -> float:
    v = fixado("orcamento_s")
    return float(v) if v is not None else 120.0


def memoria_livre_bytes() -> float:
    try:
        return float(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError, AttributeError):
        return 4e9


def custo_uvlm(paineis: int, faixas_bf: int, passos: int, fileiras: int, livre: bool, fileiras_livres: int | None,
               k_cache: int | None = None) -> dict:
    P3, seg_corpo = 3 * paineis, 2 * paineis
    if k_cache is None:
        k_cache = max(4, int(250e6 // max(1.0, 8.0 * 7 * paineis * faixas_bf)))
    seg = mont = 0.0
    mem = 0.0
    for k in range(1, passos + 1):
        n = min(k, fileiras)
        if livre:
            nl = min(n, fileiras_livres or n)
            seg += (P3 + nl * (faixas_bf + 1)) * (seg_corpo + 2 * n * faixas_bf)
        else:
            fora = max(0, n - k_cache)
            seg += P3 * (seg_corpo + 2 * fora * faixas_bf) + min(n, k_cache) * paineis * faixas_bf
            if k <= min(fileiras, k_cache):
                mont += 4 * faixas_bf * P3
    if not livre:
        mem = 8.0 * 7 * paineis * faixas_bf * min(fileiras, k_cache, passos)
    return {"interacoes": seg + mont, "segundos": segundos(seg=seg + 5 * mont), "memoria_bytes": mem}


def custo_vpm(paineis: int, faixas_bf: int, passos: int, fileiras_aneis: int = 3, idade_fusao: int | None = 8) -> dict:
    linhas = 2 * faixas_bf + 1
    P3, sg_ = 3 * paineis, 2 * paineis + 2 * fileiras_aneis * faixas_bf
    pp = sg = seg = 0.0
    for k in range(1, passos + 1):
        idade = max(0, k - fileiras_aneis)
        if idade_fusao:
            por = idade if idade <= idade_fusao else idade_fusao * (1 + 0.5 * math.log2(idade / idade_fusao))
        else:
            por = idade
        npart = linhas * por
        pp += npart * npart + (P3 + fileiras_aneis * faixas_bf) * npart
        sg += npart * sg_
        seg += (P3 + fileiras_aneis * faixas_bf) * sg_
    return {"interacoes": pp + sg + seg, "segundos": segundos(seg=seg, pp=pp, sg=sg),
            "memoria_bytes": 8.0 * 30 * linhas * passos}


def custo_rll(paineis: int, faixas_bf: int, passos_asa: int, n_sub: int, pas: int, n_el: int, idade_rolagem: float,
              max_idade: int | None, fileiras_aneis: int = 3, idade_fusao: int | None = 8, n_helices: int = 1) -> dict:
    linhas_a = 2 * faixas_bf + 1
    linhas_h = n_helices * pas * (2 * n_el + 1)
    seg_a = 2 * paineis + 2 * fileiras_aneis * faixas_bf
    seg_h = n_helices * pas * (2 * n_el + 1) * 3
    P3 = 3 * paineis
    pp = sg = seg = 0.0
    npart = 0.0
    for k in range(1, passos_asa * n_sub + 1):
        ia = max(0.0, k / n_sub - fileiras_aneis)
        if idade_fusao and ia > idade_fusao:
            pa_ = idade_fusao * (1 + 0.5 * math.log2(ia / idade_fusao))
        else:
            pa_ = ia
        ih = min(float(k), float(max_idade)) if max_idade else float(k)
        jovem = min(ih, idade_rolagem)
        npart = linhas_a * pa_ + linhas_h * jovem + 3 * n_helices * pas * max(0.0, ih - jovem)
        pp += npart * npart
        sg += npart * (seg_a + seg_h)
        pts = 10 * n_helices * pas * n_el
        seg += pts * (seg_h + seg_a)
        pp += pts * npart
        if k % n_sub == 0:
            q = P3 + fileiras_aneis * faixas_bf
            seg += q * (seg_a + seg_h); pp += q * npart
    return {"interacoes": pp + sg + seg, "segundos": segundos(seg=seg, pp=pp, sg=sg),
            "memoria_bytes": 8.0 * 30 * npart * 4, "particulas": int(npart)}


def confere_orcamento(c: dict, o_que: str, forcar: bool = False) -> None:
    livre = memoria_livre_bytes()
    if c["memoria_bytes"] > 0.5 * livre:
        raise ValueError(f"{o_que}: precisa de ~{c['memoria_bytes'] / 1e9:.1f} GB de memória e há {livre / 1e9:.1f} GB "
                         "livres. Reduza a esteira (fileiras) ou os painéis.")
    if c["segundos"] > orcamento_s() and not forcar:
        raise ValueError(f"{o_que}: estimado em ~{c['segundos']:.0f} s nesta máquina ({descreve_maquina()}), acima do "
                         f"orçamento de {orcamento_s():.0f} s (Configurações → Discretização). Aumente o orçamento, marque "
                         "'rodar assim mesmo' ou reduza a malha.")
    if c["segundos"] > 20:
        avisa(f"{o_que}: estimado em ~{c['segundos']:.0f} s.")
