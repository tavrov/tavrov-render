"""Gera a maquete 3D de estúdio de cada produto (seção D0 da tarefa nuvem 06).

    python ops/gerar-3d.py --pronto p12   # O FLUXO INTEIRO de um produto: render final, 3D, AR, conferência,
                                          # site (cartão + página do produto) e prévia para o CEO aprovar
    python ops/gerar-3d.py p07            # um produto (só a maquete)
    python ops/gerar-3d.py --todos        # todo maquetes/*.json
    python ops/gerar-3d.py p07 --rapido   # rascunho: poucas amostras, meia resolução
    python ops/gerar-3d.py --conferir     # só confere o que já foi gerado (sem Blender)
    python ops/gerar-3d.py --so-glb p07   # só refaz o 3D (.glb/.usdz) e o maquete.json
    python ops/gerar-3d.py --recompor     # troca o fundo das fotos SEM Blender, a partir dos renders
                                          # transparentes guardados em maquetes/renders/<cod>/
    python ops/gerar-3d.py --referencias  # objetos de comparação (moeda, celular, lata, garrafa, pessoa...)
    python ops/gerar-3d.py --previa       # cópia do visualizador para o link de prévia (aprovação do CEO)
    python ops/gerar-3d.py --arquivo      # um .html só, para mandar por WhatsApp e abrir sem internet
    python ops/gerar-3d.py --novo p12 --tipo torneado --nome "Garrafa Térmica" --medidas 8x8x26 \
        --fonte "Anúncio MLB... (Mercado Livre), consultado em DD/MM/AAAA" --anuncio https://...
                                          # molde de produto novo: cria maquetes/p12.json + p12.py
                                          # --tipo pote|garrafa|caixa_organizadora|utensilio|tapete|eletronico:
                                          # molde PARAMÉTRICO — só preencher "molde" no JSON (ops/maquete3d/moldes.py)

Entrada:  maquetes/<cod>.json (medidas, fontes, câmeras) + maquetes/<cod>.py (modelagem).
Saída:    public/maquetes/<cod>/frente.jpg · lado.jpg · detalhe.jpg (1600×1200, estúdio)
          maquetes/renders/<cod>/<vista>.webp (render transparente com a sombra, guardado para recompor)
          public/maquetes/<cod>/cartao.webp (800×800, vitrine) · <cod>.glb (3D + realidade aumentada)
          public/maquetes/<cod>/maquete.json (medidas medidas no 3D, legenda, alt, conferência)

Precisa de `pip install bpy pillow` (Blender como módulo Python 3.11). Roda na nuvem;
não precisa de Blender instalado no PC.
"""
import argparse
import importlib.util
import json
import re
import struct
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MAQUETES = RAIZ / 'maquetes'
SAIDA = RAIZ / 'public' / 'maquetes'
LEGENDA = ('Maquete Tavrov nas medidas informadas no anúncio. '
           'Forma e cores fiéis ao produto; acabamento e textura podem variar.')
VISTAS = ('frente', 'lado', 'detalhe')
RENDERS = MAQUETES / 'renders'


CABECALHO = '''"""{cod} · {nome} — {L} × {P} × {A} cm (L × P × A).

Descreva aqui a forma, como nas fotos oficiais do anúncio (só referência; sem logotipo).
Peças do estúdio: e.caixa · e.cilindro · e.esfera · e.tubo · e.toro · e.engrenagem · e.furar · e.rasgos
Blocos prontos: e.rebaixo_face (painel do cubo p16) · e.almofada (peça macia da p08)
Materiais: aluminio_escovado, aluminio_anodizado, inox_escovado, metal_cromado, metal_pintado,
plastico_fosco, plastico_brilhante, plastico_transparente, silicone, borracha, pelucia, tecido,
madeira, vidro. Cores: hex sRGB tiradas da foto oficial; metal claro de verdade (alumínio ~#B4B8BD).
Eixos: X = largura, Y = profundidade (frente em -Y), Z = altura; apoiado em z = 0; tudo em cm.
O gerador recusa a maquete se a caixa envolvente fugir da medida (1% dela, entre 1 e 5 mm).
"""
'''

# Um molde por tipo de produto: o ponto de partida que deu certo no piloto.
MOLDES = {
    'caixa': '''

def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    corpo = e.mat('plastico_fosco', '#D9D4CE')          # troque pelo material e pela cor da foto oficial
    e.caixa('corpo', L, P, A, pos=(0, 0, A / 2), mat=corpo, raio=0.4)
''',
    'cilindro': '''

def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    corpo = e.mat('inox_escovado', '#C9CDD2')           # garrafa, pote, copo, luminária...
    tampa = e.mat('plastico_fosco', '#2B2B2E')
    e.cilindro('corpo', L, A * 0.85, pos=(0, 0, A * 0.425), mat=corpo, raio=0.3)
    e.cilindro('tampa', L * 0.9, A * 0.15, pos=(0, 0, A * 0.925), mat=tampa, raio=0.25)
''',
    'chapa': '''

ESP = 0.15                                              # espessura da chapa (cm) — organizador p07


def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    chapa = e.mat('aluminio_anodizado', '#B4B8BD')
    fundo = e.caixa('fundo', L, P, ESP, pos=(0, 0, ESP / 2), mat=chapa, raio=0.06)
    e.rasgos(fundo, 'x', (0, 0, ESP / 2), n=int(L // 1.4), passo=1.3, largura=0.45, comprimento=P * 0.6, normal='z')
    costas = e.caixa('costas', L, ESP, A, pos=(0, P / 2 - ESP / 2, A / 2), mat=chapa, raio=0.06)
    e.rasgos(costas, 'x', (0, P / 2 - ESP / 2, A * 0.58), n=int(L // 1.3), passo=1.2, largura=0.42, comprimento=A * 0.55)
    for s in (-1, 1):
        e.caixa(f'lateral{s}', ESP, P, A * 0.6, pos=(s * (L / 2 - ESP / 2), 0, A * 0.3), mat=chapa, raio=0.06)
    e.caixa('frente', L, ESP, A * 0.45, pos=(0, -P / 2 + ESP / 2, A * 0.225), mat=chapa, raio=0.06)
''',
    'cubo': '''

REB = 1.0                                               # profundidade dos painéis (cm) — cubo p16


def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    corpo = e.caixa('corpo', L, P, A, pos=(0, 0, A / 2), mat=e.mat('plastico_brilhante', '#ECE7DE'), raio=1.3, segmentos=6)
    pl, ph = L - 2.8, A - 2.8
    for face, cor in (('frente', '#DCEFF7'), ('dir', '#EDE4F7'), ('esq', '#FDE9D9'), ('costas', '#E4F4E1')):
        e.rebaixo_face(corpo, face, pl, ph, cor, prof=REB, centro_z=A / 2)
    # ponha as peças de cada face dentro do rebaixo (entre o fundo e a face): engrenagens,
    # botões, cordas... como em maquetes/p16.py
''',
    'torneado': '''

def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    r = L / 2
    # perfil de torno (raio, altura) em cm: fora de baixo para cima, borda, dentro de cima para baixo.
    # garrafa, copo, vaso, pote, luminária — desenhe o perfil olhando a foto oficial de lado.
    parede = max(0.2, r * 0.06)
    e.torneado('corpo', [(0, 0), (r * 0.92, 0), (r, A * 0.03), (r, A * 0.97), (r - parede / 2, A),
                         (r - parede, A * 0.97), (r - parede, A * 0.08), (0, A * 0.06)],
               e.mat('plastico_brilhante', '#E9E4DC'))
''',
    'almofada': '''

def modelar(e, spec):
    L, P, A = (spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
    # peça macia de pé, como a p08; ajuste lombar/abas/costas ao formato da foto oficial
    borda = e.almofada('almofada', L, P, A, e.mat('pelucia', '#1C1C1F'), vivo=0.42, cor_vivo='#161618')
    # `borda` = pontos da costura (cm): use para zíper, etiqueta ou alça (veja maquetes/p08.py)
''',
}

