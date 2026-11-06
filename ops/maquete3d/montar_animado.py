"""Monta o vídeo animado (FÁBRICA 2.0) a partir dos planos do animar.py: cada plano sobre uma cor da marca que muda no
ritmo (mestres: SISTEMA/divulgacao/mestres/animado.md), texto curto e grande que sobe e acende (legenda em movimento),
selo TAVROV no topo, rótulo "Tavrov 3D animation · real size" e o fecho com o link. Sai MUDO, 1080×1920, h264;
a voz Kokoro entra depois (video_animado.py, no PC, só junta o áudio).

Uso: python ops/maquete3d/montar_animado.py <roteiro.json> <pasta dos planos> <saida.mp4>
Roteiro: {"planos": [{"pasta": "S1-gancho", "fundo": "#2A1416", "texto": "...", "miudo": "..."}...],
          "fecho": {"texto": "Link in bio → Tavrov US store", "rodape": "tavrov.com/us/self-cleaning-pet-grooming-brush · @tavrovoficial", "segundos": 2.5},
          "rotulo": "Tavrov 3D animation · real size"}
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONTE = os.environ.get("TAVROV_FONTE", "C\\:/Windows/Fonts/arialbd.ttf")
SELO = os.path.join(RAIZ, "social", "marca", "selo.png")
FPS = 24
ESCURO, OURO = "0x140B0C", "0xD9B65E"


def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def texto_animado(linhas, y0, tam, cor="white", atraso=0.0, passo=None):
    """cada linha sobe 40 px e acende em 0,25 s, uma depois da outra (0,08 s): a legenda em movimento"""
    passo = passo or int(tam * 1.18)
    out = []
    for k, l in enumerate(linhas):
        t0 = atraso + k * 0.08
        out.append(f"drawtext=fontfile='{FONTE}':expansion=none:text='{esc(l)}':fontsize={tam}:fontcolor={cor}:borderw=4"
                   f":bordercolor={ESCURO}:x=(w-tw)/2:y='{y0 + k * passo}+40*max(0\\,1-(t-{t0})/0.25)'"
                   f":alpha='min(1\\,max(0\\,(t-{t0})/0.25))'")
    return out


def plano(p, pasta, i, tmp, rotulo):
    quadros = sorted(f for f in os.listdir(os.path.join(pasta, p["pasta"])) if f.endswith(".png"))
    seg = len(quadros) / FPS
    fundo = p.get("fundo", "#2A1416").replace("#", "0x")
    # v2 30/10: quadro 9:16 cheio (sem faixa preta) e a legenda no terço de baixo, fora do produto; no 1º plano o texto
    # já está aceso no quadro 0 (o gancho tem de estar na tela no 1º segundo, regra do mestre e do TikTok)
    filtros = [f"[1:v]scale=1080:1920:flags=lanczos[m];[0:v][m]overlay=0:0:shortest=1"]
    linhas = textwrap.wrap(p.get("texto", ""), 20)[:3]
    y0 = 1500 - 97 * (len(linhas) - 1)
    filtros += texto_animado(linhas, y0, 82, atraso=-1.0 if i == 1 else 0.0)
    if p.get("miudo"):
        filtros += texto_animado([p["miudo"]], 1500 + 110, 40, cor=OURO, atraso=-1.0 if i == 1 else 0.15)
    filtros.append(f"drawtext=fontfile='{FONTE}':expansion=none:text='{esc(rotulo)}':fontsize=32:fontcolor=white"
                   f":box=1:boxcolor={ESCURO}@0.6:boxborderw=10:x=(w-tw)/2:y=170")
    saida = os.path.join(tmp, f"p{i:02d}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={fundo}:s=1080x1920:r={FPS}:d={seg}",
                    "-framerate", str(FPS), "-i", os.path.join(pasta, p["pasta"], "%04d.png"),
                    "-filter_complex", ",".join(filtros) + ",format=yuv420p", "-r", str(FPS), "-t", f"{seg}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", saida], check=True)
    return saida, seg


def fecho(f, tmp):
    seg = float(f.get("segundos", 2.5))
    filtros = texto_animado(textwrap.wrap(f["texto"], 18)[:3], 820, 90)
    filtros.append(f"drawtext=fontfile='{FONTE}':expansion=none:text='{esc(f['rodape'])}':fontsize=44:fontcolor={OURO}"
                   f":x=(w-tw)/2:y=h-180")
    saida = os.path.join(tmp, "fim.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={ESCURO}:s=1080x1920:r={FPS}:d={seg}",
                    "-vf", ",".join(filtros) + ",format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    saida], check=True)
    return saida, seg


def montar(roteiro, pasta, saida):
    r = json.load(open(roteiro, encoding="utf-8"))
    tmp = tempfile.mkdtemp()
    clipes = [plano(p, pasta, i, tmp, r.get("rotulo", "Tavrov 3D animation · real size")) for i, p in enumerate(r["planos"], 1)]
    clipes.append(fecho(r["fecho"], tmp))
    lista = os.path.join(tmp, "lista.txt")
    open(lista, "w").write("".join(f"file '{c}'\n" for c, _ in clipes))
    junto = os.path.join(tmp, "junto.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", junto], check=True)
    # selo TAVROV no topo do vídeo inteiro (o mesmo do video_produto.py)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", junto, "-loop", "1", "-i", SELO, "-filter_complex",
                    "[1:v]scale=440:-1[s];[0:v][s]overlay=(W-w)/2:24:shortest=1,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-movflags", "+faststart", saida], check=True)
    total = sum(s for _, s in clipes)
    print(f"OK {saida} {total:.1f} s ({len(clipes)} partes; {r['fecho'].get('segundos', 2.5)} s de cartão parado)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    montar(*sys.argv[1:])
