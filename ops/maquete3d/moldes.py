"""Moldes paramétricos de maquete (CEO 04/10: volume com qualidade e cada maquete mais barata).

Produto novo de forma comum = MOLDE + PARÂMETROS no `maquetes/<cod>.json`, sem modelar à mão:

    "molde": {"nome": "pote", "cor": "#FFFFFF", "material": "vidro", "cor_tampa": "#E8ECEF",
              "redondo": false, "travas": 4, "cor_trava": "#6B7A8F"}

e o `maquetes/<cod>.py` fica em 2 linhas (ou nem existe: o gerar-3d usa o molde do JSON):

    from maquete3d.moldes import modelar_por_molde as modelar

Cada molde fecha a caixa envolvente EXATA em L × P × A (`medidas_cm` do JSON), apoiado em z = 0,
frente para −Y, com as peças, materiais e bevels do estúdio padrão (`estudio.py`). Modelagem à mão
(`maquetes/<cod>.py` próprio) só quando nenhum molde serve — e o que der certo nela vira molde aqui.

| molde | para | parâmetros (além de cor/material) |
|---|---|---|
| `caixa_organizadora` | caixa, cesto, gaveta, organizador aberto ou com tampa | parede, raio, cor_tampa, divisorias, alcas, cor_alca |
| `pote` | pote/recipiente com tampa (redondo ou retangular), marmita, porta-mantimento | redondo, altura_tampa, cor_tampa, travas, cor_trava, vedacao |
| `garrafa` | garrafa, squeeze, frasco, garrafa térmica, copo com tampa (cilindro) | d_gargalo, ombro, altura_tampa, cor_tampa, alca |
| `utensilio` | espátula, colher, pegador, faca de servir, escova — peça plana com cabo | cabeca (espatula/colher/escova), frac_cabo, cor_cabo, material_cabo |
| `tapete` | tapete, placa, escorredor, jogo americano, capacho | raio, borda, cor_borda, nervuras, listras (lista de cores) |
| `eletronico` | balança, rádio, caixa de som, controle, carregador, luminária de mesa quadrada | tela (L, A em fração), cor_tela, face_tela, botoes, cor_botao, pes |
"""

MOLDES_DOC = __doc__

import bpy  # noqa: E402  (o estúdio já importou; aqui só para apagar peça refeita)


def _medidas(spec):
    m = spec['medidas_cm']
    return float(m['L']), float(m['P']), float(m['A'])


def _vidro_sem_sombra(*obs):
    """vidro/transparente não faz sombra chapada (lição do c14: o Cycles escurece o que está dentro)."""
    for ob in obs:
        ob.visible_shadow = False


def _eh_transparente(material):
    return material in ('vidro', 'plastico_transparente')


# ───────────────────────── caixa organizadora ─────────────────────────

def caixa_organizadora(e, L, P, A, cor='#E9E6E1', material='plastico_fosco', parede=0.3, raio=1.0,
                       cor_tampa=None, material_tampa=None, altura_tampa=1.2, divisorias=0, alcas=False,
                       cor_alca=None):
    """Caixa aberta (ou com tampa, se `cor_tampa`) de parede `parede`, cantos de `raio`; `divisorias`
    paredes internas ao longo de X; `alcas` = recorte de pega nas laterais esquerda e direita."""
    m = e.mat(material, cor)
    alt_corpo = A - (altura_tampa if cor_tampa else 0.0)
    # caixa aberta: o bevel do topo rebaixa a borda da parede fina; o corpo nasce mais alto pelo
    # quanto a borda desce (medido) e fica exatamente em A
    h = 0.0
    for _ in range(3):
        corpo = e.caixa('corpo', L, P, alt_corpo + h, pos=(0, 0, (alt_corpo + h) / 2), mat=m, raio=raio, segmentos=5)
        oco = e.caixa('corpo-oco', L - 2 * parede, P - 2 * parede, alt_corpo + h,
                      pos=(0, 0, (alt_corpo + h) / 2 + parede), aux=True, arredondar=True, raio=max(0.1, raio - parede))
        e.furar(corpo, oco, depois_do_bevel=True)
        falta = alt_corpo - e.caixa_envolvente()[1].z / 0.01
        if cor_tampa or abs(falta) < 0.03:
            break
        e.pecas.remove(corpo)
        bpy.data.objects.remove(corpo)
        bpy.data.objects.remove(oco)
        h += falta
    if _eh_transparente(material):
        _vidro_sem_sombra(corpo)
    if alcas:
        for lado in (-1, 1):
            pega = e.caixa(f'pega{lado}', parede * 4, min(P * 0.4, 9.0), min(alt_corpo * 0.18, 2.2),
                           pos=(lado * L / 2, 0, alt_corpo * 0.82), aux=True, arredondar=True, raio=0.5)
            e.furar(corpo, pega, depois_do_bevel=True)
    for i in range(divisorias):
        x = -L / 2 + L * (i + 1) / (divisorias + 1)
        e.caixa(f'divisoria{i}', parede, P - 2 * parede, alt_corpo * 0.85 - parede,
                pos=(x, 0, parede + (alt_corpo * 0.85 - parede) / 2), mat=m, raio=0.08)
    if cor_tampa:
        mt = e.mat(material_tampa or material, cor_tampa)
        tampa = e.caixa('tampa', L, P, altura_tampa, pos=(0, 0, A - altura_tampa / 2), mat=mt, raio=min(raio, altura_tampa / 2.1),
                        segmentos=5)
        reb = e.caixa('tampa-rebaixo', L - 3.0, P - 3.0, 0.4, pos=(0, 0, A), aux=True, arredondar=True, raio=max(0.2, raio - 0.5))
        e.furar(tampa, reb, depois_do_bevel=True)
        if alcas and cor_alca:
            # trava de alça sobre a junta tampa/corpo, nas laterais (dentro de L)
            ma = e.mat('plastico_fosco', cor_alca)
            for lado in (-1, 1):
                e.caixa(f'trava{lado}', 0.25, min(P * 0.35, 8.0), altura_tampa + 1.6,
                        pos=(lado * (L / 2 - 0.125), 0, A - (altura_tampa + 1.6) / 2), mat=ma, raio=0.08)
        if _eh_transparente(material_tampa or material):
            _vidro_sem_sombra(tampa)