# Moldes PARAMÉTRICOS (ops/maquete3d/moldes.py): a maquete inteira sai das medidas + "molde" do JSON
# (cores hex e poucos parâmetros), sem modelar à mão — o .py do produto é 1 linha.
PARAMETRICOS = ('caixa_organizadora', 'pote', 'garrafa', 'utensilio', 'tapete', 'eletronico')
for _nome in PARAMETRICOS:
    MOLDES[_nome] = '''
# molde paramétrico: as peças saem de "molde" em maquetes/<cod>.json (parâmetros em ops/maquete3d/moldes.py)
from maquete3d.moldes import modelar_por_molde as modelar  # noqa: E402,F401
'''

# objetos de comparação ligados de saída, por tipo (catálogo em ops/maquete3d/referencias.py)
# os objetos de comparação ligados de saída vêm do tamanho do produto (referencias.sugeridas):
# moeda e cartão para o que é pequeno, celular/lata/garrafa no meio, pessoa de 1,70 m no que é grande


def _sugeridas(maior_cm, tipo):
    sys.path.insert(0, str(RAIZ / 'ops'))
    from maquete3d.referencias import sugeridas
    return sugeridas(maior_cm, tipo)


FONTE_REPRESENTATIVA = 'Proporções estimadas pelas fotos oficiais; o fornecedor não informou a medida exata'
LEGENDA_REPRESENTATIVA = ('Maquete Tavrov representativa, feita pelas fotos oficiais: o fornecedor não informou a medida exata. '
                          'Forma e cores fiéis ao produto; o tamanho é aproximado.')


def novo(cod, nome, medidas, fonte, anuncio, tipo='caixa', representativa=False):
    """Molde de maquete nova no padrão Tavrov (câmeras, legenda, referências e conferência vazias).
    08/11 (#648, CEO 07/11): representativa=True = sem medida exata na fonte; --medidas são só as proporções lidas nas fotos,
    o site não mostra número nem "tamanho real" e avisa no laudo."""
    js, py = MAQUETES / f'{cod}.json', MAQUETES / f'{cod}.py'
    if js.exists() or py.exists():
        raise SystemExit(f'{cod}: já existe maquetes/{cod}.json ou .py — edite o que está lá')
    try:
        L, P, A = (float(x.replace(',', '.')) for x in medidas.lower().split('x'))
    except ValueError:
        raise SystemExit('--medidas no formato LxPxA em cm, ex.: 23x9x10')
    num = lambda v: int(v) if v == int(v) else v  # noqa: E731
    spec = {
        'codigo': cod, 'nome': nome,
        'medidas_cm': {'L': num(L), 'P': num(P), 'A': num(A)},
        'fonte_medidas': fonte,
        'referencia_visual': {'anuncio': anuncio,
                              'situacao': 'A CONFERIR — modelar pela forma das fotos oficiais do anúncio (só referência).'},
        'tipo': tipo,
        'pecas': [{'nome': 'corpo', 'forma': f'molde {tipo} (troque pelas peças reais)', 'medida_cm': f'{num(L)} × {num(P)} × {num(A)}',
                   'material': 'plastico_fosco', 'cor': '#D9D4CE'}],
        'cameras': {'frente': {'az': -32, 'el': 22, 'lente': 70},
                    'lado': {'az': 60, 'el': 14, 'lente': 85},
                    'detalhe': {'az': -20, 'el': 30, 'lente': 100, 'alvo': [0, -num(P) / 2, num(A) * 0.7], 'zoom': 2.2}},
        'referencias': _sugeridas(max(L, P, A), tipo),
        'alt': f'Maquete 3D de {nome}, {num(L)} × {num(P)} × {num(A)} cm',
        'conferida_por': None, 'data': None,
    }
    if representativa:
        spec.update(representativa=True, fonte_medidas=FONTE_REPRESENTATIVA, legenda=LEGENDA_REPRESENTATIVA,
                    alt=f'Maquete 3D representativa de {nome}, feita pelas fotos oficiais')
    if tipo in PARAMETRICOS:
        spec['molde'] = {'nome': tipo, 'cor': '#D9D4CE'}   # troque a cor e ponha os parâmetros do molde
    js.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    py.write_text(CABECALHO.format(cod=cod, nome=nome, L=num(L), P=num(P), A=num(A)) + MOLDES[tipo], encoding='utf-8')
    print(f'{cod}: molde criado em maquetes/{cod}.json e maquetes/{cod}.py — modele as peças e rode '
          f'python ops/gerar-3d.py {cod} --rapido')


def carregar_spec(cod):
    spec = json.loads((MAQUETES / f'{cod}.json').read_text(encoding='utf-8'))
    for campo in ('codigo', 'nome', 'medidas_cm', 'fonte_medidas', 'referencia_visual', 'cameras', 'alt'):
        if campo not in spec:
            raise SystemExit(f'{cod}: maquetes/{cod}.json sem o campo "{campo}"')
    if spec['codigo'] != cod:
        raise SystemExit(f'{cod}: o JSON diz codigo={spec["codigo"]}')
    return spec


