from __future__ import annotations

import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

mimetypes.add_type("font/woff2", ".woff2")
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .fronteira import analise as AN
from .fronteira import arquivos as AQ
from .fronteira import geometria as G
from .fronteira import otimiza as OT
from .fronteira import regras as RG
from .nucleo import configuracao as C

WEB = Path(__file__).resolve().parent / "web"
LIMITE_CORPO = 8 * 1024 * 1024
PORTA = 8741

class Estado:
    def __init__(self, pasta_dados: Path):
        self.pasta = Path(pasta_dados)
        self.arq_cfg = self.pasta / "configuracao.json"
        self.pasta_aeronaves = self.pasta / "aeronaves"
        self.cfg = C.Configuracao.ler(self.arq_cfg)

def _estado_cfg(est: Estado) -> dict:
    return {
        "problemas": est.cfg.problemas(),
        "opcoes": [
            {"chave": o.chave, "grupo": o.grupo, "rotulo": o.rotulo, "ajuda": o.ajuda,
             "tipo": o.tipo, "escolhas": list(o.escolhas), "minimo": o.minimo,
             "maximo": o.maximo, "padrao": o.padrao, "valor": est.cfg.valor(o.chave),
             "ativa": est.cfg.ativa(o.chave)}
            for o in C.OPCOES],
    }

