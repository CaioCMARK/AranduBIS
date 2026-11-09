from __future__ import annotations

GPA, MPA = 1e9, 1e6

PADRAO = {
    "balsa": {"E": 2.85 * GPA, "G": 0.148 * GPA, "X": 12.39 * MPA, "XC": 14.0 * MPA, "S": 2.1 * MPA, "nu": 0.01,
              "fonte": "valor de referencia do projeto"},
    "tubo_carbono": {"E": 112.0 * GPA, "G": 4.45 * GPA, "X": 1218.0 * MPA, "XC": 1200.0 * MPA, "S": 40.0 * MPA, "nu": 0.12,
                     "fonte": "valor de referencia do projeto"},
}
ALIAS = {"fibra_carbono": "tubo_carbono", "carbono": "tubo_carbono"}

def propriedades(nome: str, esq: dict | None = None, mats: dict | None = None, qualidade_balsa: float = 1.0,
                 qualidade_carbono: float = 1.0) -> dict:
    nome = ALIAS.get(nome, nome)
    if nome not in PADRAO:
        raise ValueError(f"material {nome!r} sem propriedades mecanicas: declare em \"materiais_mecanicos\" "
                         f"(E, G, X, XC, S em Pa) ou use um de {sorted(PADRAO)}")
    p = dict(PADRAO[nome])
    for fonte in ((esq or {}).get("materiais_mecanicos", {}).get(nome), (mats or {}).get(nome)):
        if fonte:
            p.update({k: float(v) for k, v in fonte.items() if k in ("E", "G", "X", "XC", "S", "nu")})
    q = qualidade_carbono if nome == "tubo_carbono" else qualidade_balsa
    for k in ("X", "XC", "S"):
        p[k] = p[k] * q
    return p