def carregar_modelo(cod):
    caminho = MAQUETES / f'{cod}.py'
    mod_spec = importlib.util.spec_from_file_location(f'maquete_{cod}', caminho)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return mod


def tolerancia_cm(medida_cm):
    """1% da medida, entre 1 e 5 mm (mesma regra de ops/maquete3d/estudio.py, sem precisar do Blender)."""
    return max(0.1, min(0.5, medida_cm * 0.01))


def conferir_medidas(cod, spec, medidas):
    alvo = spec['medidas_cm']
    erros = []
    for eixo, valor in zip(('L', 'P', 'A'), medidas):
        if abs(valor - alvo[eixo]) > tolerancia_cm(alvo[eixo]):
            erros.append(f'{eixo} = {valor} cm (anúncio: {alvo[eixo]} cm)')
    if erros:
        raise SystemExit(f'{cod}: a maquete não bate com a medida do anúncio: ' + '; '.join(erros))


def gerar(cod, rapido=False, so_glb=False):
    sys.path.insert(0, str(RAIZ / 'ops'))
    from maquete3d.estudio import Estudio
    spec = carregar_spec(cod)
    modelo = carregar_modelo(cod)
    t0 = time.time()
    e = Estudio(cod)
    modelo.modelar(e, spec)
    medidas = e.medidas_cm()
    if spec.get('conferir_peca'):
        # 31/10 (kit, u09: 5 faixas + bolsinha): a medida do anúncio é de UMA peça; ela é conferida com a mesma tolerância e
        # a foto mostra o kit inteiro (enquadramento pela cena toda)
        import bpy
        nome = spec['conferir_peca']
        if nome.endswith('*'):
            # 31/10 (u10: o osso é feito de várias peças "osso-*"; o mosquetão e os rolos ficam fora da medida)
            todas = e.pecas
            e.pecas = [o for o in todas if o.name.startswith(nome[:-1])]
            lo, hi = e.caixa_envolvente()
            e.pecas = todas
            dims = [(hi[i] - lo[i]) for i in range(3)]
        else:
            dims = list(bpy.data.objects[nome].dimensions)
        medidas = tuple(round(v / 0.01, 2) for v in sorted(dims[:2], reverse=True)) + (round(dims[2] / 0.01, 2),)
    conferir_medidas(cod, spec, medidas)
    lo, hi = e.caixa_envolvente()

    destino = SAIDA / cod
    destino.mkdir(parents=True, exist_ok=True)
    cor_render = None
    if so_glb and (destino / 'maquete.json').is_file():   # só o 3D: as fotos (e a medida de cor) ficam
        cor_render = json.loads((destino / 'maquete.json').read_text(encoding='utf-8')).get('cor_render')
    if not so_glb:
        e.montar_estudio()
        amostras = 24 if rapido else spec.get('amostras', 96)
        escala = 0.5 if rapido else 1.0
        from maquete3d import cor
        mats = e.materiais_por_area()
        mat_corpo, cor_glb = (mats[0][0], mats[0][1]) if mats else (None, None)
        # alvo do corpo: o tom MEDIDO na foto oficial (cor_corpo_foto; produto escuro lê preto com luz, não o hex puro),
        # senão a cor oficial do spec, senão a do .glb
        alvo_cor = spec.get('cor_corpo_foto') or spec.get('cor_corpo') or cor_glb
        if alvo_cor and not spec.get('cor_corpo_foto'):   # produto claro: teto de tom (cor.alvo_foto, CEO 07/11)
            alvo_cor = cor.alvo_foto(alvo_cor)
        escuro = bool(cor_glb) and cor.escuro(cor_glb)
        ctr = cor.contraste(mats, cor_glb) if mats else None    # 30/10: u03 = a alça amarela
        alvo_ctr = (spec.get('cor_contraste_foto') or ctr[1]) if ctr else None
        preenche = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            pngs = {}
            masc, masc_c = Path(tmp) / 'mascara.png', Path(tmp) / 'mascara-contraste.png'
            if mat_corpo is not None:
                # 30/10 (cérebro): a foto sai perto da cor oficial. A luz se acerta numa PROVA pequena da frente
                # (400 × 300, 16 amostras, até 5 vezes) e cada vista sai 1 vez só no tamanho final (a 1ª versão refazia
                # a frente inteira e o final da u06 passou de 25 min). Produto claro: ajusta a exposição. Produto escuro:
                # baixa o preenchimento (fill, topo, ambiente) e mantém key e rim; exposição só como último recurso,
                # até EV_ESCURO_MIN (a u03 com −5,7 virou silhueta chapada e a alça amarela ficou mostarda)
                c = spec['cameras']['frente']
                e.enquadrar(c['az'], c['el'], lente=c.get('lente', 70), alvo=c.get('alvo'),
                            zoom=c.get('zoom', 1.0), folga=c.get('folga', 1.18))
                if escuro:
                    e.sem_veludo(mat_corpo)     # 1º passo do escuro: o veludo do tecido era o véu cinza da u03
                e.render_mascara(masc, mat_corpo)
                if ctr:
                    e.render_mascara(masc_c, ctr[0])
                prova = Path(tmp) / 'prova.png'
                vs = e.cena.view_settings
                for tentativa in range(5):
                    e.render(prova, 400, 300, 16)
                    medido = cor.tom_medio(prova, masc)
                    if medido is None or cor.aceita(alvo_cor, medido) or tentativa == 4:
                        break
                    if not escuro:
                        vs.exposure = cor.proxima_exposicao(vs.exposure, alvo_cor, medido)
                    elif preenche > cor.PREENCHE_MIN or cor.luma(medido) < cor.luma(alvo_cor):
                        preenche = cor.proximo_preenchimento(preenche, alvo_cor, medido)
                        e.preencher(preenche)
                    else:                       # preenchimento no mínimo e ainda claro: um pouco de exposição, com piso
                        vs.exposure = max(cor.EV_ESCURO_MIN, cor.proxima_exposicao(vs.exposure, alvo_cor, medido))
            for vista in VISTAS:
                c = spec['cameras'][vista]
                e.enquadrar(c['az'], c['el'], lente=c.get('lente', 70), alvo=c.get('alvo'),
                            zoom=c.get('zoom', 1.0), folga=c.get('folga', 1.18))
                pngs[vista] = Path(tmp) / f'{vista}.png'
                e.render(pngs[vista], int(1600 * escala), int(1200 * escala), amostras)
                if vista == 'frente' and mat_corpo is not None:
                    medido = cor.tom_medio(pngs[vista], masc)   # a medida que vale é a da foto final
                    cor_render = {'alvo': cor.hexa(alvo_cor), 'foto': cor.hexa(medido) if medido else None,
                                  'diferenca': round(cor.diferenca(alvo_cor, medido), 3) if medido else None,
                                  'exposicao': round(e.cena.view_settings.exposure, 2), 'limite': cor.LIMITE,
                                  'escuro': escuro, 'preenchimento': round(preenche, 3),
                                  'alvo_de': 'foto oficial (cor_corpo_foto)' if spec.get('cor_corpo_foto') else 'cor do material'}
                    if ctr:
                        mc = cor.tom_medio(pngs[vista], masc_c)
                        cor_render['contraste'] = {'alvo': cor.hexa(alvo_ctr), 'foto': cor.hexa(mc) if mc else None,
                                                   'diferenca': round(cor.diferenca(alvo_ctr, mc), 3) if mc else None,
                                                   'limite': cor.LIMITE_CONTRASTE}
                    print(f"{cod}: cor do corpo {cor_render['alvo']} → foto {cor_render['foto']} "
                          f"(diferença {cor_render['diferenca']}, exposição {cor_render['exposicao']}, "
                          f"preenchimento {cor_render['preenchimento']})"
                          + (f"; contraste {cor_render['contraste']['alvo']} → {cor_render['contraste']['foto']} "
                             f"({cor_render['contraste']['diferenca']})" if ctr else ""))
                if not rapido:                    # rascunho não sobrescreve o render guardado
                    guardar_render(cod, vista, pngs[vista])
            compor_vistas(cod, pngs)
    e.exportar_glb(destino / f'{cod}.glb')
    vidro_sem_transmissao(destino / f'{cod}.glb')
    from maquete3d.estudio import exportar_usdz
    exportar_usdz(e, destino / f'{cod}.usdz')

    info = {
        'codigo': cod,
        'nome': spec['nome'],
        'medidas_cm': spec['medidas_cm'],
        'medidas_maquete_cm': dict(zip(('L', 'P', 'A'), medidas)),
        'fonte_medidas': spec['fonte_medidas'],
        # 30/10 (cérebro): a legenda conferida (com as simplificações) mora no spec e sobrevive quando a nuvem regera
        'legenda': spec.get('legenda') or LEGENDA,
        **({'representativa': True} if spec.get('representativa') else {}),   # #648: a régua não afirma tamanho real
        # 30/10 (cérebro): as páginas /loja/ (EN) mostram a legenda e o alt em inglês, se o spec tiver
        **({'legenda_en': spec['legenda_en']} if spec.get('legenda_en') else {}),
        **({'alt_en': spec['alt_en']} if spec.get('alt_en') else {}),
        'alt': spec['alt'],
        'imagens': {v: f'/maquetes/{cod}/{v}.jpg' for v in VISTAS} | {'cartao': f'/maquetes/{cod}/cartao.webp'}
                   | ({'uso': imagem_uso(cod, spec)['uso']} if imagem_uso(cod, spec) else {}),
        **{k: v for k, v in imagem_uso(cod, spec).items() if k != 'uso'},
        'glb': f'/maquetes/{cod}/{cod}.glb',
        'usdz': f'/maquetes/{cod}/{cod}.usdz',
        # objetos de comparação ligados de saída no visualizador (catálogo em public/maquetes/ref/)
        'referencias': spec.get('referencias', ['celular', 'lata']),
        # caixa do produto no sistema do glTF (m, Y para cima, frente em +Z): as linhas de medida
        # da página usam esta caixa
        'caixa_gltf_m': {'min': [round(lo.x, 5), round(lo.z, 5), round(-hi.y, 5)],
                         'max': [round(hi.x, 5), round(hi.z, 5), round(-lo.y, 5)]},
        'cor_render': cor_render,   # tom médio do corpo na foto × cor oficial (maquete3d/cor.py)
        'conferida_por': spec.get('conferida_por'),
        'data': spec.get('data'),
        'rascunho': _rascunho_anterior(destino) if so_glb else bool(rapido),
    }
    (destino / 'maquete.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{cod}: ok em {time.time() - t0:.0f} s · maquete {medidas[0]} × {medidas[1]} × {medidas[2]} cm '
          f'(L × P × A) · {destino.relative_to(RAIZ)}')
    return info


