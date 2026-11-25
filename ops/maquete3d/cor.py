"""Cor da foto × cor do produto (cérebro 30/10).

O .glb leva a cor VERDADEIRA do produto (o visualizador 3D e o AR do cliente mostram o .glb); quem se
corrige é a exposição do render das fotos. Regra: o tom médio do corpo na foto fica a no máximo 15% da
cor oficial (diferença de luma sRGB ÷ 255). Prova do defeito: u03 preta #0B0B0C saía #989795 na foto.

Sem Blender: só PIL. `python ops/maquete3d/cor.py` roda o teste.
"""
import math

LIMITE = 0.15          # diferença máxima de tom (luma sRGB / 255)
EV_MIN, EV_MAX = -6.0, 2.0
# 30/10 (cérebro, depois da u03 virar silhueta): o material de contraste também é medido (limite 25%); produto
# escuro não baixa a exposição global (no máximo EV_ESCURO_MIN, último recurso): baixa o preenchimento
LIMITE_CONTRASTE = 0.25
ESCURO_LUMA = 64            # corpo com luma sRGB abaixo disto = produto escuro
CONTRASTE_LUMA = 40         # o contraste é o material de maior área que difere do corpo em pelo menos isto
PREENCHE_MIN, PREENCHE_MAX = 0.03, 1.5
EV_ESCURO_MIN = -1.5


# 07/11 (CEO: maquete branca "muito clara por conta da luz"): o laço de exposição mirava o tom oficial (#F3F2EF, luma 242)
# e estourava 81% do corpo da c22 em branco puro, sem relevo. Produto claro mira no máximo TETO_CLARO (ainda dentro do
# LIMITE de 15% do oficial): sobra faixa para a sombra e o brilho desenharem a forma.
TETO_CLARO = 212


def alvo_foto(cor):
    """Tom que o render da foto persegue: o oficial, ou o oficial escurecido até luma TETO_CLARO se for mais claro."""
    r, g, b = rgb(cor)
    lu = luma((r, g, b))
    if lu <= TETO_CLARO:
        return hexa((r, g, b))
    f = TETO_CLARO / lu
    return hexa((r * f, g * f, b * f))


def aceita(alvo, medido):
    """O laço de exposição para aqui? Dentro do LIMITE e, se o alvo é claro, sem passar do teto + 15 de luma
    (07/11: a p31 parou em #F8FAF9 com alvo #D0D5D7 — 14,7%, 'dentro' dos 15% — e saiu 91% estourada)."""
    if diferenca(alvo, medido) > LIMITE:
        return False
    return luma(alvo) < TETO_CLARO - 1 or luma(medido) <= TETO_CLARO + 15


def rgb(cor):
    """'#RRGGBB' ou (r, g, b) 0–255 → tupla de inteiros."""
    if isinstance(cor, str):
        h = cor.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(round(c)) for c in cor[:3])


def hexa(cor):
    return '#%02X%02X%02X' % rgb(cor)


def luma(cor):
    """Luma Rec. 709 em sRGB, 0–255 (o 'tom' que o olho compara)."""
    r, g, b = rgb(cor)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _linear(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def diferenca(alvo, medido):
    return abs(luma(alvo) - luma(medido)) / 255.0


def ajuste_ev(alvo, medido):
    """Quantos stops mexer na exposição para o tom medido chegar ao alvo (em luz linear)."""
    a, m = max(_linear(luma(alvo)), 1e-4), max(_linear(luma(medido)), 1e-4)
    return math.log2(a / m)


def tom_medio(png, mascara_png, alfa_min=0.98):
    """Média sRGB dos pixels do corpo: os opacos na máscara (render do corpo sozinho, o resto em holdout)."""
    from PIL import Image
    foto = Image.open(png).convert('RGBA')
    masc = Image.open(mascara_png).convert('RGBA').resize(foto.size, Image.NEAREST)
    lim = int(alfa_min * 255)
    soma, n = [0, 0, 0], 0
    for (r, g, b, a), (_, _, _, am) in zip(_pixels(foto), _pixels(masc)):
        if am >= lim and a >= lim:
            soma[0] += r; soma[1] += g; soma[2] += b; n += 1
    if not n:
        return None
    return tuple(round(s / n) for s in soma)


def _pixels(im):
    """Pixels em lista (Pillow ≥ 11.3: get_flattened_data; getdata sai no Pillow 14)."""
    f = getattr(im, 'get_flattened_data', None)
    return list(f()) if f else list(im.getdata())


def tom_opaco(png, alfa_min=0.98):
    """Média sRGB dos pixels opacos do render transparente (o produto inteiro, sem a sombra)."""
    from PIL import Image
    foto = Image.open(png).convert('RGBA')
    lim = int(alfa_min * 255)
    px = [x for x in _pixels(foto) if x[3] >= lim]
    if not px:
        return None
    return tuple(round(sum(x[k] for x in px) / len(px)) for k in range(3))


def _srgb(v):
    v = max(0.0, min(1.0, v))
    return round(255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))


