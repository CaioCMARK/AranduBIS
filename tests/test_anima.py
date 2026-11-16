import shutil
import subprocess

import pytest

pytest.importorskip("matplotlib")
from aranduBIS.nucleo import anima as A
from aranduBIS.fronteira import geometria as G

def _tem_ffmpeg():
    try:
        A.ffmpeg(); return True
    except A.ErroDeAnimacao:
        return False

@pytest.mark.skipif(not _tem_ffmpeg(), reason="sem ffmpeg")
def test_mp4_h264_toca_em_qualquer_lugar(tmp_path):
    esq = G.abre_exemplo("generico/asa_canard.json")
    b, tipo = A.modos(esq, 18.75, "mp4", "h264", largura=481, fps=10, n_modos=1, segundos_por_modo=1.2)
    assert tipo == "video/mp4" and b[4:8] == b"ftyp"
    f = tmp_path / "m.mp4"; f.write_bytes(b)
    sonda = shutil.which("ffprobe")
    if sonda:
        r = subprocess.run([sonda, "-v", "error", "-show_entries", "stream=codec_name,pix_fmt,width,height", "-of", "csv=p=0", str(f)],
                           capture_output=True, text=True)
        cod, w, h, pix = r.stdout.strip().split(",")
        assert cod == "h264" and pix == "yuv420p" and int(w) % 2 == 0 and int(h) % 2 == 0

def test_formato_e_codec_invalidos_sao_recusados():
    esq = G.abre_exemplo("generico/asa_canard.json")
    with pytest.raises(A.ErroDeAnimacao):
        A.modos(esq, 18.75, "webm")
    with pytest.raises(A.ErroDeAnimacao):
        A.codificador("vp9")

def test_sem_longarina_nao_tem_o_que_animar():
    esq = G.abre_exemplo("asa_ar3_naca0012.json")
    with pytest.raises(A.ErroDeAnimacao, match="longarina"):
        A.modos(esq, 18.75, "gif")