def fazer_handler(est: Estado):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _host_ok(self) -> bool:
            h = (self.headers.get("Host") or "").split(":")[0]
            return h in ("127.0.0.1", "localhost")

        def _json(self, obj, status=200):
            b = json.dumps(obj, ensure_ascii=False).encode("utf8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _arquivo(self, p: Path):
            b = p.read_bytes()
            self.send_response(200)
            tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text") or p.suffix == ".js" else ""))
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _corpo(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > LIMITE_CORPO:
                raise ValueError("corpo grande demais")
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if not self._host_ok():
                return self._json({"erro": "host recusado"}, 403)
            u = urlparse(self.path)
            try:
                if u.path == "/":
                    return self._arquivo(WEB / "index.html")
                if u.path.startswith("/web/"):
                    p = (WEB / u.path[5:]).resolve()
                    if WEB.resolve() in p.parents and p.is_file():
                        return self._arquivo(p)
                    return self._json({"erro": "não encontrado"}, 404)
                if u.path == "/api/exemplos":
                    return self._json({"exemplos": G.exemplos()})
                if u.path == "/api/exemplo":
                    nome = parse_qs(u.query).get("nome", [""])[0]
                    return self._json(G.abre_exemplo(nome))
                if u.path == "/api/arquivos":
                    q = parse_qs(u.query)
                    return self._json(AQ.lista(est.cfg, q.get("pasta", [""])[0], q.get("sub", [""])[0]))
                if u.path == "/api/arquivo":
                    q = parse_qs(u.query)
                    return self._arquivo(AQ.caminho_do_arquivo(est.cfg, q.get("pasta", [""])[0], q.get("caminho", [""])[0]))
                if u.path == "/api/regras":
                    return self._json({"regras": RG.lista(est.pasta)})
                if u.path == "/api/regra":
                    q = parse_qs(u.query)
                    return self._json(RG.abre(est.pasta, q.get("nome", [""])[0], q.get("origem", [""])[0]))
                if u.path == "/api/materiais":
                    return self._json({"materiais": G.materiais()})
                if u.path == "/api/configuracao":
                    return self._json(_estado_cfg(est))
                if u.path == "/api/otimiza/estado":
                    q = parse_qs(u.query)
                    return self._json(OT.estado(q.get("id", [""])[0]))
            except (G.ErroDeGeometria, AQ.ErroDeArquivo, RG.ErroDeRegra, OT.ErroDeOtimiza, OSError) as e:
                return self._json({"erro": str(e)}, 400)
            return self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            if not self._host_ok():
                return self._json({"erro": "host recusado"}, 403)
            try:
                d = self._corpo()
                if self.path == "/api/constroi":
                    return self._json(G.constroi(d))
                if self.path == "/api/medidas":
                    return self._json(G.medidas(d))
                if self.path == "/api/aero/resumo":
                    return self._json(AN.resumo_aero(d))
                if self.path == "/api/regra/avalia":
                    return self._json(RG.avalia(d.get("regra"), d.get("valores")))
                if self.path == "/api/regra/grava":
                    return self._json({"caminho": RG.grava(est.pasta, d.get("regra") or {}, d.get("nome", ""))})
                if self.path == "/api/equilibrio":
                    return self._json(AN.equilibrio(d))
                if self.path == "/api/limites":
                    return self._json(AN.limites(d))
                if self.path == "/api/dinamica":
                    return self._json(AN.dinamica(d))
                if self.path == "/api/dinamica/comandos":
                    return self._json(AN.comandos(d))
                if self.path == "/api/dinamica/resposta_comando":
                    return self._json(AN.resposta_comando(d))
                if self.path == "/api/envelope_cg":
                    return self._json(AN.envelope_cg(d))
                if self.path == "/api/asa":
                    return self._json(AN.asa(d))
                if self.path == "/api/massa_estrutural":
                    return self._json(AN.massa_estrutural(d))
                if self.path == "/api/trem":
                    return self._json(AN.trem(d))
                if self.path == "/api/flambagem":
                    return self._json(AN.flambagem(d))
                if self.path == "/api/cauda":
                    return self._json(AN.cauda(d))
                if self.path == "/api/torcao":
                    return self._json(AN.torcao(d))
                if self.path == "/api/torcao_fe":
                    return self._json(AN.torcao_fe(d))
                if self.path == "/api/cargas":
                    return self._json(AN.cargas(d))
                if self.path == "/api/controle":
                    return self._json(AN.controle(d))
                if self.path == "/api/propulsao":
                    return self._json(AN.propulsao(d))
                if self.path == "/api/decolagem":
                    return self._json(AN.decolagem(d))
                if self.path == "/api/grava":
                    return self._json({"caminho": G.grava(d, est.pasta_aeronaves)})
                if self.path == "/api/configuracao":
                    for k, v in d.items():
                        est.cfg.definir(k, v)
                    est.pasta.mkdir(parents=True, exist_ok=True)
                    est.cfg.gravar(est.arq_cfg)
                    return self._json(_estado_cfg(est))
                if self.path == "/api/otimiza/inicia":
                    return self._json({"id": OT.inicia(d.get("problema") or {}, d.get("execucao") or {})})
                if self.path == "/api/otimiza/inicia_arvore":
                    return self._json({"id": OT.inicia_arvore(d.get("topologias") or {}, d.get("execucao") or {}, d.get("semear"))})
                if self.path == "/api/otimiza/para":
                    OT.para(d.get("id", ""))
                    return self._json({"ok": True})
                if self.path == "/api/otimiza/materializa":
                    return self._json(OT.materializa(d.get("problema") or {}, d.get("x") or {}))
            except (G.ErroDeGeometria, C.ConfiguracaoInvalida, AN.ErroDeAnalise, RG.ErroDeRegra, OT.ErroDeOtimiza) as e:
                return self._json({"erro": str(e)}, 400)
            except (ValueError, KeyError, TypeError) as e:
                return self._json({"erro": f"pedido inválido: {e}"}, 400)
            return self._json({"erro": "não encontrado"}, 404)

    return H

def servir(pasta_dados=None, porta: int = PORTA, abrir: bool = True) -> int:
    pasta = Path(pasta_dados) if pasta_dados else Path.cwd() / "dados"
    srv = ThreadingHTTPServer(("127.0.0.1", porta), fazer_handler(Estado(pasta)))
    url = f"http://127.0.0.1:{porta}/"
    print(f"[aranduBIS] {url}  (Ctrl+C encerra)")
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(servir())
