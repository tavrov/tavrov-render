"""u11 · Magnetic Cable Clips, 6 Pack — cada clipe 2 × 2 × 1,5 cm (L × P × A, descrição da CJ, 31/10).

Forma pela descrição das fotos oficiais da CJ (a rede da nuvem não abriu as fotos): clipe de plástico preto, base
quadrada de cantos arredondados com fita adesiva embaixo; tampa superior articulada atrás, que fecha sozinha pelo ímã;
o cabo passa por um canal redondo que atravessa o clipe da esquerda para a direita, perto da frente. Sem logotipo.
Kit: 6 clipes em 2 fileiras de 3; 2 deles com a tampa aberta (mostra o canal e o ímã). A medida conferida é a do
clipe c1 (fechado): conferir_peca "c1-*".
Eixos: X = largura, Y = profundidade (frente em -Y), Z = altura; apoiado em z = 0; tudo em cm.
"""
import math

PRETO = '#161618'        # o estúdio clareia o preto (lição da u09): material um pouco mais escuro
FITA = '#D8D4CA'         # espuma adesiva clara embaixo
IMA = '#9EA3A8'
FITA_A = 0.08            # espessura da fita adesiva
CANAL_D = 0.62           # diâmetro do canal do cabo
CANAL_Y = -0.22          # canal perto da frente
RAIO = 0.28


def _rot_x(v, graus):
    a = math.radians(graus)
    x, y, z = v
    return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def _clipe(e, n, cx, cy, L, P, A, mats, aberto=0.0):
    plast, fita, ima = mats
    corte = A / 2                                  # a tampa encosta na base no meio da altura
    e.caixa(f'c{n}-fita', L - 0.12, P - 0.12, FITA_A, pos=(cx, cy, FITA_A / 2), mat=fita, raio=0.03)
    # base e tampa saem do mesmo bloco arredondado (2 × 2 × A), cortado no meio: a junta fica fina, como no clipe real
    zb = FITA_A + (A - FITA_A) / 2
    base = e.caixa(f'c{n}-base', L, P, A - FITA_A, pos=(cx, cy, zb), mat=plast, raio=RAIO)
    cima = e.caixa(f'c{n}-corte-b', L * 3, P * 3, A * 2, pos=(cx, cy, corte + A), aux=True)
    e.furar(base, cima, depois_do_bevel=True)
    c = e.cilindro(f'c{n}-canal-b', CANAL_D, L * 2, pos=(cx, cy + CANAL_Y, corte), rot=(0, 90, 0), aux=True)
    e.furar(base, c, depois_do_bevel=True)
    # ímã redondo embutido no topo da base, atrás do canal
    e.cilindro(f'c{n}-ima', 0.46, 0.04, pos=(cx, cy + 0.5, corte - 0.015), mat=ima, raio=0.01)
    # tampa: o mesmo bloco, a metade de cima, girada em torno da dobradiça (aresta de trás, no corte)
    h = (cx, cy + P / 2, corte)

    def girado(rel):
        r = _rot_x(rel, -aberto)
        return (h[0] + r[0], h[1] + r[1], h[2] + r[2])

    tampa = e.caixa(f'c{n}-tampa', L, P, A - FITA_A, pos=girado((0, -P / 2, zb - corte)), rot=(-aberto, 0, 0),
                    mat=plast, raio=RAIO)
    baixo = e.caixa(f'c{n}-corte-t', L * 3, P * 3, A * 2, pos=girado((0, -P / 2, -A)), rot=(-aberto, 0, 0), aux=True)
    e.furar(tampa, baixo, depois_do_bevel=True)
    ct = e.cilindro(f'c{n}-canal-t', CANAL_D, L * 2, pos=girado((0, CANAL_Y - P / 2, 0)), rot=(0, 90, 0), aux=True)
    e.furar(tampa, ct, depois_do_bevel=True)
    # dobradiça: pino fino na aresta de trás (dentro da medida)
    e.cilindro(f'c{n}-dobradica', 0.14, L * 0.7, pos=(h[0], h[1] - 0.09, h[2]), rot=(0, 90, 0), mat=plast, raio=0.02)


def modelar(e, spec):
    m = spec['medidas_cm']
    L, P, A = m['L'], m['P'], m['A']
    plast = e.mat('plastico_fosco', PRETO)
    e.sem_veludo(plast)
    mats = (plast, e.mat('plastico_fosco', FITA), e.mat('metal_pintado', IMA))
    dx, dy = L + 1.0, P + 1.6
    pos = [(-dx, -dy / 2, 0), (0, -dy / 2, 0), (dx, -dy / 2, 70),
           (-dx, dy / 2, 0), (0, dy / 2, 75), (dx, dy / 2, 0)]
    # c1 = o clipe conferido (fechado, frente à esquerda)
    for n, (x, y, ab) in enumerate(pos, start=1):
        _clipe(e, n, x, y, L, P, A, mats, aberto=ab)