# ───────────────────────── pote com tampa ─────────────────────────

def pote(e, L, P, A, cor='#FFFFFF', material='plastico_transparente', redondo=False, altura_tampa=None,
         cor_tampa='#E8ECEF', material_tampa='plastico_fosco', travas=0, cor_trava='#6B7A8F', vedacao='#7E858C',
         parede=0.3):
    """Recipiente com tampa (o c14 virou molde): redondo (L = P = Ø) ou retangular de cantos redondos;
    `travas` 0 ou 4 abas de clique (só no retangular), que ficam dentro de L × P."""
    alt_t = altura_tampa if altura_tampa is not None else max(0.8, min(2.0, A * 0.16))
    aba = 0.28 if travas else 0.0
    m = e.mat(material, cor)
    mt = e.mat(material_tampa, cor_tampa)
    alt_v = A - alt_t
    if redondo:
        d = min(L, P)
        r = d / 2
        corpo = e.torneado('pote', [(0, 0), (r - 0.4, 0), (r, 0.4), (r, alt_v), (r - parede, alt_v),
                                    (r - parede, parede + 0.3), (r - parede - 0.3, parede), (0, parede)], m)
        tampa = e.torneado('tampa', [(0, alt_v), (r + 0.0, alt_v), (r, A - 0.3), (r - 0.3, A), (0, A)], mt)
        # nervuras de pega na tampa
        e.cilindro('vedacao', d - 0.2, 0.2, pos=(0, 0, alt_v + 0.05), mat=e.mat('silicone', vedacao), raio=0.05)
    else:
        lp, pp = L - 2 * aba - (0.3 if travas else 0.0), P - 2 * aba - (0.3 if travas else 0.0)
        rr = min(1.2, lp / 6, pp / 6)
        corpo = e.caixa('pote', lp, pp, alt_v, pos=(0, 0, alt_v / 2), mat=m, raio=rr, segmentos=6)
        oco = e.caixa('pote-oco', lp - 2 * parede, pp - 2 * parede, alt_v, pos=(0, 0, alt_v / 2 + parede),
                      aux=True, arredondar=True, raio=max(0.2, rr - parede))
        e.furar(corpo, oco, depois_do_bevel=True)
        e.caixa('vedacao', lp + 0.1, pp + 0.1, 0.2, pos=(0, 0, alt_v + 0.1), mat=e.mat('silicone', vedacao), raio=0.08)
        tl, tp = lp + (0.3 if travas else 0.0), pp + (0.3 if travas else 0.0)
        tampa = e.caixa('tampa', tl, tp, alt_t - 0.2, pos=(0, 0, alt_v + 0.2 + (alt_t - 0.2) / 2), mat=mt,
                        raio=min(0.5, (alt_t - 0.2) / 2.1), segmentos=5)
        reb = e.caixa('tampa-rebaixo', tl - 2.2, tp - 2.2, 0.5, pos=(0, 0, A), aux=True, arredondar=True, raio=0.6)
        e.furar(tampa, reb, depois_do_bevel=True)
        if travas:
            mtr = e.mat('plastico_fosco', cor_trava)
            alt_aba = min(1.9, alt_t + 0.8)
            z = A - 0.1 - alt_aba / 2
            for nome, (x, y, lx, ly) in {'frente': (0, -tp / 2 - aba / 2, min(5.0, tl * 0.3), aba),
                                         'costas': (0, tp / 2 + aba / 2, min(5.0, tl * 0.3), aba),
                                         'esq': (-tl / 2 - aba / 2, 0, aba, min(3.6, tp * 0.36)),
                                         'dir': (tl / 2 + aba / 2, 0, aba, min(3.6, tp * 0.36))}.items():
                e.caixa(f'trava-{nome}', lx, ly, alt_aba, pos=(x, y, z), mat=mtr, raio=0.1)
    if _eh_transparente(material):
        _vidro_sem_sombra(corpo)
    if _eh_transparente(material_tampa):
        _vidro_sem_sombra(tampa)