def guardar_render(cod, vista, png):
    """Render transparente (produto + sombra de contato no alfa) em maquetes/renders/<cod>/<vista>.webp:
    trocar o fundo depois é só `--recompor`, sem Blender (tarefa nuvem 07). WebP com alfa sem perda
    no alfa: ~10× menor que o PNG, abaixo de 1 MB (sem Git LFS)."""
    from PIL import Image
    d = RENDERS / cod
    d.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert('RGBA').save(d / f'{vista}.webp', 'WEBP', quality=92, alpha_quality=100, method=6)


def compor_vistas(cod, renders):
    """As fotos do site a partir dos renders transparentes {vista: arquivo}: 3 vistas + cartão da vitrine."""
    sys.path.insert(0, str(RAIZ / 'ops'))
    from maquete3d.composicao import compor
    destino = SAIDA / cod
    for vista, png in renders.items():
        compor(png, destino / f'{vista}.jpg')
        if vista == 'frente':
            compor(png, destino / 'cartao.webp', qualidade=86, tamanho=(800, 800), quadrado=True)


def recompor(cod):
    """Troca o fundo das fotos sem Blender, dos renders guardados (o fundo mora em estudio.FUNDO_HEX)."""
    renders = {v: RENDERS / cod / f'{v}.webp' for v in VISTAS}
    faltam = [str(p.relative_to(RAIZ)) for p in renders.values() if not p.is_file()]
    if faltam:
        raise SystemExit(f'{cod}: sem render guardado ({", ".join(faltam)}) — rode python ops/gerar-3d.py --pronto {cod}')
    compor_vistas(cod, renders)
    print(f'{cod}: fotos recompostas no fundo novo')


def _glb_ler(caminho):
    dados = Path(caminho).read_bytes()
    tam, = struct.unpack_from('<I', dados, 12)
    return json.loads(dados[20:20 + tam]), dados[20 + tam:]


