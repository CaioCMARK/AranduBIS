from __future__ import annotations

import json
import mimetypes
import sys
import threading
import traceback
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
from .nucleo import discretizacao as DS

WEB = Path(__file__).resolve().parent / "web"
LIMITE_CORPO = 8 * 1024 * 1024
PORTA = 8741

class Estado:
    def __init__(self, pasta_dados: Path):
        self.pasta = Path(pasta_dados)
        self.arq_cfg = self.pasta / "configuracao.json"
        self.pasta_aeronaves = self.pasta / "aeronaves"
        self.cfg = C.Configuracao.ler(self.arq_cfg)
        DS.ARQ_MAQUINA = str(self.pasta / "maquina.json")

def _estado_cfg(est: Estado) -> dict:
    return {
        "problemas": est.cfg.problemas(),
        "opcoes": [
            {"chave": o.chave, "grupo": o.grupo, "rotulo": o.rotulo, "ajuda": o.ajuda,
             "tipo": o.tipo, "escolhas": list(o.escolhas), "minimo": o.minimo,
             "maximo": o.maximo, "padrao": o.padrao, "valor": est.cfg.valor(o.chave),
             "ativa": est.cfg.ativa(o.chave),
             "derivado": o.derivado, "fonte": o.fonte, "auto": o.auto, "referencia": o.referencia, "sem_efeito": o.sem_efeito, "manual": est.cfg.manual(o.chave)}
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

        def _origem_ok(self) -> bool:
            o = self.headers.get("Origin")
            if o is None:
                return True
            return (urlparse(o).hostname or "") in ("127.0.0.1", "localhost")

        def _recusa(self, motivo: str):
            self.close_connection = True
            return self._json({"erro": motivo}, 403)

        def _falha_interna(self, e: Exception):
            traceback.print_exc()
            self.close_connection = True
            return self._json({"erro": f"erro interno ({type(e).__name__}): {e}"}, 500)

        def _json(self, obj, status=200):
            if isinstance(obj, dict) and self.command == "POST":
                usadas, av = DS.usadas(), DS.avisos()
                if usadas and "discretizacao_usada" not in obj:
                    obj = {**obj, "discretizacao_usada": usadas}
                if av:
                    obj = {**obj, "avisos_discretizacao": av}
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

        def _binario(self, b: bytes, tipo: str, nome: str):
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _corpo(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0 or n > LIMITE_CORPO:
                self.close_connection = True
                raise ValueError("corpo grande demais")
            d = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(d, dict):
                raise ValueError("o corpo precisa ser um objeto JSON")
            return d

        def do_GET(self):
            if not self._host_ok():
                return self._recusa("host recusado")
            u = urlparse(self.path)
            try:
                if u.path == "/":
                    return self._arquivo(WEB / "index.html")
                if u.path == "/favicon.ico":
                    self.send_response(204); self.end_headers(); return
                if u.path.startswith("/web/"):
                    p = (WEB / u.path[5:]).resolve()
                    if WEB.resolve() in p.parents and p.is_file():
                        return self._arquivo(p)
                    return self._json({"erro": "não encontrado"}, 404)
                if u.path == "/api/exemplos":
                    return self._json({"exemplos": G.exemplos()})
                if u.path == "/api/maquina":
                    return self._json(DS.maquina(recalibrar=parse_qs(u.query).get("recalibrar", ["0"])[0] == "1"))
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
            except Exception as e:
                return self._falha_interna(e)
            return self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            fix = {o.chave[len("discretizacao."):]: est.cfg.valor(o.chave) for o in C.OPCOES if o.chave.startswith("discretizacao.")}
            with DS.pedido(fix):
                return self._post()

        def _post(self):
            if not self._host_ok():
                return self._recusa("host recusado")
            if not self._origem_ok():
                return self._recusa("origem recusada")
            try:
                d = self._corpo()
                if self.path == "/api/constroi":
                    return self._json(G.constroi(d))
                if self.path == "/api/medidas":
                    return self._json(G.medidas(d))
                if self.path == "/api/exporta/fabricacao":
                    return self._json(G.exporta_fabricacao(d, est.pasta))
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
                if self.path == "/api/pouso_dinamico":
                    return self._json(AN.pouso_dinamico(d))
                if self.path == "/api/flambagem":
                    return self._json(AN.flambagem(d))
                if self.path == "/api/uvlm/video":
                    from .nucleo import anima as ANI
                    try:
                        dados, tipo = AN.uvlm_video(d)
                    except (ANI.ErroDeAnimacao, ValueError, FileNotFoundError, KeyError) as e:
                        return self._json({"erro": str(e)}, 400)
                    return self._binario(dados, tipo, "esteira.mp4")
                if self.path == "/api/anima/modos":
                    from .nucleo import anima as ANI
                    try:
                        dados, tipo = ANI.modos(d.get("esquema") or {}, float(d.get("Vd") or 18.75), d.get("formato", "mp4"), d.get("codec", "h264"),
                                                int(d.get("largura", 1280)), int(d.get("fps", 24)), int(d.get("n_modos", 3)), asa=d.get("asa"))
                    except (ANI.ErroDeAnimacao, ValueError, FileNotFoundError, KeyError) as e:
                        return self._json({"erro": str(e)}, 400)
                    return self._binario(dados, tipo, "modos." + ("gif" if tipo == "image/gif" else "mp4"))
                if self.path in ("/api/peso", "/api/peso/servos"):
                    from .nucleo import peso as PS
                    try:
                        esq_ = dict(d.get("esquema") or {}); esq_.setdefault("_pasta", str(G.PASTA_EXEMPLOS / "monoplano"))
                        if self.path == "/api/peso":
                            return self._json(PS.calcula(esq_, d.get("opcoes"), d.get("motor"), d.get("mtow_kg")))
                        novo = PS.servos_no_modelo(esq_, float(d["servo_g"]))
                        return self._json({k: v for k, v in novo.items() if not k.startswith("_")})
                    except (ValueError, KeyError, TypeError) as e:
                        return self._json({"erro": str(e)}, 400)
                if self.path == "/api/chapeado_fe":
                    return self._json(AN.chapeado_fe(d))
                if self.path == "/api/cauda":
                    return self._json(AN.cauda(d))
                if self.path == "/api/nervuras_dxf":
                    return self._json(AN.nervuras_dxf(d))
                if self.path == "/api/planificacao":
                    return self._json(AN.planificacao(d))
                if self.path == "/api/nervuras/posicoes":
                    return self._json(AN.nervuras_posicoes(d))
                if self.path == "/api/secoes":
                    return self._json(AN.secoes(d))
                if self.path == "/api/vibracao":
                    return self._json(AN.vibracao(d))
                if self.path == "/api/torcao":
                    return self._json(AN.torcao(d))
                if self.path == "/api/uvlm":
                    return self._json(AN.uvlm(d))
                if self.path == "/api/helice":
                    return self._json(AN.helice(d))
                if self.path == "/api/convergencia/vlm":
                    return self._json(AN.convergencia_vlm(d))
                if self.path == "/api/aeroelastica":
                    return self._json(AN.aeroelastica(d))
                if self.path == "/api/calibracao":
                    return self._json(AN.calibracao(d))
                if self.path == "/api/massa_asa":
                    return self._json(AN.massa_asa(d))
                if self.path == "/api/flutter/tempo":
                    return self._json(AN.flutter_tempo(d))
                if self.path == "/api/flutter":
                    return self._json(AN.flutter(d))
                if self.path == "/api/torcao_fe":
                    return self._json(AN.torcao_fe(d))
                if self.path == "/api/juncao":
                    return self._json(AN.juncao(d))
                if self.path == "/api/cargas":
                    return self._json(AN.cargas(d))
                if self.path == "/api/controle":
                    return self._json(AN.controle(d))
                if self.path == "/api/propulsao":
                    return self._json(AN.propulsao(d))
                if self.path == "/api/decolagem":
                    return self._json(AN.decolagem(d))
                if self.path == "/api/perfil/le":
                    return self._json({"pontos": G.perfil_pontos(d.get("perfil", ""), d.get("pasta"), d.get("n", 81))})
                if self.path == "/api/perfil/grava":
                    return self._json(G.grava_perfil(d.get("nome", ""), d.get("pontos"), d.get("pasta"), est.pasta_aeronaves))
                if self.path == "/api/grava":
                    return self._json({"caminho": G.grava(d, est.pasta_aeronaves)})
                if self.path == "/api/configuracao":
                    est.cfg.definir_varias(d)
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
            except Exception as e:
                return self._falha_interna(e)
            return self._json({"erro": "não encontrado"}, 404)

    return H

def opcoes_da_linha(argv) -> tuple[int, bool]:
    porta, abrir = PORTA, True
    for i, a in enumerate(argv):
        if a == "--sem-navegador":
            abrir = False
        elif a == "--porta" and i + 1 < len(argv):
            porta = int(argv[i + 1])
        elif a.startswith("--porta="):
            porta = int(a.split("=", 1)[1])
    return porta, abrir


def quer_janela(argv, congelado: bool = False) -> bool:
    if "--navegador" in argv or "--sem-navegador" in argv:
        return False
    return "--janela" in argv or congelado


def _janela(url: str, srv) -> bool:
    try:
        import webview
    except Exception:
        return False
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window("AranduBIS", url, width=1440, height=900, min_size=(1024, 640))
        webview.start()
    except Exception as e:
        print(f"[aranduBIS] janela propria indisponivel ({e}); abrindo no navegador")
        webbrowser.open(url)
        try:
            while fio.is_alive():
                fio.join(0.5)
        except KeyboardInterrupt:
            pass
    srv.shutdown()
    return True


def servir(pasta_dados=None, porta: int = PORTA, abrir: bool = True, janela: bool = False) -> int:
    pasta = Path(pasta_dados) if pasta_dados else Path.cwd() / "dados"
    srv = ThreadingHTTPServer(("127.0.0.1", porta), fazer_handler(Estado(pasta)))
    url = f"http://127.0.0.1:{porta}/"
    print(f"[aranduBIS] {url}  (Ctrl+C encerra)")
    if janela and _janela(url, srv):
        return 0
    if abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    porta, abrir = opcoes_da_linha(sys.argv[1:])
    sys.exit(servir(porta=porta, abrir=abrir, janela=quer_janela(sys.argv[1:])))
