"""Objetos do dia a dia para comparar o tamanho real (a "Régua Tavrov" do protótipo).

Cada um vira `public/maquetes/ref/<nome>.glb` (em metros, apoiado no chão, centro da base na
origem, frente para +Z no glTF) e entra na lista `public/maquetes/ref/referencias.json`, que o
visualizador lê. Medidas de objetos comuns no Brasil; nenhum tem marca, rótulo ou logotipo.

    python ops/gerar-3d.py --referencias
"""
import json
from pathlib import Path

# nome: (rótulo do botão, etiqueta curta no 3D, largura × profundidade × altura em cm,
#        faixa de tamanho do produto em que o objeto aparece — maior medida, cm)
CATALOGO = {
    'moeda':      ('Moeda de R$ 1', 'moeda · 2,7 cm', (2.7, 2.7, 0.19), (0, 15)),
    'cartao':     ('Cartão de banco', 'cartão · 8,6 cm', (8.56, 5.4, 0.08), (0, 40)),
    'celular':    ('Celular', 'celular · 14,7 cm', (7.1, 1.0, 14.7), (3, 150)),
    'lata':       ('Lata de 350 ml', 'lata · 12,2 cm', (6.6, 6.6, 12.2), (3, 80)),
    'caneca':     ('Caneca de café', 'caneca · 9,5 cm', (11.0, 8.2, 9.5), (4, 60)),
    'detergente': ('Detergente 500 ml', 'detergente · 21 cm', (6.4, 4.4, 21.0), (8, 80)),
    'garrafa2l':  ('Garrafa PET de 2 litros', 'garrafa 2 L · 33 cm', (10.5, 10.5, 33.0), (15, 200)),
    'pessoa':     ('Pessoa de 1,70 m', 'pessoa · 1,70 m', (53.3, 27.5, 170.0), (45, 100000)),
}

# o que ligar de saída pelo tamanho do produto (maior medida, cm) — produtos de todos os tamanhos
def sugeridas(maior_cm, tipo=None):
    """No máximo 2 objetos ligados de saída (mais que isso polui a cena — CEO, 27/09)."""
    if maior_cm < 6:
        return ['moeda', 'cartao']
    if maior_cm < 15:
        return ['moeda', 'celular'] if maior_cm < 9 else ['celular', 'lata']
    if maior_cm <= 45:
        return {'chapa': ['celular', 'detergente'], 'almofada': ['celular', 'garrafa2l']}.get(tipo, ['celular', 'lata'])
    if maior_cm <= 90:
        return ['garrafa2l', 'pessoa']
    return ['pessoa']


def _celular(e):
    moldura = e.mat('aluminio_anodizado', '#3B3D42')
    tela = e.mat('vidro_tela', '#0B0C0F')
    e.caixa('corpo', 7.1, 0.8, 14.7, pos=(0, 0, 7.35), mat=moldura, raio=0.38, segmentos=5)
    e.caixa('tela', 6.75, 0.04, 14.35, pos=(0, -0.41, 7.35), mat=tela, raio=0.02)
    e.caixa('camera', 2.6, 0.18, 2.6, pos=(-1.8, 0.45, 12.0), mat=moldura, raio=0.5)
    for i, (x, z) in enumerate(((-2.35, 12.55), (-1.25, 11.45))):
        e.cilindro(f'lente-{i}', 0.9, 0.12, pos=(x, 0.55, z), rot=(90, 0, 0), mat=tela, raio=0.03)


def _lata(e):
    lata = e.mat('aluminio_escovado', '#C9CDD2')
    faixa = e.mat('metal_pintado', '#B3262C')       # cor lisa, sem marca
    e.cilindro('corpo', 6.6, 10.6, pos=(0, 0, 0.3 + 5.3), mat=lata, raio=0.25)
    e.cilindro('base', 6.6, 0.3, pos=(0, 0, 0.15), d_topo=6.6, mat=lata, raio=0.1)
    e.cilindro('faixa', 6.62, 6.0, pos=(0, 0, 5.6), mat=faixa, raio=0.02)
    e.cilindro('ombro', 6.6, 1.0, pos=(0, 0, 11.4), d_topo=5.4, mat=lata, raio=0.05)
    e.cilindro('tampa', 5.4, 0.3, pos=(0, 0, 12.05), mat=lata, raio=0.08)