def vidro_sem_transmissao(caminho, opacidade=0.35):
    """Vidro do .glb sem transmissão: o visualizador da página desenhava o vidro (KHR_materials_transmission)
    PRETO (c14, CEO 02/10). Vira transparência simples: alphaMode BLEND, cor clara, opacidade ~0,35,
    dupla face. O render de estúdio continua com o vidro de verdade (só o .glb muda)."""
    gltf, resto = _glb_ler(caminho)
    mudou = False
    for m in gltf.get('materials', []):
        ext = m.get('extensions', {})
        if 'KHR_materials_transmission' not in ext:
            continue
        for k in ('KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_ior'):
            ext.pop(k, None)
        if not ext:
            m.pop('extensions', None)
        pbr = m.setdefault('pbrMetallicRoughness', {})
        cor = pbr.get('baseColorFactor', [1, 1, 1, 1])
        pbr['baseColorFactor'] = [*cor[:3], opacidade]
        pbr['metallicFactor'] = 0.0
        pbr['roughnessFactor'] = min(pbr.get('roughnessFactor', 0.05), 0.1)
        m['alphaMode'] = 'BLEND'
        m['doubleSided'] = True
        mudou = True
    if not mudou:
        return False
    usados = {k for m in gltf.get('materials', []) for k in m.get('extensions', {})}
    for chave in ('extensionsUsed', 'extensionsRequired'):
        if chave in gltf:
            gltf[chave] = [x for x in gltf[chave] if not x.startswith('KHR_materials_') or x in usados]
            if not gltf[chave]:
                del gltf[chave]
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    total = 12 + 8 + len(js) + len(resto)
    Path(caminho).write_bytes(struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(js), b'JSON') + js + resto)
    return True


def pausada(cod):
    """30/10 (CEO): produto pausado ("pausado" em maquetes/<cod>.json) sai do índice do visualizador; a pasta fica."""
    try:
        return bool(json.loads((MAQUETES / f'{cod}.json').read_text(encoding='utf-8')).get('pausado'))
    except (OSError, ValueError):
        return False


def imagem_uso(cod, spec):
    """01/11 (CEO): todo produto novo ganha 1 imagem de USO REAL (molde "cena de uso", ops/maquete3d/cena_uso.py).
    Entra no maquete.json só quando a cena foi aprovada (`cena_uso.aprovada` no spec) e a foto existe."""
    c = spec.get('cena_uso') or {}
    foto = c.get('foto_site', 'uso-1')
    if not c.get('aprovada') or not (SAIDA / cod / f'{foto}.jpg').is_file():
        return {}
    return {'uso': f'/maquetes/{cod}/{foto}.jpg', 'alt_uso': c.get('alt_uso') or spec['alt'],
            **({'alt_uso_en': c['alt_uso_en']} if c.get('alt_uso_en') else {})}


def atualizar_textos(cod):
    """30/10: copia legenda/alt (PT) e legenda_en/alt_en do spec para public/maquetes/<cod>/maquete.json, sem refazer
    o render (as fotos e a assinatura do cérebro ficam)."""
    spec, arq = carregar_spec(cod), SAIDA / cod / 'maquete.json'
    info = json.loads(arq.read_text(encoding='utf-8'))
    for k in ('legenda', 'alt', 'legenda_en', 'alt_en'):
        if spec.get(k):
            info[k] = spec[k]
    uso = imagem_uso(cod, spec)                 # 01/11: a imagem de uso real (cena de uso aprovada pelo CEO)
    if uso:
        info.setdefault('imagens', {})['uso'] = uso.pop('uso')
        info.update(uso)
    arq.write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{cod}: textos do spec copiados para o maquete.json')


def gravar_indice():
    """public/maquetes/index.json: os produtos com maquete, para o visualizador (sem lista fixa na página)."""
    cods = sorted(p.parent.name for p in SAIDA.glob('*/maquete.json') if not pausada(p.parent.name))
    (SAIDA / 'index.json').write_text(json.dumps({'produtos': cods}, ensure_ascii=False) + '\n', encoding='utf-8')
    return cods


def _rascunho_anterior(destino):
    """Rascunho = fotos em meia resolução (--rapido). Lido da própria foto, que é a verdade; sem Pillow, do JSON."""
    try:
        from PIL import Image
        return Image.open(destino / 'frente.jpg').size[0] < 1600
    except ImportError:
        pass
    except OSError:
        return True
    try:
        return json.loads((destino / 'maquete.json').read_text(encoding='utf-8')).get('rascunho', True)
    except (OSError, ValueError):
        return True


# ─────────────── conferência sem Blender (usada pelos testes do site) ───────────────

def _vertices(dados, gltf, ac, tam_json):
    """Vértices reais (x, y, z) de um accessor de posição do .glb, ou None se não der para ler (então vale a
    caixa min/max). Peça inclinada (u60, 18/11): os 8 cantos da caixa do accessor, girados, inflam a medida
    (A 2.9 em vez dos 2.65 que o Blender mediu); os vértices dão a medida certa."""
    try:
        if ac.get('componentType') != 5126 or ac.get('type') != 'VEC3' or ac.get('sparse') or 'bufferView' not in ac:
            return None
        vista = gltf['bufferViews'][ac['bufferView']]
        ini_bin = 20 + tam_json
        ini_bin += (-ini_bin) % 4
        _tam_bin, tipo_bin = struct.unpack_from('<I4s', dados, ini_bin)
        if tipo_bin != b'BIN\x00' or gltf['buffers'][vista.get('buffer', 0)].get('uri'):
            return None
        base = ini_bin + 8 + vista.get('byteOffset', 0) + ac.get('byteOffset', 0)
        passo = vista.get('byteStride') or 12
        return [struct.unpack_from('<3f', dados, base + i * passo) for i in range(ac['count'])]
    except Exception:
        return None