# ───────────────────────── garrafa / cilindro ─────────────────────────

def garrafa(e, L, P, A, cor='#2F6F8F', material='plastico_fosco', d_gargalo=None, ombro=0.18, altura_tampa=None,
            cor_tampa='#1F1F1F', material_tampa='plastico_fosco', alca=False):
    """Garrafa/frasco/cilindro por perfil de torno: corpo Ø = min(L, P) (sem alça) ou Ø = P com alça
    saindo para +X até completar L. `ombro` = fração da altura que estreita até o gargalo (0 = copo reto)."""
    d = P if alca else min(L, P)
    r = d / 2
    cx = -L / 2 + r if alca else 0.0            # com alça, o corpo encosta à esquerda e a alça fecha L
    alt_tampa = altura_tampa if altura_tampa is not None else max(1.0, A * 0.1)
    rg = (d_gargalo / 2) if d_gargalo else (r * 0.55 if ombro > 0 else r)
    z_corpo = A - alt_tampa
    z_ombro = z_corpo * (1 - ombro)
    perfil = [(0, 0), (r - 0.5, 0), (r, 0.5), (r, z_ombro)]
    if ombro > 0:
        perfil += [(r - (r - rg) * 0.55, z_ombro + (z_corpo - z_ombro) * 0.55), (rg, z_corpo - 0.3), (rg, z_corpo)]
    else:
        perfil += [(r, z_corpo)]
    perfil += [(0, z_corpo)]
    corpo = e.torneado('corpo', perfil, e.mat(material, cor), pos=(cx, 0, 0))
    mt = e.mat(material_tampa, cor_tampa)
    rt = rg if ombro > 0 else r
    e.torneado('tampa', [(0, z_corpo), (rt, z_corpo), (rt, A - 0.25), (rt - 0.25, A), (0, A)], mt, pos=(cx, 0, 0))
    if _eh_transparente(material):
        _vidro_sem_sombra(corpo)
    if alca:
        # alça em C na lateral +X, do terço de baixo até perto do ombro; a face de fora chega em L/2
        esp = max(0.6, min(1.2, (L - d) * 0.45))
        xa = L / 2 - esp / 2
        x0 = cx + r - 0.4
        z1, z2 = z_ombro * 0.25, z_ombro * 0.85
        # a curva Bézier passa um pouco além dos pontos: mede e recua até a face de fora cair em L/2
        for _ in range(4):
            al = e.tubo('alca', [(x0, 0, z2), (xa, 0, z2 - 0.6), (xa, 0, z1 + 0.6), (x0, 0, z1)], esp, mat=mt)
            sobra = e.caixa_envolvente()[1].x / 0.01 - L / 2
            if abs(sobra) < 0.03:
                break
            e.pecas.remove(al)
            bpy.data.objects.remove(al)
            xa -= sobra


# ───────────────────────── utensílio plano ─────────────────────────