def glb_cores(caminho):
    """[(hex sRGB, fração da área)] dos materiais do .glb, do maior para o menor (sem Blender).
    A área é a dos triângulos já transformados pelos nós (escala incluída)."""
    import json, struct
    from pathlib import Path
    dados = Path(caminho).read_bytes()
    tam, = struct.unpack_from('<I', dados, 12)
    gltf, binario = json.loads(dados[20:20 + tam]), dados[28 + tam:]
    comp, fmt = {'SCALAR': 1, 'VEC3': 3}, {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}

    def ler(i):
        a = gltf['accessors'][i]
        v = gltf['bufferViews'][a['bufferView']]
        n, f = comp[a['type']], fmt[a['componentType']]
        passo = v.get('byteStride') or n * struct.calcsize('<' + f)
        ini = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        return [struct.unpack_from('<%d%s' % (n, f), binario, ini + k * passo) for k in range(a['count'])]

    def mult(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    def matriz(no):
        if 'matrix' in no:
            m = no['matrix']
            return [[m[j * 4 + i] for j in range(4)] for i in range(4)]
        x, y, z, w = no.get('rotation', [0, 0, 0, 1])
        sx, sy, sz = no.get('scale', [1, 1, 1])
        tx, ty, tz = no.get('translation', [0, 0, 0])
        r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
             [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
             [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        return [[r[i][0] * sx, r[i][1] * sy, r[i][2] * sz, (tx, ty, tz)[i]] for i in range(3)] + [[0, 0, 0, 1]]

    area = {}

    def visitar(i, pai):
        no = gltf['nodes'][i]
        m = mult(pai, matriz(no))
        for prim in gltf['meshes'][no['mesh']]['primitives'] if 'mesh' in no else []:
            pos = [tuple(m[k][0] * x + m[k][1] * y + m[k][2] * z + m[k][3] for k in range(3))
                   for x, y, z in ler(prim['attributes']['POSITION'])]
            idx = [t[0] for t in ler(prim['indices'])] if 'indices' in prim else list(range(len(pos)))
            soma = 0.0
            for k in range(0, len(idx) - 2, 3):
                a, b, c = pos[idx[k]], pos[idx[k + 1]], pos[idx[k + 2]]
                u = [b[j] - a[j] for j in range(3)]; v = [c[j] - a[j] for j in range(3)]
                cx, cy, cz = u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]
                soma += 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5
            mat = prim.get('material', -1)
            area[mat] = area.get(mat, 0.0) + soma
        for f in no.get('children', []):
            visitar(f, m)

    ident = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    for i in gltf['scenes'][gltf.get('scene', 0)]['nodes']:
        visitar(i, ident)
    total = sum(area.values()) or 1.0
    saida = []
    for mat, a in sorted(area.items(), key=lambda x: -x[1]):
        f = (gltf['materials'][mat].get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1])
             if mat >= 0 else [1, 1, 1, 1])
        saida.append((hexa(tuple(_srgb(c) for c in f[:3])), round(a / total, 3)))
    return saida


