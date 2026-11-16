from __future__ import annotations

from .. import referencias as R

GPA, MPA = R.GPA, R.MPA

PADRAO = {
    "balsa": {"E": R.BALSA["E"], "G": R.BALSA["G_sobre_EL"] * R.BALSA["E"], "X": R.BALSA["X"], "XC": R.BALSA["XC"],
              "S": R.BALSA["S"], "YT": R.BALSA["YT"], "YC": R.BALSA["YC"], "nu": R.BALSA["nu_LT"], "fonte": "Wood Handbook (FPL-GTR-190), valores medios: ver REFERENCIAS.md"},
    "tubo_carbono": {"E": R.CARBONO_UD["E"], "G": R.CARBONO_UD["G"], "X": R.CARBONO_UD["X"], "XC": R.CARBONO_UD["XC"],
                     "S": R.CARBONO_UD["S"], "YT": R.CARBONO_UD["YT"], "YC": R.CARBONO_UD["YC"], "nu": R.CARBONO_UD["nu12"],
                     "fonte": "lamina UD AS4/3501-6 (Soden et al. 1998): ver REFERENCIAS.md"},
    "spruce": {"E": R.SPRUCE["E"], "G": R.SPRUCE["G_sobre_EL"] * R.SPRUCE["E"], "X": R.SPRUCE["X"], "XC": R.SPRUCE["XC"],
               "S": R.SPRUCE["S"], "YT": R.SPRUCE["YT"], "YC": R.SPRUCE["YC"], "nu": R.SPRUCE["nu_LT"], "fonte": "Sitka spruce, Wood Handbook (FPL-GTR-190): ver REFERENCIAS.md"},
}
ALIAS = {"fibra_carbono": "tubo_carbono", "carbono": "tubo_carbono", "abeto": "spruce", "pinho": "spruce"}

def propriedades(nome: str, esq: dict | None = None, mats: dict | None = None, qualidade_balsa: float = 1.0,
                 qualidade_carbono: float = 1.0) -> dict:
    nome = ALIAS.get(nome, nome)
    if nome not in PADRAO:
        raise ValueError(f"material {nome!r} sem propriedades mecanicas: declare em \"materiais_mecanicos\" "
                         f"(E, G, X, XC, S em Pa) ou use um de {sorted(PADRAO)}")
    p = dict(PADRAO[nome])
    for fonte in ((esq or {}).get("materiais_mecanicos", {}).get(nome), (mats or {}).get(nome)):
        if fonte:
            p.update({k: float(v) for k, v in fonte.items() if k in ("E", "G", "X", "XC", "S", "YT", "YC", "nu")})
    q = qualidade_carbono if nome == "tubo_carbono" else qualidade_balsa if nome == "balsa" else 1.0
    for k in ("X", "XC", "S", "YT", "YC"):
        p[k] = p[k] * q
    return p