def utensilio(e, L, P, A, cor='#3A3A3A', material='silicone', cabeca='espatula', frac_cabo=0.55, cor_cabo=None,
              material_cabo='plastico_fosco', furo_pendurar=True):
    """Peça plana deitada: comprimento ao longo de X (L), largura máxima P, espessura A.
    `cabeca`: 'espatula' (pá retangular de ponta reta), 'colher' (concha oval), 'escova' (base + cerdas)."""
    lc = L * frac_cabo
    lh = L - lc
    esp_cabo = min(A, 1.2)
    mc = e.mat(material_cabo, cor_cabo or cor)
    mh = e.mat(material, cor)
    larg_cabo = min(P * 0.45, 2.4)
    cabo = e.caixa('cabo', lc, larg_cabo, esp_cabo, pos=(-L / 2 + lc / 2, 0, esp_cabo / 2), mat=mc,
                   raio=min(larg_cabo, esp_cabo) / 2.1, segmentos=5)
    if furo_pendurar:
        e.furar(cabo, e.cilindro('furo', min(0.7, larg_cabo * 0.4), 4, pos=(-L / 2 + 1.2, 0, 0), aux=True),
                depois_do_bevel=True)
    xh = L / 2 - lh / 2
    if cabeca == 'colher':
        e.esfera('concha', 1.0, pos=(xh, 0, A / 2), mat=mh, escala=(lh, P, A))
    elif cabeca == 'escova':
        alt_base = A * 0.35
        e.caixa('base', lh, P, alt_base, pos=(xh, 0, alt_base / 2), mat=mc, raio=min(0.6, alt_base / 2.1))
        e.caixa('cerdas', lh - 0.6, P - 0.6, A - alt_base, pos=(xh, 0, alt_base + (A - alt_base) / 2),
                mat=mh, raio=0.15)
    else:
        esp = min(A, 0.4)
        e.caixa('pa', lh, P, esp, pos=(xh, 0, esp / 2), mat=mh, raio=min(0.8, P / 6), segmentos=5)
        if A > esp:
            # cabo sobe para a pá: o colar fecha a espessura A no encontro
            e.caixa('colar', 1.2, larg_cabo, A, pos=(xh - lh / 2 + 0.6, 0, A / 2), mat=mc, raio=min(0.4, A / 2.1))


# ───────────────────────── tapete / placa ─────────────────────────

def tapete(e, L, P, A, cor='#8C8C8C', material='tecido', raio=1.5, borda=0.0, cor_borda=None, nervuras=0,
           listras=None):
    """Placa deitada L × P × A: tecido/microfibra/borracha/silicone. `borda` (cm) = vivo/viés em volta
    na `cor_borda`; `nervuras` = frisos ao longo de X no topo (escorredor de silicone); `listras` =
    lista de cores em faixas ao longo de X (jogo americano, tapete listrado)."""
    if borda > 0:
        e.caixa('borda', L, P, A, pos=(0, 0, A / 2), mat=e.mat(material, cor_borda or cor), raio=min(raio, A / 2.1 if A < 1 else raio))
        miolo_l, miolo_p, miolo_a = L - 2 * borda, P - 2 * borda, A * 0.92
    else:
        miolo_l, miolo_p, miolo_a = L, P, A if not nervuras else A * 0.6
    if listras:
        n = len(listras)
        larg = miolo_l / n
        for i, c in enumerate(listras):
            x = -miolo_l / 2 + larg * (i + 0.5)
            e.caixa(f'listra{i}', larg + (0.02 if i < n - 1 else 0), miolo_p, miolo_a + (0.01 if borda else 0),
                    pos=(x, 0, (miolo_a + (0.01 if borda else 0)) / 2), mat=e.mat(material, c), raio=0.1)
    else:
        e.caixa('miolo', miolo_l, miolo_p, miolo_a + (0.01 if borda else 0), pos=(0, 0, (miolo_a + (0.01 if borda else 0)) / 2),
                mat=e.mat(material, cor), raio=min(raio, miolo_a / 2.1) if not borda else min(0.3, miolo_a / 2.1))
    if nervuras:
        alt_n = A - A * 0.6
        passo = miolo_p / (nervuras + 1)
        for i in range(nervuras):
            y = -miolo_p / 2 + passo * (i + 1)
            e.caixa(f'nervura{i}', miolo_l - 1.0, min(0.4, passo * 0.4), alt_n + 0.05,
                    pos=(0, y, A * 0.6 + alt_n / 2 - 0.025), mat=e.mat(material, cor), raio=0.1)


# ───────────────────────── eletrônico pequeno ─────────────────────────

