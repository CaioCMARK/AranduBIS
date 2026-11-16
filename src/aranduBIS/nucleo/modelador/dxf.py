from __future__ import annotations

CAMADAS = {"CORTE": 1, "GRAVACAO": 5, "ROTULO": 3, "FOLHA": 8}

class Dxf:
    def __init__(self, camadas: dict | None = None):
        self.camadas = dict(camadas or CAMADAS)
        self.ent: list[str] = []

    @staticmethod
    def _g(codigo, valor):
        return f"{codigo}\n{valor}\n"

    @staticmethod
    def _n(v):
        return f"{float(v):.4f}"

    def polilinha(self, pontos, camada="CORTE", fechada=True):
        g = self._g
        s = g(0, "POLYLINE") + g(8, camada) + g(66, 1) + g(70, 1 if fechada else 0)
        for x, z in pontos:
            s += g(0, "VERTEX") + g(8, camada) + g(10, self._n(x)) + g(20, self._n(z)) + g(30, "0.0")
        self.ent.append(s + g(0, "SEQEND") + g(8, camada))

    def circulo(self, cx, cz, diametro, camada="CORTE"):
        g = self._g
        self.ent.append(g(0, "CIRCLE") + g(8, camada) + g(10, self._n(cx)) + g(20, self._n(cz)) + g(30, "0.0") + g(40, self._n(0.5 * diametro)))

    def texto(self, x, z, txt, altura=3.0, camada="GRAVACAO"):
        g = self._g
        limpo = "".join(c for c in str(txt) if 32 <= ord(c) < 127)
        self.ent.append(g(0, "TEXT") + g(8, camada) + g(10, self._n(x)) + g(20, self._n(z)) + g(30, "0.0") + g(40, self._n(altura)) + g(1, limpo))

    def texto_dxf(self) -> str:
        g = self._g
        s = g(0, "SECTION") + g(2, "HEADER") + g(9, "$ACADVER") + g(1, "AC1009") + g(9, "$INSUNITS") + g(70, 4) + g(0, "ENDSEC")
        s += g(0, "SECTION") + g(2, "TABLES")
        s += g(0, "TABLE") + g(2, "LTYPE") + g(70, 1) + g(0, "LTYPE") + g(2, "CONTINUOUS") + g(70, 0) + g(3, "Solid line") + g(72, 65) + g(73, 0) + g(40, "0.0") + g(0, "ENDTAB")
        s += g(0, "TABLE") + g(2, "LAYER") + g(70, len(self.camadas))
        for nome, cor in self.camadas.items():
            s += g(0, "LAYER") + g(2, nome) + g(70, 0) + g(62, cor) + g(6, "CONTINUOUS")
        s += g(0, "ENDTAB") + g(0, "ENDSEC")
        s += g(0, "SECTION") + g(2, "ENTITIES") + "".join(self.ent) + g(0, "ENDSEC") + g(0, "EOF")
        return s

def le(texto: str) -> list[tuple[str, dict]]:
    L = texto.split("\n")
    pares = [(L[i].strip(), L[i + 1]) for i in range(0, len(L) - 1, 2)]
    out, i, dentro = [], 0, False
    while i < len(pares):
        c, v = pares[i]
        if c == "2" and v == "ENTITIES":
            dentro = True
        elif dentro and c == "0" and v == "ENDSEC":
            break
        elif dentro and c == "0" and v in ("POLYLINE", "CIRCLE", "TEXT"):
            e = {"camada": "", "pontos": [], "raio": None, "texto": None}
            tipo, i = v, i + 1
            while i < len(pares) and not (pares[i][0] == "0" and pares[i][1] in ("POLYLINE", "CIRCLE", "TEXT", "ENDSEC")):
                c2, v2 = pares[i]
                if c2 == "8" and not e["camada"]:
                    e["camada"] = v2
                if c2 == "0" and v2 == "VERTEX":
                    p = {}
                    i += 1
                    while pares[i][0] not in ("0",):
                        p[pares[i][0]] = pares[i][1]
                        i += 1
                    e["pontos"].append((float(p["10"]), float(p["20"])))
                    continue
                if tipo != "POLYLINE" and c2 == "10":
                    e["pontos"].append([float(v2), 0.0])
                if tipo != "POLYLINE" and c2 == "20":
                    e["pontos"][-1][1] = float(v2)
                if c2 == "40":
                    e["raio"] = float(v2)
                if c2 == "1" and tipo == "TEXT":
                    e["texto"] = v2
                i += 1
            out.append((tipo, e))
            continue
        i += 1
    return out
