from __future__ import annotations

import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .fronteira import geometria as G
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
                if u.path == "/api/configuracao":
                    return self._json(_estado_cfg(est))
            except G.ErroDeGeometria as e:
                return self._json({"erro": str(e)}, 400)
            return self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            if not self._host_ok():
                return self._json({"erro": "host recusado"}, 403)
            try:
                d = self._corpo()
                if self.path == "/api/constroi":
                    return self._json(G.constroi(d))
                if self.path == "/api/grava":
                    return self._json({"caminho": G.grava(d, est.pasta_aeronaves)})
                if self.path == "/api/configuracao":
                    for k, v in d.items():
                        est.cfg.definir(k, v)
                    est.pasta.mkdir(parents=True, exist_ok=True)
                    est.cfg.gravar(est.arq_cfg)
                    return self._json(_estado_cfg(est))
            except (G.ErroDeGeometria, C.ConfiguracaoInvalida) as e:
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
