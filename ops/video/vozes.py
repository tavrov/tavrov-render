# -*- coding: utf-8 -*-
"""Roda NA NUVEM (GitHub Actions, ramo vozes): gera a narração de cada pedido vozes/pedido/<chave>.json com o Kokoro
(hexgrad/Kokoro-82M, Apache-2.0; pacote kokoro 0.9.4 Apache-2.0; misaki Apache-2.0). 30/10 (cérebro): o português
(voz pf_/pm_) usa o espeak-ng (GPL) como fonetizador SÓ dentro deste runner, nunca distribuído nem no repositório; o
áudio sai do Kokoro e o GPL não cobre a saída do programa (FAQ do GPL). MOLDE-EUA §8 e 05-DECISOES.
CEO 30/10 (LISTA 5h): "só Kokoro"; nada instalado no PC. Grava vozes/saida/<chave>.wav (24 kHz) e <chave>.json com o
tempo de cada palavra [(palavra, início s, fim s)], o mesmo formato que o falar() do video_produto.py devolve.
Pedido = {"texto": "...", "voz": "af_heart", "velocidade": 1.0}. Chave = sha256 do texto (16 letras): texto mudou, voz nova.
Quem sobe e quem busca (artefato vozes-saida): ops/sistema/voz_lote.py.
"""
import glob, json, os

import numpy as np
import soundfile as sf
from kokoro import KPipeline

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAXA = 24000


def main():
    pipes = {}   # 1 pipeline por idioma: a 1ª letra da voz é o idioma do Kokoro (a = inglês dos EUA, p = português do Brasil)
    saida = os.path.join(RAIZ, "vozes", "saida")
    os.makedirs(saida, exist_ok=True)
    for ped in sorted(glob.glob(os.path.join(RAIZ, "vozes", "pedido", "*.json"))):
        chave = os.path.basename(ped)[:-5]
        if os.path.exists(os.path.join(saida, chave + ".wav")):
            continue
        p = json.load(open(ped, encoding="utf-8"))
        partes, palavras, t0 = [], [], 0.0
        voz = p.get("voz", "af_heart")
        if voz[0] not in pipes:
            pipes[voz[0]] = KPipeline(lang_code=voz[0])
        for r in pipes[voz[0]](p["texto"], voice=voz, speed=float(p.get("velocidade", 1.0))):
            audio = r.audio.numpy() if hasattr(r.audio, "numpy") else np.asarray(r.audio)
            for tk in (r.tokens or []):
                if tk.start_ts is not None and tk.end_ts is not None and any(ch.isalnum() for ch in tk.text):
                    palavras.append((tk.text, round(t0 + tk.start_ts, 3), round(t0 + tk.end_ts, 3)))
            partes.append(audio)
            t0 += len(audio) / TAXA
        sf.write(os.path.join(saida, chave + ".wav"), np.concatenate(partes), TAXA)
        json.dump({"voz": p.get("voz", "af_heart"), "texto": p["texto"], "palavras": palavras},
                  open(os.path.join(saida, chave + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{chave}: {t0:.1f} s, {len(palavras)} palavras", flush=True)
    imprimir(saida)


def imprimir(saida):
    """30/10: a cota de artefatos da conta encheu (o upload falhou). O job continua só de leitura: o áudio sai também
    no próprio log, em FLAC (sem perda) e base64, em linhas "@@VOZ <arquivo> <pedaço>"; voz_lote.py --receber remonta."""
    import base64, io
    for wav in sorted(glob.glob(os.path.join(saida, "*.wav"))):
        dados, taxa = sf.read(wav)
        buf = io.BytesIO()
        sf.write(buf, dados, taxa, format="FLAC")
        arquivos = {os.path.basename(wav)[:-4] + ".flac": buf.getvalue(),
                    os.path.basename(wav)[:-4] + ".json": open(wav[:-4] + ".json", "rb").read()}
        for nome, b in arquivos.items():
            t = base64.b64encode(b).decode()
            for i in range(0, len(t), 4000):
                print(f"@@VOZ {nome} {t[i:i + 4000]}", flush=True)


if __name__ == "__main__":
    main()
