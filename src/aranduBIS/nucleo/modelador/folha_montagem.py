from __future__ import annotations

import io

import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz

from . import aeronave_geometria as AG
from ..estrutura import nervuras as NV
from ..estrutura import planifica as PL

A4 = (8.27, 11.69)
COR = {"ok": "#3f8f4f", "atencao": "#c9971f", "nao": "#b94a4a"}
ROT = {"ok": "desdobra bem", "atencao": "pede cuidado", "nao": "emendar"}


def _fig(titulo, subtitulo="", pagina=None, total=None):
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=A4)
    fig.patch.set_facecolor("white")
    fig.text(0.06, 0.965, titulo, fontsize=15, fontweight="bold", va="top")
    if subtitulo:
        fig.text(0.06, 0.94, subtitulo, fontsize=9, color="#555555", va="top")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.925, 0.925], color="#999999", lw=0.8))
    if pagina:
        fig.text(0.94, 0.02, f"página {pagina}", fontsize=8, color="#777777", ha="right")
    fig.text(0.06, 0.02, "Gerado pelo AranduBIS", fontsize=8, color="#777777")
    return fig


def _tabela(fig, x, y, cabec, linhas, larguras, altura_linha=0.0165, tam=7.5, cores=None, max_linhas=None):
    x0 = x
    for c, w in zip(cabec, larguras):
        fig.text(x0, y, c, fontsize=tam, fontweight="bold", va="top")
        x0 += w
    y -= altura_linha * 1.15
    import matplotlib.pyplot as plt
    fig.add_artist(plt.Line2D([x, x + sum(larguras)], [y + altura_linha * 0.15, y + altura_linha * 0.15], color="#444444", lw=0.6))
    for k, lin in enumerate(linhas[:max_linhas] if max_linhas else linhas):
        x0 = x
        if k % 2 == 1:
            fig.add_artist(plt.Rectangle((x - 0.004, y - altura_linha * 0.85), sum(larguras) + 0.006, altura_linha, color="#f0f2f5", zorder=0, transform=fig.transFigure))
        for j, (c, w) in enumerate(zip(lin, larguras)):
            cor = (cores[k] if cores and cores[k] and j == len(lin) - 1 else "black")
            fig.text(x0, y, str(c), fontsize=tam, va="top", color=cor)
            x0 += w
        y -= altura_linha
    return y


def _paragrafo(fig, x, y, linhas, tam=8.5, passo=0.0185):
    for s in linhas:
        fig.text(x, y, s, fontsize=tam, va="top")
        y -= passo
    return y


def _resumo_asa(el):
    sec = AG._secoes(el)
    ys = np.array([q[1] for q in sec])
    cs = np.array([q[3] for q in sec])
    b = float(ys.max() - ys.min())
    if ys.min() >= 0:
        b *= 2.0
        S = 2.0 * float(_trapz(cs, ys))
    else:
        S = float(_trapz(cs, ys))
    return {"envergadura": b, "area": S, "alongamento": b * b / S if S > 0 else 0.0, "corda_raiz": float(cs[np.argmin(np.abs(ys))]), "corda_ponta": float(cs[np.argmax(np.abs(ys))])}