def medir_sem_mascara(glb, render_transparente):
    """Para maquete sem `cor_render` (feita antes de 30/10): o tom dos pixels opacos da frente contra a média
    das cores do .glb pesada pela área (o corpo pesa mais; com peças de outra cor, a média é a justa)."""
    cores = glb_cores(glb)
    if not cores:
        return None
    alvo = tuple(round(sum(rgb(h)[k] * f for h, f in cores) / sum(f for _, f in cores)) for k in range(3))
    medido = tom_opaco(render_transparente)
    if medido is None:
        return None
    return {'alvo': hexa(alvo), 'corpo_glb': cores[0][0], 'foto': hexa(medido),
            'diferenca': round(diferenca(alvo, medido), 3), 'limite': LIMITE, 'medido_por': 'conferir (sem máscara)'}


def escuro(cor):
    return luma(cor) < ESCURO_LUMA


def contraste(materiais, corpo):
    """O material de contraste: o de maior área cuja cor difere do corpo em ≥ CONTRASTE_LUMA (u03: a alça amarela,
    não a borda preta). `materiais` = [(qualquer, hex, área)] do maior para o menor. None se não houver."""
    for item in materiais[1:]:
        if abs(luma(item[1]) - luma(corpo)) >= CONTRASTE_LUMA:
            return item
    return None


def _hsv(c):
    import colorsys
    r, g, b = (x / 255 for x in rgb(c))
    return colorsys.rgb_to_hsv(r, g, b)


def medir_contraste_sem_mascara(glb, render_transparente, alvo=None):
    """30/10 (cérebro): o --conferir mede o contraste também nas fotos já no disco (sem render novo, sem Blender).
    Contraste colorido (saturação ≥ 0,25: a alça amarela da u03): os pixels opacos com o mesmo matiz (±25°) e saturação
    ≥ 0,25. Contraste neutro (preto/branco): a fração de pixels mais claros (ou mais escuros) do tamanho da área dele.
    Devolve o mesmo formato do cor_render['contraste'] (ou None se o .glb não tem contraste)."""
    cores = glb_cores(glb)
    if not cores:
        return None
    ctr = contraste([(None, h, f) for h, f in cores], cores[0][0])
    if not ctr:
        return None
    alvo = alvo or ctr[1]
    from PIL import Image
    px = [x[:3] for x in _pixels(Image.open(render_transparente).convert('RGBA')) if x[3] >= 250]
    if not px:
        return None
    h, s, _ = _hsv(ctr[1])
    if s >= 0.25:
        # brilho ≥ 0,12: o preto do corpo com um tom amarelado de ruído não conta como alça
        sel = [p for p in px if _hsv(p)[1] >= 0.25 and _hsv(p)[2] >= 0.12
               and min(abs(_hsv(p)[0] - h), 1 - abs(_hsv(p)[0] - h)) <= 25 / 360]
    else:
        n = max(1, int(len(px) * min(max(ctr[2], 0.01), 0.3)))
        sel = sorted(px, key=luma, reverse=luma(ctr[1]) > luma(cores[0][0]))[:n]
    if len(sel) < 20:      # peça de contraste não aparece na frente: não dá para medir
        return None
    medido = tuple(round(sum(p[k] for p in sel) / len(sel)) for k in range(3))
    return {'alvo': hexa(alvo), 'foto': hexa(medido), 'diferenca': round(diferenca(alvo, medido), 3),
            'limite': LIMITE_CONTRASTE, 'medido_por': 'conferir (sem máscara, %d px)' % len(sel)}


def proximo_preenchimento(atual, alvo, medido):
    """Fator do preenchimento (fill + topo + ambiente) da próxima prova: a luz é linear, então o passo é a razão em
    luz linear, amortecida (0,8) porque a luz principal e o recorte não mudam."""
    a, m = max(_linear(luma(alvo)), 1e-4), max(_linear(luma(medido)), 1e-4)
    return max(PREENCHE_MIN, min(PREENCHE_MAX, atual * (a / m) ** 0.8))


