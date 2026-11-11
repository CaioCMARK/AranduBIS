from __future__ import annotations
_MU_AR = 1.81e-5
RHO_AR = 1.225

import re as _re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from enum import Enum

from numba import njit

class Origem(str, Enum):

    TUNEL = "tunel"
    CFD = "cfd"
    XFOIL = "xfoil"
    SINTETICA = "sintetica"
    DESCONHECIDA = "desconhecida"

class Confianca(str, Enum):

    VALIDADA = "validada"
    MARGINAL = "marginal"
    SUSPEITA = "suspeita"
    DESCARTADA = "descartada"

@njit(cache=True, fastmath=False)
def _consulta_grade(re_log_pts, alpha_pts, re_log_grid, alpha_grid, grade3):
    n = re_log_pts.shape[0]
    nr = re_log_grid.shape[0]
    na = alpha_grid.shape[0]
    out = np.empty((n, 3))
    for k in range(n):
        x = re_log_pts[k]
        y = alpha_pts[k]
        i = 0
        while i < nr - 2 and re_log_grid[i + 1] < x:
            i += 1
        j = 0
        while j < na - 2 and alpha_grid[j + 1] < y:
            j += 1
        x0, x1 = re_log_grid[i], re_log_grid[i + 1]
        y0, y1 = alpha_grid[j], alpha_grid[j + 1]
        tx = (x - x0) / (x1 - x0)
        ty = (y - y0) / (y1 - y0)
        for c in range(3):
            g00 = grade3[i, j, c]; g10 = grade3[i + 1, j, c]
            g01 = grade3[i, j + 1, c]; g11 = grade3[i + 1, j + 1, c]
            out[k, c] = (g00 * (1 - tx) * (1 - ty) + g10 * tx * (1 - ty)
                         + g01 * (1 - tx) * ty + g11 * tx * ty)
    return out

