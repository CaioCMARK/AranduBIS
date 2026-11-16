from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

CODECS = {"h264": ["libx264", "libopenh264", "h264_mf"], "h265": ["libx265", "hevc_mf"]}
CORES = {"asa": (0.29, 0.53, 0.77), "canard": (0.85, 0.55, 0.24), "fuselagem": (0.75, 0.45, 0.45)}
PALETA = [(0.29, 0.53, 0.77), (0.85, 0.55, 0.24), (0.42, 0.66, 0.31), (0.64, 0.47, 0.78), (0.35, 0.67, 0.67), (0.75, 0.45, 0.45)]
NATUREZA = {"flexao": "flexão", "torcao": "torção"}


class ErroDeAnimacao(ValueError):
    pass


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    c = shutil.which("ffmpeg")
    if not c:
        raise ErroDeAnimacao("ffmpeg nao encontrado: instale o pacote imageio-ffmpeg (pip install imageio-ffmpeg) para gerar MP4")
    return c


def codificador(codec: str) -> str:
    if codec not in CODECS:
        raise ErroDeAnimacao(f"codec {codec!r}: use {', '.join(CODECS)}")
    r = subprocess.run([ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30)
    for enc in CODECS[codec]:
        if f" {enc} " in r.stdout:
            return enc
    raise ErroDeAnimacao(f"este ffmpeg nao tem codificador {codec.upper()} ({', '.join(CODECS[codec])})")


def _modos(esq: dict, Vd: float, n_modos: int) -> dict:
    from .estrutura import flutter as FL
    from .modelador import aeronave_geometria as AG
    asas = {}
    for e in esq.get("elementos", []):
        if e.get("tipo") != "asa" or not (e.get("estrutura") or {}).get("longarinas"):
            continue
        d = FL.dados_de_vibracao(esq, e["nome"], Vd=Vd)
        xa = np.broadcast_to(np.asarray(d["x_alfa_c"], float), d["y"].shape) * d["c"]
        rg = np.broadcast_to(np.asarray(d["r_giro_c"], float), d["y"].shape) * d["c"]
        m = FL.modos_de_vibracao(d["y"], d["EI"], d["GJ"], d["m_lin"], d["m_lin"] * xa, d["m_lin"] * (rg ** 2 + xa ** 2), n_modos)
        sec = AG._secoes(e)
        asas[e["nome"]] = dict(y=d["y"], ea=d["ea_c"], h=np.array(m["h"]), a=np.array(m["alfa"]), f=m["f_hz"], nat=m["natureza"],
                               pos=np.asarray(e.get("posicao", [0, 0, 0]), float), ys=np.array([q[1] for q in sec]),
                               xl=np.array([q[0] for q in sec]), cs=np.array([q[3] for q in sec]))
    if not asas:
        raise ErroDeAnimacao("nenhuma asa com longarina declarada: sem modos de vibracao para animar")
    return asas


def modos(esq: dict, Vd: float, formato: str = "mp4", codec: str = "h264", largura: int = 1280, fps: int = 24,
          n_modos: int = 3, segundos_por_modo: float = 2.0, asa: str | None = None) -> tuple[bytes, str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    from .modelador import aeronave_geometria as AG

    if formato not in ("mp4", "gif"):
        raise ErroDeAnimacao("formato: mp4 ou gif")
    largura = int(min(max(int(largura), 480), 3840)) // 2 * 2
    altura = int(round(largura * 0.66)) // 2 * 2
    fps = int(min(max(int(fps), 10), 60))
    enc = codificador(codec) if formato == "mp4" else None

    asas = _modos(esq, Vd, max(4, n_modos))
    principal = asa if asa in asas else max(asas, key=lambda n: asas[n]["y"][-1])
    A = AG.constroi(esq)
    V0, T, zona = A.V.copy(), np.asarray(A.T), np.asarray(A.zona)
    nome_z = np.array([z.split(".")[0] for z in A.zonas]); cam = np.array(A.camadas)
    tipos = {e["nome"]: e.get("tipo") for e in esq.get("elementos", [])}
    mostra = np.array([cam[k] == "aero" or tipos.get(nome_z[k]) == "corpo" for k in zona])
    T = T[mostra]; dono = nome_z[zona[mostra]]
    vert = {n: np.unique(T[dono == n].ravel()) for n in set(dono)}
    presos = {}
    for n, idx in vert.items():
        if n in asas or tipos.get(n) != "asa":
            continue
        P = V0[idx]
        for m_, w in asas.items():
            ym = float(np.mean(P[:, 1])) - w["pos"][1]
            zm = float(np.mean(P[:, 2]))
            if abs(ym) <= w["y"][-1] and abs(zm - w["pos"][2]) < 0.25 * w["y"][-1] and abs(float(np.mean(P[:, 0])) - (w["pos"][0] + np.interp(ym, w["ys"], w["xl"]))) < 2 * np.max(w["cs"]):
                presos[n] = m_; break

    def campo(n, yloc, r):
        w = asas[n]; ya = np.abs(yloc)
        h = np.interp(ya, w["y"], w["h"][r]); a = np.interp(ya, w["y"], w["a"][r])
        xea = w["pos"][0] + np.interp(yloc, w["ys"], w["xl"]) + np.interp(ya, w["y"], w["ea"]) * np.interp(yloc, w["ys"], w["cs"])
        return h, a, xea

    esc = {}
    for n, w in asas.items():
        yt = w["y"][-1]; c_t = float(np.interp(yt, np.abs(w["ys"]), w["cs"]))
        esc[n] = [0.09 * yt / max(abs(campo(n, np.array([yt]), r)[0][0]) + abs(campo(n, np.array([yt]), r)[1][0]) * 0.5 * c_t, 1e-12)
                  for r in range(len(w["f"]))]

    def deforma(coef):
        V = V0.copy()
        for n, w in asas.items():
            for alvo in [n] + [p for p, q in presos.items() if q == n]:
                idx = vert.get(alvo)
                if idx is None:
                    continue
                P = V0[idx]
                yloc = P[:, 1] - w["pos"][1] if alvo == n else np.full(len(idx), np.mean(P[:, 1]) - w["pos"][1])
                tot = np.zeros(len(idx))
                for r, cf in enumerate(coef.get(n, [])):
                    if cf:
                        h, a, xea = campo(n, yloc, r)
                        tot += cf * esc[n][r] * (h - a * (P[:, 0] - xea))
                V[idx, 2] += tot
        return V

    cores_el = {}
    for i, n in enumerate(sorted(set(dono))):
        cores_el[n] = CORES.get(n, PALETA[i % len(PALETA)])
    base = np.array([cores_el[n] for n in dono])
    luz = np.array([-0.3, -0.5, 0.8]); luz /= np.linalg.norm(luz)
    w0 = asas[principal]
    nm = min(n_modos, len(w0["f"]))
    cenas = [(f"modo {r + 1} de {principal}: {NATUREZA.get(w0['nat'][r], w0['nat'][r])}, {w0['f'][r]:.1f} Hz",
              {principal: [1.0 if k == r else 0.0 for k in range(len(w0['f']))]}, True) for r in range(nm)]
    cenas.append(("todos juntos, cada um na sua frequência", {n: [1.0, 0.7, 0.6][:nm] + [0.0] * (len(asas[n]["f"]) - nm) for n in asas}, False))
    qpc = max(12, int(round(fps * segundos_por_modo)))
    quadros = [(i, k) for i in range(len(cenas)) for k in range(qpc)]

    dpi = 100
    fig = plt.figure(figsize=(largura / dpi, altura / dpi), dpi=dpi)
    ax = fig.add_axes([-0.12, -0.15, 1.24, 1.15], projection="3d")
    lo, hi = V0[np.unique(T)].min(0), V0[np.unique(T)].max(0); ctr = 0.5 * (lo + hi); R = 0.36 * (hi - lo).max()
    ax.set_xlim(ctr[0] - R, ctr[0] + R); ax.set_ylim(ctr[1] - R, ctr[1] + R); ax.set_zlim(ctr[2] - 0.6 * R, ctr[2] + 0.6 * R)
    ax.set_box_aspect((1, 1, 0.6)); ax.view_init(elev=24, azim=-122); ax.set_axis_off()
    fs = max(8, largura / 75)
    tit = fig.text(0.5, 0.95, "", ha="center", fontsize=fs)
    sub = fig.text(0.5, 0.915, "", ha="center", fontsize=0.7 * fs, color="0.35")
    pc = [None]

    def quadro(q):
        i, k = quadros[q]; titulo, cf, so = cenas[i]
        t = 2 * np.pi * k / qpc
        if so:
            coef = {n: [c * np.sin(t) for c in v] for n, v in cf.items()}
        else:
            f1 = asas[principal]["f"][0]
            coef = {n: [c * np.sin(max(1, round(asas[n]["f"][j] / f1)) * t) for j, c in enumerate(v)] for n, v in cf.items()}
        P = deforma(coef)[T]
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        s = 0.45 + 0.55 * np.abs(nrm @ luz)
        if pc[0] is not None:
            pc[0].remove()
        pc[0] = Poly3DCollection(P, facecolors=np.clip(base * s[:, None], 0, 1), edgecolors="none", linewidths=0)
        ax.add_collection3d(pc[0])
        tit.set_text(titulo)
        sub.set_text(f"{esq.get('nome', '')} · deslocamentos exagerados · " + ("a forma é o que importa, a amplitude é arbitrária" if so else "frequências relativas arredondadas"))
        return pc[0],

    an = FuncAnimation(fig, quadro, frames=len(quadros), blit=False)
    with tempfile.TemporaryDirectory(prefix="arandubis_anima_") as tmp:
        saida = Path(tmp) / f"modos.{formato}"
        if formato == "gif":
            an.save(saida, writer=PillowWriter(fps=min(fps, 20)), dpi=dpi)
            tipo = "image/gif"
        else:
            matplotlib.rcParams["animation.ffmpeg_path"] = ffmpeg()
            extra = ["-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
            if enc in ("libx265", "hevc_mf"):
                extra += ["-tag:v", "hvc1"]
            if enc not in ("libx264", "libx265"):
                extra = ["-pix_fmt", "yuv420p", "-b:v", "6M", "-movflags", "+faststart"]
            an.save(saida, writer=FFMpegWriter(fps=fps, codec=enc, extra_args=extra), dpi=dpi)
            tipo = "video/mp4"
        plt.close(fig)
        return saida.read_bytes(), tipo


def esteira(instantaneos: list, aneis_corpo: np.ndarray, titulo: str = "", largura: int = 1280, fps: int = 15,
            codec: str = "h264", vista=(22, -128)) -> tuple[bytes, str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

    if not instantaneos:
        raise ErroDeAnimacao("nada para animar: rode a analise com instantaneos")
    enc = codificador(codec)
    altura = int(round(largura * 9 / 16 / 2)) * 2
    dpi = 100
    fig = plt.figure(figsize=(largura / dpi, altura / dpi), dpi=dpi)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([-0.12, -0.25, 1.24, 1.38], projection="3d")
    todos = [aneis_corpo.reshape(-1, 3)]
    ult = instantaneos[-1]
    if "X" in ult:
        todos.append(ult["X"])
    for a in ult["aneis"]:
        todos.append(a.reshape(-1, 3))
    for q_ in (instantaneos[0], ult):
        if q_.get("solo"):
            p0 = np.asarray(q_["solo"]["p0"], float)
            todos.append(np.array([p0, p0 + [0.0, 0.0, 0.0]]))
    P = np.vstack(todos)
    lo, hi = np.percentile(P, 0.5, axis=0), np.percentile(P, 99.5, axis=0)
    lo = np.minimum(lo, aneis_corpo.reshape(-1, 3).min(0)); hi = np.maximum(hi, aneis_corpo.reshape(-1, 3).max(0))
    ext = np.maximum(hi - lo, 1e-6)
    ext[2] = max(ext[2], 0.15 * ext[:2].max())
    lo, hi = lo - 0.03 * ext, hi + 0.03 * ext
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], lo[2] + 1.06 * ext[2])
    ax.set_box_aspect(tuple(1.06 * ext / ext.max())); ax.set_proj_type("persp", focal_length=0.6)
    ax.view_init(elev=vista[0], azim=vista[1]); ax.set_axis_off()
    ax.add_collection3d(Poly3DCollection(aneis_corpo, facecolors=(0.55, 0.62, 0.72, 0.9), edgecolors=(0.3, 0.35, 0.45, 0.4), linewidths=0.2))
    wmax = max((np.percentile(q["w"], 99) for q in instantaneos if "w" in q and len(q["w"])), default=1.0)
    fs = max(8, largura / 80)
    tit = fig.text(0.5, 0.95, titulo, ha="center", fontsize=fs * min(1.0, 95.0 / max(1, len(titulo))))
    sub = fig.text(0.5, 0.91, "", ha="center", fontsize=0.75 * fs, color="0.35")
    vivos = []

    def quadro(i):
        for o in vivos:
            o.remove()
        vivos.clear()
        q = instantaneos[i]
        seg = []
        for a in q["aneis"]:
            for k in range(a.shape[0]):
                seg += list(zip(a[k, :-1], a[k, 1:]))
            for j in range(a.shape[1]):
                seg += list(zip(a[:-1, j], a[1:, j]))
        if seg:
            lc = Line3DCollection(seg, colors=[(0.2, 0.3, 0.5, 0.5)], linewidths=0.4)
            ax.add_collection3d(lc); vivos.append(lc)
        if q.get("solo"):
            n_ = np.asarray(q["solo"]["n"], float); p0 = np.asarray(q["solo"]["p0"], float)
            e1 = np.array([n_[2], 0.0, -n_[0]]); e2 = np.array([0.0, 1.0, 0.0])
            xs, ys = ax.get_xlim(), ax.get_ylim()
            a0 = (np.array([xs[0], 0, 0]) - p0) @ e1; a1 = (np.array([xs[1], 0, 0]) - p0) @ e1
            quad = [p0 + a * e1 + b * e2 for a, b in ((a0, ys[0]), (a1, ys[0]), (a1, ys[1]), (a0, ys[1]))]
            ch = Poly3DCollection([quad], facecolors=(0.45, 0.6, 0.35, 0.18), edgecolors=(0.35, 0.5, 0.25, 0.4), linewidths=0.6)
            ax.add_collection3d(ch); vivos.append(ch)
        if q.get("pas"):
            sp = [list(zip(a[:-1], a[1:])) for a in q["pas"]]
            lp = Line3DCollection([x for s_ in sp for x in s_], colors=[(0.93, 0.55, 0.2, 1.0)], linewidths=2.2)
            ax.add_collection3d(lp); vivos.append(lp)
        if "X" in q and len(q["X"]):
            c = np.log10(np.clip(q["w"] / wmax, 1e-3, 1.0))
            sc = ax.scatter(q["X"][:, 0], q["X"][:, 1], q["X"][:, 2], c=c, cmap="plasma_r", vmin=-3, vmax=0, s=4.0, depthshade=False, linewidths=0)
            vivos.append(sc)
        n = len(q["X"]) if "X" in q else 0
        sub.set_text(f"t = {q['t']:.3f} s · CL = {q['CL']:.3f}" + (f" · {n} partículas (roxo = |α| forte, amarelo = fraco)" if n else ""))
        return vivos

    an = FuncAnimation(fig, quadro, frames=len(instantaneos), blit=False)
    with tempfile.TemporaryDirectory(prefix="arandubis_esteira_") as tmp:
        saida = Path(tmp) / "esteira.mp4"
        matplotlib.rcParams["animation.ffmpeg_path"] = ffmpeg()
        extra = ["-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if enc in ("libx265", "hevc_mf"):
            extra += ["-tag:v", "hvc1"]
        if enc not in ("libx264", "libx265"):
            extra = ["-pix_fmt", "yuv420p", "-b:v", "6M", "-movflags", "+faststart"]
        an.save(saida, writer=FFMpegWriter(fps=fps, codec=enc, extra_args=extra), dpi=dpi)
        plt.close(fig)
        return saida.read_bytes(), "video/mp4"