def glb_caixa_m(caminho, so_no=None, exato=False):
    """Caixa envolvente (m) do .glb, lida dos min/max dos acessores de posição (sem Blender).
    Devolve (largura X, altura Y, profundidade Z) no sistema do glTF (Y para cima).
    so_no (31/10, kit u09): só o nó com esse nome (e os filhos dele) entra na caixa.
    exato (u60, 18/11): mede pelos vértices, não pelos cantos da caixa de cada malha (peça inclinada)."""
    dados = Path(caminho).read_bytes()
    magico, _versao, _total = struct.unpack_from('<4sII', dados, 0)
    if magico != b'glTF':
        raise ValueError(f'{caminho}: não é GLB')
    tam, tipo = struct.unpack_from('<I4s', dados, 12)
    if tipo != b'JSON':
        raise ValueError(f'{caminho}: primeiro bloco não é JSON')
    gltf = json.loads(dados[20:20 + tam])

    # matrizes 4 × 4 em listas (sem numpy: roda no CI e no PC sem instalar nada)
    def mult(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    def matriz(no):
        if 'matrix' in no:
            m = no['matrix']                      # glTF guarda por coluna
            return [[m[j * 4 + i] for j in range(4)] for i in range(4)]
        x, y, z, w = no.get('rotation', [0, 0, 0, 1])
        sx, sy, sz = no.get('scale', [1, 1, 1])
        tx, ty, tz = no.get('translation', [0, 0, 0])
        r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
             [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
             [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
                [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
                [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
                [0, 0, 0, 1]]

    identidade = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    lo, hi = [1e9] * 3, [-1e9] * 3

    def visitar(i, pai, dentro):
        no = gltf['nodes'][i]
        m = mult(pai, matriz(no))
        nome = no.get('name') or ''
        dentro = dentro or (nome.startswith(so_no[:-1]) if so_no and so_no.endswith('*') else nome == so_no)
        if 'mesh' in no and dentro:
            for prim in gltf['meshes'][no['mesh']]['primitives']:
                ac = gltf['accessors'][prim['attributes']['POSITION']]
                a, b = ac['min'], ac['max']
                pontos = _vertices(dados, gltf, ac, tam) if exato else None
                if pontos is None:   # sem ler os vértices: os 8 cantos da caixa do accessor
                    pontos = [(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])]
                for x, y, z in pontos:
                    for k in range(3):
                        v = m[k][0] * x + m[k][1] * y + m[k][2] * z + m[k][3]
                        lo[k], hi[k] = min(lo[k], v), max(hi[k], v)
        for f in no.get('children', []):
            visitar(f, m, dentro)

    for i in gltf['scenes'][gltf.get('scene', 0)]['nodes']:
        visitar(i, identidade, so_no is None)
    if hi[0] < lo[0]:
        raise ValueError(f'{caminho}: o nó {so_no!r} não está no .glb')
    return tuple(hi[k] - lo[k] for k in range(3))


_COMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}


def glb_estrutura(caminho):
    """Os erros estruturais que o KhronosGroup/glTF-Validator pega e o visor do site só mostra quebrado
    (polimento do GitHub, 23/10; sem instalar nada): cabeçalho, blocos, limites de buffer/bufferView/accessor
    e índices que apontam para o nada. Devolve lista de erros (vazia = ok)."""
    nome, erros = Path(caminho).name, []
    dados = Path(caminho).read_bytes()
    magico, versao, total = struct.unpack_from('<4sII', dados, 0)
    if magico != b'glTF' or versao != 2:
        return [f'{nome}: cabeçalho não é GLB 2.0']
    if total != len(dados):
        erros.append(f'{nome}: cabeçalho diz {total} bytes, o arquivo tem {len(dados)}')
    tam, tipo = struct.unpack_from('<I4s', dados, 12)
    if tipo != b'JSON' or tam % 4:
        erros.append(f'{nome}: bloco JSON fora do padrão (tipo/alinhamento de 4 bytes)')
    gltf = json.loads(dados[20:20 + tam])
    bin_tam = 0
    if len(dados) > 20 + tam:
        bin_tam, bin_tipo = struct.unpack_from('<I4s', dados, 20 + tam)
        if bin_tipo != b'BIN\x00' or 28 + tam + bin_tam > len(dados):
            erros.append(f'{nome}: bloco BIN inválido ou cortado')
    if gltf.get('asset', {}).get('version') != '2.0':
        erros.append(f'{nome}: asset.version não é "2.0"')
    falta_ext = set(gltf.get('extensionsRequired', [])) - set(gltf.get('extensionsUsed', []))
    if falta_ext:
        erros.append(f'{nome}: extensionsRequired fora de extensionsUsed: {sorted(falta_ext)}')
    buffers, vistas = gltf.get('buffers', []), gltf.get('bufferViews', [])
    for i, b in enumerate(buffers):
        if 'uri' not in b and b.get('byteLength', 0) > bin_tam:
            erros.append(f'{nome}: buffer {i} ({b.get("byteLength")} B) maior que o bloco BIN ({bin_tam} B)')
    for i, v in enumerate(vistas):
        b = v.get('buffer', -1)
        if not 0 <= b < len(buffers):
            erros.append(f'{nome}: bufferView {i} aponta para buffer {b} inexistente')
        elif v.get('byteOffset', 0) + v.get('byteLength', 0) > buffers[b].get('byteLength', 0):
            erros.append(f'{nome}: bufferView {i} passa do fim do buffer {b}')
    for i, a in enumerate(gltf.get('accessors', [])):
        if 'bufferView' not in a:
            continue
        v = a['bufferView']
        if not 0 <= v < len(vistas):
            erros.append(f'{nome}: accessor {i} aponta para bufferView {v} inexistente')
            continue
        elem = _COMP.get(a.get('type'), 0) * _BYTES.get(a.get('componentType'), 0)
        passo = vistas[v].get('byteStride', elem)
        fim = a.get('byteOffset', 0) + (a.get('count', 0) - 1) * passo + elem if a.get('count') else 0
        if not elem or fim > vistas[v].get('byteLength', 0):
            erros.append(f'{nome}: accessor {i} passa do fim da bufferView {v} (ou tipo inválido)')
    n_acc, n_mat = len(gltf.get('accessors', [])), len(gltf.get('materials', []))
    for m, malha in enumerate(gltf.get('meshes', [])):
        for p in malha.get('primitives', []):
            idx = list(p.get('attributes', {}).values()) + ([p['indices']] if 'indices' in p else [])
            if any(not 0 <= x < n_acc for x in idx) or not 0 <= p.get('material', 0) < max(n_mat, 1):
                erros.append(f'{nome}: malha {m} com accessor/material inexistente')
    n_img, n_tex = len(gltf.get('images', [])), len(gltf.get('textures', []))
    if any(not 0 <= t.get('source', 0) < max(n_img, 1) for t in gltf.get('textures', [])):
        erros.append(f'{nome}: textura aponta para imagem inexistente')
    for m, mat in enumerate(gltf.get('materials', [])):
        refs = re.findall(r'"index":\s*(\d+)', json.dumps(mat))
        if any(int(x) >= n_tex for x in refs):
            erros.append(f'{nome}: material {m} usa textura inexistente')
    return erros


def conferir(cod, cor_foto=False):
    """Confere o que já foi gerado: arquivos, tamanhos e medidas do .glb. Devolve lista de erros."""
    erros = []
    spec = carregar_spec(cod)
    d = SAIDA / cod
    for nome in [f'{v}.jpg' for v in VISTAS] + ['cartao.webp', f'{cod}.glb', f'{cod}.usdz', 'maquete.json']:
        if not (d / nome).is_file() or (d / nome).stat().st_size == 0:
            erros.append(f'{cod}: falta public/maquetes/{cod}/{nome}')
    if erros:
        return erros
    erros += [f'{cod}: {x}' for x in glb_estrutura(d / f'{cod}.glb')]
    alvo = spec['medidas_cm']
    medidas = []   # a caixa dos cantos (padrão) e a dos vértices (peça inclinada, u60): vale o eixo que bater em qualquer uma
    for exato in (False, True):
        x, y, z = glb_caixa_m(d / f'{cod}.glb', spec.get('conferir_peca'), exato)   # glTF: X largura, Y altura, Z profundidade
        if spec.get('conferir_peca'):   # kit (u09): a medida do anúncio é de 1 peça, deitada; mesma regra do gerar (L ≥ P)
            x, z = sorted((x, z), reverse=True)
        medidas.append({'L': x, 'A': y, 'P': z})
    for eixo in ('L', 'A', 'P'):
        if all(abs(m[eixo] * 100 - alvo[eixo]) > tolerancia_cm(alvo[eixo]) for m in medidas):
            erros.append(f'{cod}: .glb com {eixo} = {medidas[0][eixo] * 100:.1f} cm (anúncio: {alvo[eixo]} cm)')
    # cor da foto (cérebro 30/10): só no --conferir e no pronto; a validação do site (testar-site.py) não trava
    # a publicação por tom de foto de produto que já está no ar — decisão do cérebro se isso deve travar
    cr = json.loads((d / 'maquete.json').read_text(encoding='utf-8')).get('cor_render') if cor_foto else None
    if cor_foto and not cr and (RENDERS / cod / 'frente.webp').is_file():   # 30/10 (cérebro): sem cor_render, mede aqui
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d import cor
        cr = cor.medir_sem_mascara(d / f'{cod}.glb', RENDERS / cod / 'frente.webp')
    if cor_foto and cr and cr.get('foto') and spec.get('cor_corpo_foto') and cr.get('alvo') != spec['cor_corpo_foto']:
        # 31/10 (u09, conector): o alvo guardado no render ficou velho (a ficha trocou o cor_corpo_foto depois): a foto
        # medida é comparada com o alvo ATUAL da ficha
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d import cor
        cr = dict(cr, alvo=spec['cor_corpo_foto'], diferenca=round(cor.diferenca(spec['cor_corpo_foto'], cr['foto']), 3))
    if cr and cr.get('diferenca') is not None and cr['diferenca'] > cr.get('limite', 0.15):   # 30/10 (cérebro)
        erros.append(f"{cod}: foto com o corpo {cr['foto']} longe da cor oficial {cr['alvo']} "
                     f"(diferença {cr['diferenca']:.0%} > {cr.get('limite', 0.15):.0%}): ajuste a luz/material")
    if cor_foto and cr and spec.get('cor_corpo_foto') and cr.get('foto'):
        # o alvo do corpo mudou para o tom da foto oficial (produto escuro): a foto no disco é medida contra ele
        sys.path.insert(0, str(RAIZ / 'ops'))   # 31/10: sem isto o import quebrava quando nenhum ramo acima tinha posto o caminho
        from maquete3d import cor
        if cor.diferenca(spec['cor_corpo_foto'], cr['foto']) > cr.get('limite', 0.15):
            erros.append(f"{cod}: foto com o corpo {cr['foto']} longe do tom da foto oficial {spec['cor_corpo_foto']} "
                         f"(diferença {cor.diferenca(spec['cor_corpo_foto'], cr['foto']):.0%}): ajuste a luz")
    ct = (cr or {}).get('contraste') or {}
    if cor_foto and not ct and (RENDERS / cod / 'frente.webp').is_file():   # foto feita antes da régua 2.0
        from maquete3d import cor
        ct = cor.medir_contraste_sem_mascara(d / f'{cod}.glb', RENDERS / cod / 'frente.webp',
                                             spec.get('cor_contraste_foto')) or {}
    if ct.get('foto') and spec.get('cor_contraste_foto') and ct.get('alvo') != spec['cor_contraste_foto']:
        # 11/11 (#744, p40): mesmo caso do corpo da u09 — a ficha ganhou o tom medido na foto oficial depois do render;
        # a foto no disco é medida contra o alvo novo (sem refazer o render)
        from maquete3d import cor
        ct = dict(ct, alvo=spec['cor_contraste_foto'], diferenca=round(cor.diferenca(spec['cor_contraste_foto'], ct['foto']), 3))
    if ct.get('diferenca') is not None and ct['diferenca'] > ct.get('limite', 0.25) and spec.get('contraste_aceito') \
            and spec.get('conferida_por'):
        # 15/11 (#1080, u45): peça fina (arame da grelha) sobre fundo escuro — a máscara mede o fundo entre os fios.
        # Só o cérebro, que conferiu lado a lado (conferida_por), aceita com o motivo; vira aviso (L6: só outro objeto reprova)
        print(f"AVISO {cod}: contraste {ct['foto']} × {ct['alvo']} ({ct['diferenca']:.0%}) aceito: {spec['contraste_aceito']}")
    elif ct.get('diferenca') is not None and ct['diferenca'] > ct.get('limite', 0.25):   # 30/10: a alça da u03
        erros.append(f"{cod}: foto com o contraste {ct['foto']} longe da cor oficial {ct['alvo']} "
                     f"(diferença {ct['diferenca']:.0%} > {ct.get('limite', 0.25):.0%}): a luz apagou a peça de contraste")
    rascunho = _rascunho_anterior(d)
    tam = (800, 600) if rascunho else (1600, 1200)     # rascunho (--rapido) sai em meia resolução
    try:
        from PIL import Image
        for v in VISTAS:
            if Image.open(d / f'{v}.jpg').size != tam:
                erros.append(f'{cod}: {v}.jpg não tem {tam[0]}×{tam[1]}')
        if Image.open(d / 'cartao.webp').size != (800, 800):
            erros.append(f'{cod}: cartao.webp não tem 800×800')
        uso = json.loads((d / 'maquete.json').read_text(encoding='utf-8')).get('imagens', {}).get('uso')
        if uso:                                  # 01/11: a imagem de uso real, se publicada, existe e é 1600 × 1200
            arq = SAIDA / cod / Path(uso).name
            if not arq.is_file():
                erros.append(f'{cod}: maquete.json aponta a imagem de uso {uso}, mas o arquivo não existe')
            elif Image.open(arq).size != (1600, 1200):
                erros.append(f'{cod}: {arq.name} não tem 1600×1200')
    except ImportError:
        pass
    return erros


def pronto(cod, rapido=False):
    """O fluxo padrão Tavrov de um produto, do render à prévia, com o que falta no fim."""
    import subprocess
    print(f'── {cod}: 1/4 maquete (render de estúdio, 3D, realidade aumentada)')
    gerar(cod, rapido=rapido)
    cods = gravar_indice()
    print(f'── {cod}: 2/4 conferência (arquivos e medidas do 3D)')
    erros = conferir(cod, cor_foto=True)
    for x in erros:
        print('   ERRO', x)
    if erros:
        raise SystemExit(f'{cod}: a maquete não passou na conferência — corrija e rode de novo')
    print(f'── {cod}: 3/4 site (cartão com a maquete + página do produto com o 3D)')
    r = subprocess.run([sys.executable, str(RAIZ / 'ops' / 'gerar-produtos.py')], capture_output=True, text=True)
    no_site = f'/maquetes/{cod}/cartao.webp' in (RAIZ / 'public' / 'produtos.json').read_text(encoding='utf-8')
    print('   ' + (r.stdout.strip().splitlines() or ['(sem saída)'])[-1])
    print(f'── {cod}: 4/4 prévia para aprovação')
    sys.path.insert(0, str(RAIZ / 'ops'))
    from maquete3d.previa import montar
    montar(RAIZ, cods)
    spec = carregar_spec(cod)
    print(f"""
{cod} pronto no padrão Tavrov. Falta:
  [ ] olhar as 3 fotos: public/maquetes/{cod}/frente.jpg · lado.jpg · detalhe.jpg{'  (RASCUNHO: rode sem --rapido)' if rapido else ''}
  [ ] publicar a prévia (ops/logs/previa-3d/) e o CEO aprovar
  [ ] gerente geral comparar com o anúncio e preencher conferida_por e data em maquetes/{cod}.json
  [ ] cena de uso (padrão CEO 01/11): 1 imagem do produto em uso real — molde em maquetes/LEIA-ME.md, seção "Cena de uso"
  [ ] {'o produto já está no site: o cartão e a página dele usam a maquete' if no_site else 'o produto ainda não está no produtos.json (entra quando passar na peneira: pesquisa + laudo + link)'}
  [ ] commit: maquetes/{cod}.json · maquetes/{cod}.py · public/maquetes/{cod}/ · public/maquetes/index.json{' · páginas do site' if no_site else ''}
  medidas: {spec['medidas_cm']['L']} × {spec['medidas_cm']['P']} × {spec['medidas_cm']['A']} cm · fonte: {spec['fonte_medidas'][:90]}""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('codigos', nargs='*')
    ap.add_argument('--todos', action='store_true')
    ap.add_argument('--rapido', action='store_true')
    ap.add_argument('--conferir', action='store_true')
    ap.add_argument('--so-glb', action='store_true', help='só refaz os .glb e o maquete.json (sem render)')
    ap.add_argument('--recompor', action='store_true',
                    help='troca o fundo das fotos sem Blender, dos renders guardados em maquetes/renders/')
    ap.add_argument('--pronto', metavar='COD', help='o fluxo inteiro de um produto: maquete, conferência, site e prévia')
    ap.add_argument('--novo', metavar='COD', help='cria o molde de uma maquete nova')
    ap.add_argument('--previa', action='store_true',
                    help='monta a cópia do visualizador para o link de prévia (claude.ai) em ops/logs/previa-3d/')
    ap.add_argument('--arquivo', action='store_true',
                    help='um .html só (3D, fotos e three.js dentro) para mandar por WhatsApp — em ops/logs/arquivo-3d/')
    ap.add_argument('--textos', action='store_true',
                    help='só copia legenda/alt (PT e EN) do spec para o maquete.json publicado (sem Blender)')
    ap.add_argument('--referencias-en', action='store_true',
                    help='catálogo EN da régua (referencias-en.json + o quarter moeda-us.glb), sem Blender')
    ap.add_argument('--referencias', action='store_true',
                    help='gera os objetos de comparação (celular, lata, garrafa...) em public/maquetes/ref/')
    ap.add_argument('--nome')
    ap.add_argument('--medidas', help='LxPxA em cm, ex.: 23x9x10')
    ap.add_argument('--fonte', help='de onde vem a medida (anúncio + data)')
    ap.add_argument('--representativa', action='store_true',
                    help='sem medida exata na fonte: --medidas = proporções das fotos; o site avisa e não mostra número (CEO 07/11)')
    ap.add_argument('--anuncio', help='link do anúncio usado como referência de forma')
    ap.add_argument('--tipo', choices=sorted(MOLDES), default='caixa',
                    help='molde de partida: caixa, cilindro, torneado (garrafa, copo, vaso), chapa (organizador p07), '
                         'cubo (p16), almofada (p08)')
    a = ap.parse_args()
    if a.pronto:
        pronto(a.pronto, rapido=a.rapido)
        return
    if a.arquivo:
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d.previa import montar_arquivo_unico
        montar_arquivo_unico(RAIZ, a.codigos or gravar_indice())
        return
    if a.previa:
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d.previa import montar
        montar(RAIZ, a.codigos or gravar_indice())
        return
    if a.referencias_en:
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d.referencias import gerar_en
        print('referencias-en:', ', '.join(gerar_en(SAIDA / 'ref')))
        return
    if a.textos:
        for c in (a.codigos or []):
            atualizar_textos(c)
        return
    if a.referencias:
        sys.path.insert(0, str(RAIZ / 'ops'))
        from maquete3d.referencias import gerar_todas
        gerar_todas(SAIDA / 'ref')
        return
    if a.novo:
        faltam = [f'--{k}' for k in ('nome', 'medidas', 'fonte', 'anuncio') if not getattr(a, k)]
        if faltam:
            ap.error('--novo precisa de ' + ', '.join(faltam))
        novo(a.novo, a.nome, a.medidas, a.fonte, a.anuncio, a.tipo, a.representativa)
        return
    cods = sorted(p.stem for p in MAQUETES.glob('*.json')) if a.todos or not a.codigos else a.codigos
    if a.conferir:
        erros = [x for c in cods for x in conferir(c, cor_foto=True)]
        for x in erros:
            print('ERRO', x)
        print('maquetes conferidas:', ', '.join(cods), '·', 'TUDO OK' if not erros else f'{len(erros)} erro(s)')
        sys.exit(1 if erros else 0)
    if a.recompor:
        for c in cods:
            recompor(c)
        return
    for c in cods:
        gerar(c, rapido=a.rapido, so_glb=a.so_glb)
    print('visualizador: public/maquetes/ver.html —', ', '.join(gravar_indice()))


if __name__ == '__main__':
    main()