def _planta(ax, esq, el, nerv=None, faixas_=None, xc=None):
    sec = AG._secoes(el)
    S = sorted((abs(q[1]), q[0], q[3]) for q in sec)
    ymax = max(q[1] for q in sec)
    def le(y):
        return float(np.interp(abs(y), [s[0] for s in S], [s[1] for s in S]))
    def ch(y):
        return float(np.interp(abs(y), [s[0] for s in S], [s[2] for s in S]))
    ys = np.linspace(-ymax, ymax, 120)
    ax.fill_between(ys, [le(y) for y in ys], [le(y) + ch(y) for y in ys], color="#e8edf3", zorder=1)
    ax.plot(ys, [le(y) for y in ys], color="black", lw=1.2, zorder=3)
    ax.plot(ys, [le(y) + ch(y) for y in ys], color="black", lw=1.2, zorder=3)
    ax.plot([ys[0], ys[0]], [le(ys[0]), le(ys[0]) + ch(ys[0])], color="black", lw=1.2)
    ax.plot([ys[-1], ys[-1]], [le(ys[-1]), le(ys[-1]) + ch(ys[-1])], color="black", lw=1.2)
    cfg = el.get("estrutura") or {}
    if faixas_:
        for f in faixas_:
            for sinal in (1, -1) if f["y0_m"] >= -1e-9 else (1,):
                y0, y1 = (f["y0_m"], f["y1_m"]) if sinal == 1 else (-f["y1_m"], -f["y0_m"])
                yy = np.linspace(y0, y1, 12)
                topo = [le(y) for y in yy]
                base = [le(y) + min(xc if xc else 0.25, 1.0) * ch(y) for y in yy]
                ax.fill_between(yy, topo, base, color=COR[f["status"]], alpha=0.38, zorder=2)
    for lg in cfg.get("longarinas", []):
        from ..modelador import aeronave_estrutura as ES
        y0, y1 = lg.get("y") or [-ymax, ymax]
        yy = np.linspace(max(-ymax, min(y0, y1)), min(ymax, max(y0, y1)), 40)
        ax.plot(yy, [le(y) + ES.posicao_x(lg, ch(y), y) for y in yy], color="#7a4d1d", lw=2.0, zorder=4)
        if lg.get("y") and y0 >= 0 and any(q[1] < 0 for q in sec):
            ax.plot(-yy, [le(y) + ES.posicao_x(lg, ch(y), y) for y in yy], color="#7a4d1d", lw=2.0, zorder=4)
    if nerv:
        for n in nerv:
            y = n["y_m"]
            a = np.radians(n.get("angulo", 0.0))
            x0, x1 = le(y), le(y) + ch(y)
            ax.plot([y, y + (x1 - x0) * np.tan(a)], [x0, x1], color="#1f4e79", lw=0.9, zorder=5)
            ax.text(y, x1 + ch(y) * 0.12, f"N{n['i']:02d}", fontsize=5.5, rotation=90, ha="center", va="bottom", color="#1f4e79")
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlabel("envergadura y (m)", fontsize=7)
    ax.set_ylabel("x (m), frente no alto", fontsize=7)
    ax.tick_params(labelsize=6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _pagina_resumo(esq, A, asas, pag):
    fig = _fig(f"Folha de montagem · {esq.get('nome', 'aeronave')}", "Resumo da aeronave, lista de peças e massas previstas", pag)
    y = 0.90
    elementos = [e for e in esq.get("elementos", []) if e.get("tipo") != "ponto"]
    linhas = []
    for e in elementos:
        extra = ""
        if e.get("tipo") == "asa":
            r = _resumo_asa(e)
            extra = f"b = {r['envergadura']:.3f} m · S = {r['area']:.3f} m² · AR = {r['alongamento']:.1f}"
        linhas.append([e["nome"], e.get("tipo", ""), extra])
    y = _tabela(fig, 0.06, y, ["elemento", "tipo", "dimensões"], linhas, [0.26, 0.14, 0.48], max_linhas=24) - 0.02
    itens = sorted(A.itens_massa, key=lambda t: -t["massa"])
    total = sum(t["massa"] for t in itens)
    fig.text(0.06, y, f"Massa prevista: {1000 * total:.0f} g ({len(itens)} itens)", fontsize=9, fontweight="bold", va="top")
    y -= 0.03
    lin = [[t["nome"], f"{1000 * t['massa']:.1f}", f"{100 * t['massa'] / total:.1f}", t.get("origem", "")[:44]] for t in itens[:30]]
    y = _tabela(fig, 0.06, y, ["peça", "massa (g)", "%", "origem"], lin, [0.28, 0.11, 0.07, 0.42], tam=7)
    if len(itens) > 30:
        fig.text(0.06, y - 0.005, f"… mais {len(itens) - 30} itens menores.", fontsize=7, color="#666666", va="top")
    fig.text(0.06, 0.06, "As massas vêm do modelo (densidade × volume, valores informados e hipóteses). Pese cada peça e compare.", fontsize=7.5, color="#444444")
    return fig


def _pagina_asa(esq, el, nome, pag, avisos):
    cfg = el.get("estrutura") or {}
    fig = _fig(f"Montagem da asa · {nome}", "Posição das nervuras, longarinas e faixas de chapeado", pag)
    r = _resumo_asa(el)
    fig.text(0.06, 0.915, f"b = {r['envergadura']:.3f} m · S = {r['area']:.3f} m² · AR = {r['alongamento']:.1f} · corda {1000 * r['corda_raiz']:.0f} mm na raiz e {1000 * r['corda_ponta']:.0f} mm na ponta", fontsize=8, va="top", color="#333333")
    nerv = None
    try:
        conj = NV.pecas(esq, nome)
        nerv = conj["nervuras"]
    except (ValueError, KeyError) as e:
        avisos.append(f"{nome}: sem nervuras ({e})")
    faixas_, xc = None, None
    try:
        fx = PL.faixas(esq, nome)
        faixas_, xc = fx["faixas"], fx["ate_xc"]
    except (ValueError, KeyError):
        pass
    ax = fig.add_axes([0.08, 0.60, 0.86, 0.27])
    _planta(ax, esq, el, nerv, faixas_, xc)
    ax.set_title("Vista de cima: nervuras (azul), longarinas (marrom) e faixas de chapeado (verde, amarelo, vermelho)", fontsize=7.5, loc="left")
    y = 0.57
    if nerv:
        mat = conj["material"]
        fig.text(0.06, y, f"Nervuras · {len(nerv)} posições · {mat} de {conj['espessura_mm']:.2f} mm", fontsize=9, fontweight="bold", va="top")
        y -= 0.025
        lin = [[f"N{n['i']:02d}", f"{1000 * n['y_m']:+.0f}", f"{n['corda_mm']:.0f}", f"{n['ainc']:.1f}", f"{n['angulo']:.1f}", len(n["pecas"])] for n in nerv]
        meio = (len(lin) + 1) // 2 if len(lin) > 20 else len(lin)
        cab = ["nº", "y (mm)", "corda (mm)", "incid. (°)", "ângulo (°)", "peças"]
        w = [0.05, 0.07, 0.085, 0.07, 0.075, 0.05]
        ya = _tabela(fig, 0.06, y, cab, lin[:meio], w, tam=6.5, altura_linha=0.0145)
        if len(lin) > meio:
            _tabela(fig, 0.52, y, cab, lin[meio:], w, tam=6.5, altura_linha=0.0145)
        y = ya - 0.02
    if faixas_:
        fig.text(0.06, y, f"Chapeado · {len(faixas_)} faixas até {100 * xc:.0f} % da corda", fontsize=9, fontweight="bold", va="top")
        y -= 0.025
        lin = [[f"F{i:02d}", f"{1000 * f['y0_m']:.0f} a {1000 * f['y1_m']:.0f}", f"{f['quantidade']} × {len(f['pecas'])}", f["modo"], f"{f['deformacao_max_pct']:.2f}", ROT[f["status"]]] for i, f in enumerate(faixas_, 1)]
        cores = [COR[f["status"]] for f in faixas_]
        y = _tabela(fig, 0.06, y, ["faixa", "y (mm)", "peças", "corte", "deform. (%)", "situação"], lin, [0.06, 0.16, 0.09, 0.14, 0.12, 0.15], tam=6.5, altura_linha=0.0145, cores=cores, max_linhas=18)
        if len(faixas_) > 18:
            fig.text(0.06, y - 0.004, f"… mais {len(faixas_) - 18} faixas: veja a tabela da vista Chapeado planificado.", fontsize=7, color="#666666", va="top")
    return fig


def _pagina_sequencia(esq, asas, pag):
    fig = _fig("Sequência de montagem sugerida", "Roteiro genérico: ajuste ao seu processo", pag)
    passos = [
        "1. Corte as peças planas a partir dos DXF de nervuras e de chapeado. Confira o primeiro corte em refugo.",
        "2. Numere cada peça com o nome da tabela (N01, N02…, F01, F02…) e separe por asa.",
        "3. Prepare o gabarito: marque no plano a posição y de cada nervura e a linha das longarinas.",
        "4. Fixe as longarinas e os tubos no gabarito e encaixe as nervuras nos rasgos, na ordem da raiz para a ponta.",
        "5. Confira o alinhamento: ângulo de cada nervura, incidência e corda conferem com a tabela da página da asa.",
        "6. Cole o bordo de ataque e o bordo de fuga, se houver, antes do chapeado.",
        "7. Cole as faixas de chapeado da raiz para a ponta. Alinhe a linha tracejada de cada faixa com o bordo de ataque.",
        "8. Faixas em amarelo pedem cuidado (umedecer ou aquecer a pele); as vermelhas precisam de emenda.",
        "9. Faça o acabamento e a entelagem, se houver, seguindo a ordem do fabricante do filme.",
        "10. Pese a asa montada e compare com a massa prevista da página inicial.",
    ]
    y = _paragrafo(fig, 0.06, 0.89, passos, tam=9, passo=0.032)
    fig.text(0.06, y - 0.02, "Observações do modelo", fontsize=10, fontweight="bold", va="top")
    obs = ["As faixas seguem as estações em y, não o plano inclinado de nervuras com ângulo.", "Limites de deformação por material são hipóteses: confirme com um teste de bancada.", "Furos de alívio, nervuras cruzadas e recortes de aileron não fazem parte deste roteiro."]
    _paragrafo(fig, 0.06, y - 0.05, ["• " + s for s in obs], tam=8.5, passo=0.025)
    return fig


def folhas(esq: dict, asas=None) -> tuple[bytes, list]:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages
    A = AG.constroi(esq)
    els = [e for e in esq.get("elementos", []) if e.get("tipo") == "asa" and (asas is None or e["nome"] in asas)]
    avisos, figs = [], []
    figs.append(_pagina_resumo(esq, A, els, 1))
    for e in els:
        figs.append(_pagina_asa(esq, e, e["nome"], len(figs) + 1, avisos))
    figs.append(_pagina_sequencia(esq, els, len(figs) + 1))
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for f in figs:
            pdf.savefig(f)
            import matplotlib.pyplot as plt
            plt.close(f)
    return buf.getvalue(), list(dict.fromkeys(avisos))