@dataclass
class Polar:

    nome: str
    alpha: np.ndarray
    re: np.ndarray
    cl: np.ndarray
    cd: np.ndarray
    cm: np.ndarray
    origem: Origem = Origem.DESCONHECIDA
    confianca: Confianca = Confianca.MARGINAL
    meta: dict = field(default_factory=dict)

    xtr_sup: np.ndarray | None = None
    xtr_inf: np.ndarray | None = None

    _interp: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.alpha = np.asarray(self.alpha, dtype=float)
        self.re = np.asarray(self.re, dtype=float)
        for k in ("cl", "cd", "cm"):
            setattr(self, k, np.asarray(getattr(self, k), dtype=float))
        n_re, n_a = len(self.re), len(self.alpha)
        for k in ("cl", "cd", "cm"):
            if getattr(self, k).shape != (n_re, n_a):
                raise ValueError(
                    f"{self.nome}: {k} tem shape {getattr(self, k).shape}, esperado {(n_re, n_a)}"
                )
        for k in ("xtr_sup", "xtr_inf"):
            v = getattr(self, k)
            if v is None:
                continue
            v = np.asarray(v, dtype=float)
            setattr(self, k, v)
            if v.shape != (n_re, n_a):
                raise ValueError(
                    f"{self.nome}: {k} tem shape {v.shape}, esperado {(n_re, n_a)}")
        if np.any(np.diff(self.alpha) <= 0):
            raise ValueError(f"{self.nome}: alpha deve ser estritamente crescente")
        if np.any(np.diff(self.re) <= 0):
            raise ValueError(f"{self.nome}: re deve ser estritamente crescente")
        self.origem = Origem(self.origem)
        self.confianca = Confianca(self.confianca)
        self._montar_interpoladores()

    def usavel(self) -> bool:
        return (self.confianca in (Confianca.VALIDADA, Confianca.MARGINAL)
                and self.origem is not Origem.DESCONHECIDA)

    def exigir_usavel(self) -> None:
        if not self.usavel():
            raise ValueError(
                f"polar '{self.nome}' não é usável em projeto: "
                f"origem={self.origem.value}, confianca={self.confianca.value}. "
                "Declare a procedência ou use outra."
            )

    def _montar_interpoladores(self) -> None:
        self._interp = {
            "re_log": np.log(self.re),
            "alpha": self.alpha,
            "grade3": np.ascontiguousarray(np.stack([self.cl, self.cd, self.cm], axis=-1)),
        }

    def __call__(self, alpha, re, avisar=True) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        alpha = np.asarray(alpha, dtype=float)
        re = np.asarray(re, dtype=float)
        alpha, re = np.broadcast_arrays(alpha, re)
        if avisar and re.size:
            self._avisar_fora_da_grade(alpha, re)
        re_log_pts = np.log(re).ravel()
        saida3 = _consulta_grade(np.ascontiguousarray(re_log_pts), np.ascontiguousarray(alpha.ravel()),
                                 self._interp["re_log"], self._interp["alpha"], self._interp["grade3"])
        saida = tuple(saida3[:, c].reshape(alpha.shape) for c in range(3))
        return saida

    def _avisar_fora_da_grade(self, alpha, re) -> None:
        import warnings

        r0, r1 = float(self.re[0]), float(self.re[-1])
        rmin, rmax = float(np.min(re)), float(np.max(re))
        if rmin < r0 * 0.99 or rmax > r1 * 1.01:
            warnings.warn(
                f"polar '{self.nome}': Reynolds pedido "
                f"[{rmin:.3g}, {rmax:.3g}] sai da grade tabelada "
                f"[{r0:.3g}, {r1:.3g}]. O valor devolvido e EXTRAPOLADO "
                "linearmente em log(Re) -- em Reynolds baixo isso subestima o "
                "cd, porque a bolha laminar nao e linear. Gere as estacoes que "
                "faltam em vez de confiar nisto.",
                RuntimeWarning, stacklevel=3)
        a0, a1 = float(self.alpha[0]), float(self.alpha[-1])
        amin, amax = float(np.min(alpha)), float(np.max(alpha))
        if amin < a0 - 0.5 or amax > a1 + 0.5:
            warnings.warn(
                f"polar '{self.nome}': alpha pedido [{amin:.3g}, {amax:.3g}] "
                f"sai da tabela [{a0:.3g}, {a1:.3g}]. Alem do estol a "
                "extrapolacao linear faz `cl` subir para sempre; use "
                "`estender_viterna` se precisa de pos-estol.",
                RuntimeWarning, stacklevel=3)

    def cl_max(self, re: float) -> tuple[float, float]:
        cl, _, _ = self(self.alpha, np.full_like(self.alpha, re), avisar=False)
        i = int(np.argmax(cl))
        return float(cl[i]), float(self.alpha[i])

    def estacoes_suspeitas(self, minimo=-0.8, maximo=0.05) -> list[dict]:
        if len(self.re) < 2:
            return []
        cd_min = np.array([
            float(np.min(self(self.alpha, np.full_like(self.alpha, r),
                              avisar=False)[1]))
            for r in self.re])
        suspeitas = []
        for k in range(len(self.re) - 1):
            if cd_min[k] <= 0 or cd_min[k + 1] <= 0:
                continue
            n = (np.log(cd_min[k + 1] / cd_min[k])
                 / np.log(self.re[k + 1] / self.re[k]))
            if not (minimo <= n <= maximo):
                suspeitas.append({
                    "de": float(self.re[k]), "para": float(self.re[k + 1]),
                    "expoente": float(n),
                    "cd_min": (float(cd_min[k]), float(cd_min[k + 1])),
                    "motivo": (f"cd_min ~ Re^{n:.2f} entre "
                               f"{self.re[k]:.3g} e {self.re[k+1]:.3g}; a "
                               "camada limite só admite entre -0,5 (laminar) "
                               "e -0,2 (turbulento)"),
                })
        return suspeitas

    def sem_estacoes_suspeitas(self, minimo=-0.8, maximo=0.05):
        import copy

        atual = self
        for _ in range(len(self.re)):
            suspeitas = atual.estacoes_suspeitas(minimo, maximo)
            if not suspeitas:
                break
            s = suspeitas[0]
            baixo = 0 if s["cd_min"][0] < s["cd_min"][1] else 1
            alvo = s["de"] if baixo == 0 else s["para"]
            manter = ~np.isclose(atual.re, alvo)
            if manter.sum() < 2:
                break
            novo = copy.copy(atual)
            novo._interp = {}
            novo.re = atual.re[manter]
            for k in ("cl", "cd", "cm"):
                setattr(novo, k, getattr(atual, k)[manter])
            for k in ("xtr_sup", "xtr_inf"):
                v = getattr(atual, k, None)
                if v is not None:
                    setattr(novo, k, v[manter])
            novo.meta = dict(atual.meta)
            novo.meta["estacoes_descartadas"] = (
                str(novo.meta.get("estacoes_descartadas", "")) + f" {alvo:.0f}")
            novo._montar_interpoladores()
            atual = novo
        return atual

    @property
    def faixa_re(self) -> tuple[float, float]:
        return float(self.re[0]), float(self.re[-1])

    def __repr__(self) -> str:
        a0, a1 = self.alpha[0], self.alpha[-1]
        r0, r1 = self.faixa_re
        nc = self.meta.get("ncrit", "?")
        marca = "" if self.usavel() else "  !NAO-USAVEL!"
        return (f"<Polar {self.nome} [{self.origem.value}/{self.confianca.value}]: "
                f"Re {r0:.3g}..{r1:.3g} ({len(self.re)} estações), "
                f"alpha {a0:.1f}..{a1:.1f} ({len(self.alpha)} pts), Ncrit={nc}{marca}>")