def eletronico(e, L, P, A, cor='#F2F2F2', material='plastico_brilhante', raio=0.8, tela=(0.45, 0.35),
               cor_tela='#111214', face_tela='frente', botoes=2, cor_botao='#9A9EA3', pes=True, prato=None,
               cor_prato=None, material_prato='inox_escovado'):
    """Corpo de cantos redondos com tela (fração da face) e `botoes` redondos ao lado/embaixo.
    `face_tela`: 'frente' (−Y, de pé) ou 'topo' (deitado, tela no alto, ex.: balança de cozinha).
    `prato` = Ø (cm) de prato redondo no topo (balança); `pes` = 4 pés de borracha (cabem em A)."""
    alt_pe = 0.25 if pes else 0.0
    alt_prato = 0.3 if prato else 0.0
    alt_corpo = A - alt_pe - alt_prato
    m = e.mat(material, cor)
    corpo = e.caixa('corpo', L, P, alt_corpo, pos=(0, 0, alt_pe + alt_corpo / 2), mat=m, raio=min(raio, alt_corpo / 2.1),
                    segmentos=6)
    mt = e.mat('vidro_tela', cor_tela)
    mb = e.mat('plastico_fosco', cor_botao)
    if face_tela == 'topo' and prato and min(prato, P - 0.2, L - 0.2) > P * 0.7:
        face_tela = 'frente_baixa'           # o prato toma o topo: tela e botões vão para a face da frente
    if face_tela == 'topo':
        z_top = alt_pe + alt_corpo
        if prato:
            dp = min(prato, P - 0.2, L - 0.2)
            e.cilindro('prato', dp, alt_prato, pos=(0, max(0.0, min(P * 0.12, (P - dp) / 2 - 0.1)), z_top + alt_prato / 2),
                       mat=e.mat(material_prato, cor_prato or '#C9CCCF'), raio=0.1)
        tl, tp = L * tela[0], P * tela[1]
        yt = -P / 2 + tp / 2 + 0.6
        e.caixa('tela', tl, tp, 0.06, pos=(-L * 0.12 if botoes else 0, yt, z_top - 0.02), mat=mt, raio=0.1)
        for i in range(botoes):
            e.cilindro(f'botao{i}', 0.9, 0.08, pos=(L * 0.18 + i * 1.3, yt, z_top - 0.02), mat=mb, raio=0.03)
    elif face_tela == 'frente_baixa':
        z_top = alt_pe + alt_corpo
        dp = min(prato, P - 0.2, L - 0.2)
        e.cilindro('prato', dp, alt_prato, pos=(0, 0, z_top + alt_prato / 2),
                   mat=e.mat(material_prato, cor_prato or '#C9CCCF'), raio=0.1)
        ta = max(0.5, alt_corpo * 0.5)
        zt = alt_pe + alt_corpo / 2
        e.caixa('tela', L * 0.28, 0.06, ta, pos=(-L * 0.1, -P / 2 + 0.02, zt), mat=mt, raio=0.08)
        for i in range(botoes):
            e.cilindro(f'botao{i}', min(0.8, ta), 0.08, pos=(L * 0.14 + i * 1.2, -P / 2 + 0.02, zt), rot=(90, 0, 0),
                       mat=mb, raio=0.03)
    else:
        tl, ta = L * tela[0], alt_corpo * tela[1]
        zt = alt_pe + alt_corpo * 0.62
        e.caixa('tela', tl, 0.06, ta, pos=(0, -P / 2 + 0.02, zt), mat=mt, raio=0.1)
        for i in range(botoes):
            x = (i - (botoes - 1) / 2) * 1.5
            e.cilindro(f'botao{i}', 1.0, 0.08, pos=(x, -P / 2 + 0.02, alt_pe + alt_corpo * 0.24), rot=(90, 0, 0),
                       mat=mb, raio=0.03)
    if pes:
        mp = e.mat('borracha', '#2A2A2A')
        for sx in (-1, 1):
            for sy in (-1, 1):
                e.cilindro(f'pe{sx}{sy}', 1.0, alt_pe + 0.05, pos=(sx * (L / 2 - 1.4), sy * (P / 2 - 1.4), (alt_pe + 0.05) / 2),
                           mat=mp, raio=0.05)


MOLDES = {
    'caixa_organizadora': caixa_organizadora,
    'pote': pote,
    'garrafa': garrafa,
    'utensilio': utensilio,
    'tapete': tapete,
    'eletronico': eletronico,
}


def modelar_por_molde(e, spec):
    """`modelar` pronto: lê `spec['molde']` = {"nome": <molde>, ...parâmetros} e monta a maquete."""
    params = dict(spec.get('molde') or {})
    nome = params.pop('nome', None)
    if nome not in MOLDES:
        raise SystemExit(f"{spec.get('codigo')}: \"molde\".nome tem de ser um de {', '.join(MOLDES)} (veio {nome!r})")
    L, P, A = _medidas(spec)
    MOLDES[nome](e, L, P, A, **params)