def _detergente(e):
    frasco = e.mat('plastico_brilhante', '#9FD4A8')
    tampa = e.mat('plastico_fosco', '#EDEAE4')
    corpo = e.cilindro('corpo', 6.4, 16.5, pos=(0, 0, 8.25), mat=frasco, raio=0.9)
    corpo.scale.y = 4.4 / 6.4
    ombro = e.cilindro('ombro', 6.4, 1.8, pos=(0, 0, 17.4), d_topo=2.8, mat=frasco, raio=0.3)
    ombro.scale.y = 4.4 / 6.4
    e.cilindro('tampa', 2.8, 2.7, pos=(0, 0, 19.65), d_topo=1.6, mat=tampa, raio=0.25)


def _garrafa2l(e):
    pet = e.mat('plastico_transparente', '#CFE6EF')
    tampa = e.mat('plastico_fosco', '#2F6FB5')
    e.cilindro('base', 10.5, 2.0, pos=(0, 0, 1.0), d_topo=10.5, mat=pet, raio=0.8)
    e.cilindro('corpo', 10.5, 21.0, pos=(0, 0, 12.5), mat=pet, raio=0.2)
    e.cilindro('ombro', 10.5, 6.8, pos=(0, 0, 26.4), d_topo=2.8, mat=pet, raio=0.3)
    e.cilindro('gargalo', 2.8, 1.8, pos=(0, 0, 30.7), mat=pet, raio=0.1)
    e.cilindro('tampa', 3.1, 1.4, pos=(0, 0, 32.3), mat=tampa, raio=0.2)


def _caneca(e):
    loica = e.mat('plastico_brilhante', '#F4F1EC')      # cerâmica esmaltada
    # perfil de torno: fora de baixo para cima, borda, e dentro de cima para baixo (parede 4 mm)
    e.torneado('corpo', [(0, 0), (3.7, 0), (4.0, 0.1), (4.1, 0.4), (4.1, 9.3), (4.07, 9.45), (3.95, 9.5),
                         (3.8, 9.45), (3.7, 9.3), (3.7, 1.0), (3.55, 0.7), (3.2, 0.6), (0, 0.6)], loica)
    alca = e.toro('alca', 5.0, 1.0, pos=(4.1 + 0.6, 0, 4.9), rot=(90, 0, 0), mat=loica)
    alca.scale.x = 0.75


def _cartao(e):
    cartao = e.mat('plastico_brilhante', '#6E1F2A')
    chip = e.mat('metal_cromado', '#C9A64B')
    e.caixa('cartao', 8.56, 5.4, 0.08, pos=(0, 0, 0.04), mat=cartao, raio=0.03)
    e.caixa('chip', 1.1, 0.85, 0.02, pos=(-2.6, 0.6, 0.09), mat=chip, raio=0.01)


def _moeda(e):
    borda = e.mat('metal_cromado', '#C8A54A')          # anel dourado, miolo prateado (sem desenho)
    miolo = e.mat('metal_cromado', '#C9CDD2')
    e.torneado('anel', [(0, 0), (1.35, 0), (1.35, 0.19), (0, 0.19)], borda)
    e.cilindro('miolo', 1.9, 0.2, pos=(0, 0, 0.095), mat=miolo, raio=0.02)


def _pessoa(e):
    """Manequim de madeira (de artista), 1,70 m: escala humana sem virar desenho."""
    m = e.mat('madeira', '#C9A57C')
    e.esfera('cabeca', 21, pos=(0, 0, 159.5), mat=m, escala=(0.78, 0.9, 1.0))
    e.cilindro('pescoco', 9, 8, pos=(0, 0, 146), mat=m, raio=1)
    e.caixa('tronco', 36, 20, 52, pos=(0, 0, 116), mat=m, raio=9, segmentos=6)
    e.caixa('quadril', 32, 19, 16, pos=(0, 0, 86), mat=m, raio=7, segmentos=6)
    for s in (-1, 1):
        e.cilindro(f'braco{s}', 8, 30, pos=(s * 21.5, 0, 125), mat=m, raio=3.5, rot=(0, s * 6, 0))
        e.cilindro(f'antebraco{s}', 7, 27, pos=(s * 23, 0, 97), mat=m, raio=3, rot=(0, s * 3, 0))
        e.esfera(f'mao{s}', 8, pos=(s * 23.5, 0, 81), mat=m, escala=(0.6, 1.0, 1.2))
        e.cilindro(f'coxa{s}', 14, 42, pos=(s * 9, 0, 57), mat=m, raio=6)
        e.cilindro(f'canela{s}', 10, 40, pos=(s * 9, 0, 17), mat=m, raio=4)
        e.caixa(f'pe{s}', 9, 25, 5, pos=(s * 9, -5.5, 2.5), mat=m, raio=2.2)
    # fecha exatamente 1,70 m de altura (escala o boneco inteiro, mantendo as proporções)
    lo, hi = e.caixa_envolvente()
    k = 1.70 / (hi.z - lo.z)
    for ob in e.pecas:
        ob.location *= k
        ob.scale *= k


