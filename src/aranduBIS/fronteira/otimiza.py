from __future__ import annotations

import threading
import time
import uuid

from ..nucleo.otimiza import busca as B
from ..nucleo.otimiza import problema as P

_MAX_JOBS = 20

class ErroDeOtimiza(ValueError):
    pass

class _Parar(Exception):
    pass

class _Job:
    def __init__(self, jid: str, geracoes: int):
        self.id = jid
        self.lock = threading.Lock()
        self.parar_evt = threading.Event()
        self.historico: list[dict] = []
        self.estado = "rodando"
        self.erro: str | None = None
        self.refino: list[dict] | None = None
        self.geracoes_total = geracoes
        self.t0 = time.time()

_JOBS: dict[str, _Job] = {}
_JOBS_LOCK = threading.Lock()

def _guarda(job: _Job) -> None:
    with _JOBS_LOCK:
        _JOBS[job.id] = job
        if len(_JOBS) > _MAX_JOBS:
            for k in list(_JOBS)[:-_MAX_JOBS]:
                _JOBS.pop(k, None)

def inicia(problema: dict, execucao: dict | None = None) -> str:
    if not isinstance(problema, dict) or not problema.get("base", {}).get("elementos"):
        raise ErroDeOtimiza("o problema precisa de uma aeronave base: carregue ou desenhe uma na etapa 1")
    problemas = P.confere(problema)
    if problemas:
        raise ErroDeOtimiza(problemas[0])
    ex = execucao or {}
    pop = max(4, min(int(ex.get("populacao", 16)), 300))
    ger = max(1, min(int(ex.get("geracoes", 20)), 500))
    semente = int(ex.get("semente", 0))
    estrategia = ex.get("estrategia") if ex.get("estrategia") in ("melhor", "aleatoria") else "melhor"
    job = _Job(uuid.uuid4().hex[:10], ger)

    def ao_gerar(reg: dict) -> None:
        with job.lock:
            job.historico.append(reg)
        if job.parar_evt.is_set():
            raise _Parar()

    def roda():
        try:
            r = B.evolui(problema, populacao=pop, geracoes=ger, estrategia=estrategia, semente=semente,
                         processos=1, ao_gerar=ao_gerar)
            refino = B.refina(problema, r, quantos=3, processos=1)
            with job.lock:
                job.refino = refino
                job.estado = "concluido"
        except _Parar:
            with job.lock:
                job.estado = "parado"
        except Exception as e:
            with job.lock:
                job.estado = "erro"
                job.erro = str(e)

    _guarda(job)
    threading.Thread(target=roda, daemon=True).start()
    return job.id

def estado(jid: str) -> dict:
    job = _JOBS.get(jid)
    if job is None:
        raise ErroDeOtimiza("essa execução não existe mais (o servidor foi reiniciado?)")
    with job.lock:
        return {
            "id": job.id, "estado": job.estado, "erro": job.erro,
            "geracoes_total": job.geracoes_total, "historico": list(job.historico),
            "refino": job.refino, "tempo_s": time.time() - job.t0,
        }

def para(jid: str) -> None:
    job = _JOBS.get(jid)
    if job is None:
        raise ErroDeOtimiza("essa execução não existe mais")
    job.parar_evt.set()

def materializa(problema: dict, x: dict) -> dict:
    if not isinstance(problema, dict) or not problema.get("base", {}).get("elementos"):
        raise ErroDeOtimiza("problema sem aeronave base")
    try:
        esq, _ = P.monta(problema, x or {})
    except P.ProblemaInvalido as e:
        raise ErroDeOtimiza(str(e)) from None
    return esq