def proxima_exposicao(atual, alvo, medido):
    """Exposição da próxima tentativa (80% do passo, para não passar do ponto com o mapa de tons)."""
    return max(EV_MIN, min(EV_MAX, atual + 0.8 * ajuste_ev(alvo, medido)))


def teste():
    assert alvo_foto('#2F6FD6') == '#2F6FD6' and abs(luma(alvo_foto('#F3F2EF')) - TETO_CLARO) < 1.5
    assert diferenca('#F3F2EF', alvo_foto('#F3F2EF')) <= LIMITE           # o teto não fura a regra dos 15%
    assert not aceita('#D0D5D7', '#F8FAF9') and aceita('#D0D5D7', '#D4D8DA')   # p31 de 07/11: estourada não passa
    assert aceita('#2F6FD6', '#3A78DD')                                    # cor média: regra antiga
    assert hexa('#0b0b0c') == '#0B0B0C' and rgb((1.2, 2, 3)) == (1, 2, 3)
    assert diferenca('#0B0B0C', '#989795') > LIMITE                      # u03: o defeito que o cérebro viu
    assert diferenca('#9EA1A3', '#9A9C9E') <= LIMITE                      # u04: média de luz e sombra
    assert ajuste_ev('#0B0B0C', '#989795') < -4                          # preto pede bem menos luz
    assert abs(ajuste_ev('#808080', '#808080')) < 1e-9
    assert proxima_exposicao(-0.55, '#000000', '#FFFFFF') == EV_MIN       # limite de segurança
    assert escuro('#0B0B0C') and not escuro('#9EA1A3') and not escuro('#2F6FD6')
    u03 = [(0, '#0B0B0C', 0.915), (1, '#060607', 0.056), (2, '#F2C200', 0.02)]
    assert contraste(u03, '#0B0B0C')[1] == '#F2C200'                    # a alça, não a borda preta
    assert contraste([(0, '#2F6FD6', 0.79), (1, '#1F4FA3', 0.17), (2, '#F4F6F8', 0.04)], '#2F6FD6')[1] == '#F4F6F8'
    assert contraste([(0, '#9EA1A3', 1.0)], '#9EA1A3') is None
    assert proximo_preenchimento(1.0, '#1A1D23', '#959290') < 0.2           # u03: o cinza pede bem menos preenchimento
    assert proximo_preenchimento(0.05, '#FFFFFF', '#000000') == PREENCHE_MAX
    import os, tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        f, m = os.path.join(d, 'f.png'), os.path.join(d, 'm.png')
        im = Image.new('RGBA', (4, 2), (0, 0, 0, 0))
        im.putpixel((0, 0), (100, 100, 100, 255)); im.putpixel((1, 0), (200, 200, 200, 255))
        im.putpixel((2, 0), (10, 10, 10, 255))                            # outra peça: fora da máscara
        im.save(f)
        mk = Image.new('RGBA', (2, 1), (0, 0, 0, 0))                     # máscara em resolução menor
        mk.putpixel((0, 0), (0, 0, 0, 255))
        mk.save(m)
        assert tom_medio(f, m) == (150, 150, 150)
    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    u03 = os.path.join(raiz, 'public', 'maquetes', 'u03')
    if os.path.isfile(os.path.join(u03, 'u03.glb')):                     # o .glb real: corpo preto em 9/10 da área
        cores = glb_cores(os.path.join(u03, 'u03.glb'))
        assert cores[0][0] == '#0B0B0C' and cores[0][1] > 0.9, cores
        foto = os.path.join(raiz, 'maquetes', 'renders', 'u03', 'frente.webp')
        rc = medir_contraste_sem_mascara(os.path.join(u03, 'u03.glb'), foto, '#E9CD25')
        assert rc is None or rc['alvo'] == '#E9CD25'                       # a régua 2.0 mede a alça das fotos no disco
        r = medir_sem_mascara(os.path.join(u03, 'u03.glb'), foto)
        assert r is None or r['diferenca'] <= LIMITE or r['foto'] != r['alvo']
    print('cor.py: teste ok')


if __name__ == '__main__':
    teste()