MODELOS = {'celular': _celular, 'lata': _lata, 'detergente': _detergente, 'garrafa2l': _garrafa2l,
           'caneca': _caneca, 'cartao': _cartao, 'moeda': _moeda, 'pessoa': _pessoa}


def gerar_todas(destino):
    """Gera os .glb dos objetos de comparação e o referencias.json. Devolve o índice."""
    import json
    from .estudio import Estudio
    destino.mkdir(parents=True, exist_ok=True)
    indice = {}
    for nome in CATALOGO:                  # a ordem do catálogo é a ordem dos botões
        montar = MODELOS[nome]
        e = Estudio(f'ref-{nome}')
        montar(e)
        med = e.medidas_cm()
        rotulo, etiqueta, (L, P, A), (de, ate) = CATALOGO[nome]
        from .estudio import tolerancia_cm
        for obtido, esperado in zip(med, (L, P, A)):
            if abs(obtido - esperado) > tolerancia_cm(esperado):
                raise SystemExit(f'referência {nome}: {med} cm não bate com {L} × {P} × {A} cm')
        e.exportar_glb(destino / f'{nome}.glb')
        indice[nome] = {'rotulo': rotulo, 'etiqueta': etiqueta, 'medidas_cm': {'L': L, 'P': P, 'A': A},
                        'para_produtos_cm': [de, ate], 'glb': f'{nome}.glb'}
        print(f'ref {nome}: {med[0]} × {med[1]} × {med[2]} cm')
    (destino / 'referencias.json').write_text(json.dumps(indice, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return indice


# 30/10 (cérebro): as páginas /loja/ (EN, EUA) usam referências americanas. Mesmas chaves do CATALOGO (os specs
# continuam com 'moeda', 'celular'...); a moeda vira o quarter, com .glb próprio. Medida = a do objeto 3D, com fonte.
CATALOGO_EN = {
    'moeda':      ('US quarter', 'quarter · 0.96 in (2.43 cm)', (2.426, 2.426, 0.175), (0, 15), 'moeda-us.glb',
                   'US Mint, quarter dollar specifications: 24.26 mm diameter, 1.75 mm thick'),
    'cartao':     ('Credit card', 'card · 3.37 in (8.6 cm)', (8.56, 5.4, 0.08), (0, 40), 'cartao.glb',
                   'ISO/IEC 7810 ID-1 card size: 85.60 × 53.98 mm'),
    'celular':    ('Smartphone', 'phone · 5.8 in (14.7 cm)', (7.1, 1.0, 14.7), (3, 150), 'celular.glb',
                   'a common smartphone size: 147.6 × 71.6 mm, 6.1-inch screen class'),
    'lata':       ('12 oz soda can', 'can · 4.8 in (12.2 cm)', (6.6, 6.6, 12.2), (3, 80), 'lata.glb',
                   'standard US 12 fl oz beverage can: about 2.6 in wide, 4.83 in tall'),
    'caneca':     ('Coffee mug', 'mug · 3.7 in (9.5 cm)', (11.0, 8.2, 9.5), (4, 60), 'caneca.glb',
                   'a typical 11 oz ceramic mug: 3.25 in wide, 3.75 in tall (handle included in the width)'),
    'detergente': ('Dish soap bottle', 'bottle · 8.3 in (21 cm)', (6.4, 4.4, 21.0), (8, 80), 'detergente.glb',
                   'the 3D bottle is 21 cm (8.3 in) tall, about a 16.9 fl oz (500 ml) bottle'),
    'garrafa2l':  ('2-liter soda bottle', '2 L bottle · 13 in (33 cm)', (10.5, 10.5, 33.0), (15, 200), 'garrafa2l.glb',
                   'the 3D bottle is 33 cm (13 in) tall, the size of a 2-liter soda bottle'),
    'pessoa':     ('Person, 5 ft 7 in', 'person · 5 ft 7 in (1.70 m)', (53.3, 27.5, 170.0), (45, 100000), 'pessoa.glb',
                   'a 1.70 m (5 ft 7 in) adult figure'),
}


def _glb_quarter(caminho, d_cm=2.426, h_cm=0.175, lados=64):
    """O quarter em .glb sem Blender: cilindro prateado (metros, Y para cima, base em y = 0, centro na origem)."""
    import math
    import struct
    r, h = d_cm / 200, h_cm / 100
    pos, nor, idx = [], [], []

    def v(p, n):
        pos.append(p); nor.append(n)
        return len(pos) - 1
    for y, ny in ((h, 1.0), (0.0, -1.0)):          # tampas
        c = v((0.0, y, 0.0), (0.0, ny, 0.0))
        anel = [v((r * math.cos(2 * math.pi * i / lados), y, r * math.sin(2 * math.pi * i / lados)), (0.0, ny, 0.0))
                for i in range(lados)]
        for i in range(lados):
            a, b = anel[i], anel[(i + 1) % lados]
            idx += [c, b, a] if ny > 0 else [c, a, b]
    lado = []
    for i in range(lados):                          # borda
        t = 2 * math.pi * i / lados
        n = (math.cos(t), 0.0, math.sin(t))
        lado.append((v((r * n[0], 0.0, r * n[2]), n), v((r * n[0], h, r * n[2]), n)))
    for i in range(lados):
        (a0, a1), (b0, b1) = lado[i], lado[(i + 1) % lados]
        idx += [a0, a1, b1, a0, b1, b0]
    bpos = b''.join(struct.pack('<3f', *p) for p in pos)
    bnor = b''.join(struct.pack('<3f', *n) for n in nor)
    bidx = b''.join(struct.pack('<H', i) for i in idx)
    bidx += b'\x00' * ((4 - len(bidx) % 4) % 4)
    binario = bpos + bnor + bidx
    xs = [p[0] for p in pos]; ys = [p[1] for p in pos]; zs = [p[2] for p in pos]
    gltf = {
        'asset': {'version': '2.0', 'generator': 'Tavrov referencias.py (quarter sem Blender)'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': 'quarter'}],
        'materials': [{'name': 'quarter-niquel', 'pbrMetallicRoughness': {
            'baseColorFactor': [0.72, 0.73, 0.75, 1.0], 'metallicFactor': 1.0, 'roughnessFactor': 0.38}}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1}, 'indices': 2, 'material': 0}]}],
        'buffers': [{'byteLength': len(binario)}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(bpos), 'target': 34962},
                        {'buffer': 0, 'byteOffset': len(bpos), 'byteLength': len(bnor), 'target': 34962},
                        {'buffer': 0, 'byteOffset': len(bpos) + len(bnor), 'byteLength': len(idx) * 2, 'target': 34963}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': len(pos), 'type': 'VEC3',
                       'min': [min(xs), min(ys), min(zs)], 'max': [max(xs), max(ys), max(zs)]},
                      {'bufferView': 1, 'componentType': 5126, 'count': len(nor), 'type': 'VEC3'},
                      {'bufferView': 2, 'componentType': 5123, 'count': len(idx), 'type': 'SCALAR'}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binario)
    Path(caminho).write_bytes(struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(js), b'JSON') + js
                              + struct.pack('<I4s', len(binario), b'BIN\x00') + binario)


def gerar_en(destino):
    """public/maquetes/ref/referencias-en.json + moeda-us.glb (sem Blender; os outros .glb são os do catálogo BR)."""
    destino.mkdir(parents=True, exist_ok=True)
    _glb_quarter(destino / 'moeda-us.glb')
    indice = {}
    for nome, (rotulo, etiqueta, (L, P, A), (de, ate), glb, fonte) in CATALOGO_EN.items():
        indice[nome] = {'rotulo': rotulo, 'etiqueta': etiqueta, 'medidas_cm': {'L': L, 'P': P, 'A': A},
                        'para_produtos_cm': [de, ate], 'glb': glb, 'fonte': fonte}
    (destino / 'referencias-en.json').write_text(json.dumps(indice, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return indice