_CAB = _re.compile(r"Re\s*=\s*([\d.]+)\s*e\s*(\d+)", _re.I)
_NCRIT = _re.compile(r"Ncrit\s*=\s*([\d.]+)", _re.I)
_NOME = _re.compile(r"Calculated polar for:\s*(\S+)", _re.I)
_VERSAO = _re.compile(r"xflr5\s+(v[\d.]+)", _re.I)
_LINHA = _re.compile(
    r"^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)"
    r"(?:[ \t]+(-?\d+\.\d+)[ \t]+(-?\d+\.\d+))?", _re.M
)

def ler_arquivo_xflr5(caminho: str | Path) -> dict:
    caminho = Path(caminho)
    txt = caminho.read_text(encoding="latin-1")
    m = _CAB.search(txt)
    if not m:
        raise ValueError(f"{caminho.name}: não achei o Reynolds no cabeçalho")
    dados = np.array([[float(g) if g is not None else np.nan
                       for g in mm.groups()] for mm in _LINHA.finditer(txt)])
    if dados.size == 0:
        raise ValueError(f"{caminho.name}: nenhuma linha de dados reconhecida")
    ordem = np.argsort(dados[:, 0])
    dados = dados[ordem]
    nc, nm, vs = _NCRIT.search(txt), _NOME.search(txt), _VERSAO.search(txt)
    return {
        "perfil": nm.group(1) if nm else caminho.stem.replace("Polar_", ""),
        "re": float(m.group(1)) * 10 ** int(m.group(2)),
        "ncrit": float(nc.group(1)) if nc else float("nan"),
        "versao": vs.group(1) if vs else "?",
        "arquivo": caminho.name,
        "alpha": dados[:, 0], "cl": dados[:, 1], "cd": dados[:, 2], "cm": dados[:, 4],
        "xtr_sup": dados[:, 5], "xtr_inf": dados[:, 6],
    }

FRACAO_MINIMA_DE_ALPHA = 0.6

MINIMO_DE_ESTACOES = 3

def _descartar_estacoes_curtas(brutos: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(brutos) <= MINIMO_DE_ESTACOES:
        return brutos, []
    faixas = np.array([b["alpha"].max() - b["alpha"].min() for b in brutos])
    corte = FRACAO_MINIMA_DE_ALPHA * faixas.max()
    ordem = np.argsort(faixas)[::-1]
    manter = sorted(ordem[:MINIMO_DE_ESTACOES].tolist())
    for i in ordem[MINIMO_DE_ESTACOES:]:
        if faixas[i] >= corte:
            manter.append(int(i))
    manter = sorted(set(manter))
    mantidas = [brutos[i] for i in manter]
    descartadas = [brutos[i] for i in range(len(brutos)) if i not in manter]
    return mantidas, descartadas

def montar_de_arquivos(arquivos, nome: str | None = None, n_alpha: int = 121) -> Polar:
    brutos = sorted((ler_arquivo_xflr5(a) for a in arquivos), key=lambda d: d["re"])
    if not brutos:
        raise ValueError("nenhum arquivo fornecido")

    ncrits = {round(b["ncrit"], 3) for b in brutos if np.isfinite(b["ncrit"])}
    if len(ncrits) > 1:
        detalhe = ", ".join(f"{b['arquivo']}: Re={b['re']:.0f} Ncrit={b['ncrit']:g}" for b in brutos)
        raise ValueError(
            "Ncrit varia dentro da varredura de Reynolds "
            f"({sorted(ncrits)}) — os dois efeitos ficam confundidos e a tendência "
            f"de Re perde sentido. Refaça com Ncrit fixo.\n  {detalhe}"
        )
    if len({round(b["re"]) for b in brutos}) != len(brutos):
        raise ValueError("há Reynolds repetidos entre os arquivos")

    brutos, descartadas = _descartar_estacoes_curtas(brutos)

    a_min = max(b["alpha"].min() for b in brutos)
    a_max = min(b["alpha"].max() for b in brutos)
    if a_max <= a_min:
        raise ValueError("os arquivos não têm faixa de alpha em comum")
    alpha = np.linspace(a_min, a_max, n_alpha)

    re = np.array([b["re"] for b in brutos])
    cl, cd, cm = (np.array([np.interp(alpha, b["alpha"], b[k]) for b in brutos]) for k in ("cl", "cd", "cm"))
    xtr = {}
    for k in ("xtr_sup", "xtr_inf"):
        if all(k in b and np.isfinite(b[k]).all() for b in brutos):
            xtr[k] = np.array([np.interp(alpha, b["alpha"], b[k]) for b in brutos])
        else:
            xtr[k] = None
    return Polar(
        nome=nome or brutos[0]["perfil"], alpha=alpha, re=re, cl=cl, cd=cd, cm=cm,
        xtr_sup=xtr["xtr_sup"], xtr_inf=xtr["xtr_inf"],
        origem=Origem.XFOIL, confianca=Confianca.MARGINAL,
        meta={"ncrit": ncrits.pop() if ncrits else float("nan"),
              "estacoes_curtas": ", ".join(
                  f"Re={b['re']/1000:.0f}k (ate {b['alpha'].max():.1f} graus)"
                  for b in descartadas) or "nenhuma",
              "fonte": "xflr5", "versoes": sorted({b["versao"] for b in brutos}),
              "arquivos": [b["arquivo"] for b in brutos]},
    )

def estender_viterna(p: Polar, alpha_max: float = 90.0, passo: float = 2.0, AR: float = 6.0) -> Polar:
    cd_max = 1.11 + 0.018 * AR
    novo_alpha = np.arange(p.alpha[-1] + passo, alpha_max + passo / 2, passo)
    if novo_alpha.size == 0:
        return p

    cl_ext = np.empty((len(p.re), len(novo_alpha)))
    cd_ext = np.empty_like(cl_ext)
    cm_ext = np.empty_like(cl_ext)

    for i in range(len(p.re)):
        a_s = np.deg2rad(p.alpha[-1])
        cl_s, cd_s = p.cl[i, -1], p.cd[i, -1]
        sa, ca = np.sin(a_s), np.cos(a_s)
        A2 = (cl_s - cd_max * sa * ca) * sa / max(ca**2, 1e-9)
        B2 = (cd_s - cd_max * sa**2) / max(ca, 1e-9)
        a = np.deg2rad(novo_alpha)
        cl_ext[i] = cd_max / 2 * np.sin(2 * a) + A2 * np.cos(a) ** 2 / np.maximum(np.sin(a), 1e-9)
        cd_ext[i] = cd_max * np.sin(a) ** 2 + B2 * np.cos(a)
        cm_ext[i] = p.cm[i, -1]

    meta = dict(p.meta)
    meta["viterna"] = {"alpha_max": alpha_max, "AR": AR, "cd_max": cd_max}
    return Polar(
        nome=p.nome, alpha=np.concatenate([p.alpha, novo_alpha]), re=p.re,
        cl=np.hstack([p.cl, cl_ext]), cd=np.hstack([p.cd, cd_ext]),
        cm=np.hstack([p.cm, cm_ext]),
        origem=p.origem, confianca=p.confianca, meta=meta,
    )

class BancoPolares:

    def __init__(self, polares: dict[str, Polar] | None = None):
        self.polares: dict[str, Polar] = dict(polares or {})

    def __getitem__(self, nome: str) -> Polar:
        if nome not in self.polares:
            raise KeyError(f"perfil '{nome}' não está no banco. Disponíveis: {sorted(self.polares)}")
        return self.polares[nome]

    def __contains__(self, nome: str) -> bool:
        return nome in self.polares

    def __len__(self) -> int:
        return len(self.polares)

    def adicionar(self, p: Polar) -> None:
        self.polares[p.nome] = p

    def salvar(self, caminho: str | Path) -> None:
        import datetime as _dt
        import h5py

        with h5py.File(caminho, "w") as f:
            f.attrs["gerado_por"] = "arandu.aero.polares"
            f.attrs["data"] = _dt.date.today().isoformat()
            for nome, p in self.polares.items():
                g = f.create_group(nome)
                for k in ("alpha", "re", "cl", "cd", "cm"):
                    g.create_dataset(k, data=getattr(p, k), compression="gzip")
                for k in ("xtr_sup", "xtr_inf"):
                    v = getattr(p, k, None)
                    if v is not None:
                        g.create_dataset(k, data=v, compression="gzip")
                g.attrs["origem"] = p.origem.value
                g.attrs["confianca"] = p.confianca.value
                for k, v in p.meta.items():
                    g.attrs[k] = v if isinstance(v, (int, float, str)) else repr(v)

    @classmethod
    def carregar(cls, caminho: str | Path) -> BancoPolares:
        import h5py

        banco = cls()
        with h5py.File(caminho, "r") as f:
            for nome, g in f.items():
                at = dict(g.attrs)
                banco.adicionar(Polar(
                    nome=nome, alpha=g["alpha"][:], re=g["re"][:],
                    cl=g["cl"][:], cd=g["cd"][:], cm=g["cm"][:],
                    xtr_sup=g["xtr_sup"][:] if "xtr_sup" in g else None,
                    xtr_inf=g["xtr_inf"][:] if "xtr_inf" in g else None,
                    origem=Origem(at.pop("origem", "desconhecida")),
                    confianca=Confianca(at.pop("confianca", "marginal")),
                    meta=at,
                ))
        return banco

    def salvar_npz(self, caminho: str | Path) -> None:
        import json

        d, meta = {}, {}
        for nome, p in self.polares.items():
            for k in ("alpha", "re", "cl", "cd", "cm", "xtr_sup", "xtr_inf"):
                v = getattr(p, k, None)
                if v is not None:
                    d[f"{nome}/{k}"] = np.asarray(v, dtype=np.float32 if k.startswith("xtr") else float)
            meta[nome] = {"origem": p.origem.value, "confianca": p.confianca.value,
                          "meta": {k: (v if isinstance(v, (int, float, str)) else repr(v)) for k, v in p.meta.items()}}
        d["_meta"] = np.array(json.dumps(meta, ensure_ascii=False))
        np.savez_compressed(caminho, **d)

    @classmethod
    def carregar_npz(cls, caminho: str | Path) -> BancoPolares:
        import json

        banco = cls()
        with np.load(caminho, allow_pickle=False) as z:
            meta = json.loads(str(z["_meta"]))
            for nome, m in meta.items():
                g = lambda k: z[f"{nome}/{k}"] if f"{nome}/{k}" in z.files else None
                banco.adicionar(Polar(
                    nome=nome, alpha=g("alpha"), re=g("re"), cl=g("cl"), cd=g("cd"), cm=g("cm"),
                    xtr_sup=g("xtr_sup"), xtr_inf=g("xtr_inf"),
                    origem=Origem(m["origem"]), confianca=Confianca(m["confianca"]), meta=m["meta"]))
        return banco

    def __repr__(self) -> str:
        return f"<BancoPolares: {len(self.polares)} perfis {sorted(self.polares)}>"

def reynolds(V: float | np.ndarray, corda: float | np.ndarray, rho: float = RHO_AR,
             mu: float = _MU_AR) -> np.ndarray:
    return np.asarray(rho * np.asarray(V) * np.asarray(corda) / mu, dtype=float)
