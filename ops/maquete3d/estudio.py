"""Estúdio Tavrov de maquetes 3D (Blender por código, `pip install bpy pillow`).

Uma maquete = `maquetes/<cod>.json` (medidas, fontes, câmeras) + `maquetes/<cod>.py`
(função `modelar(e, spec)` que monta as peças com as ferramentas daqui).
Quem chama é `ops/gerar-3d.py`.

Convenção: tudo em CENTÍMETROS na especificação; a cena é em metros (1 cm = 0,01),
para o .glb sair no tamanho real (realidade aumentada). X = largura (L),
Y = profundidade (P, frente olhando para -Y), Z = altura (A), produto apoiado em Z = 0.
"""
import math

import bpy  # antes do bmesh: o módulo bpy é quem registra o bmesh
import bmesh
from mathutils import Vector

CM = 0.01

# fundo das fotos e composição: em composicao.py (sem Blender, para `gerar-3d.py --recompor`)
from maquete3d.composicao import FUNDO_HEX, compor  # noqa: E402,F401


def tolerancia_cm(medida_cm):
    """Quanto a maquete pode fugir da medida, por eixo: 1% da medida, entre 1 mm e 5 mm
    (anel de 2 cm: 1 mm · organizador de 23 cm: 2,3 mm · sofá de 2 m: 5 mm)."""
    return max(0.1, min(0.5, medida_cm * 0.01))


# ─────────────────────────── cor e materiais ───────────────────────────

def _linear(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(hexcor):
    h = hexcor.lstrip('#')
    return (_linear(int(h[0:2], 16)), _linear(int(h[2:4], 16)), _linear(int(h[4:6], 16)), 1.0)


def _principled(nome):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    return m, m.node_tree.nodes['Principled BSDF']


def _set(bsdf, **kw):
    nomes = {'cor': 'Base Color', 'metal': 'Metallic', 'aspereza': 'Roughness',
             'aniso': 'Anisotropic', 'aniso_giro': 'Anisotropic Rotation',
             'verniz': 'Coat Weight', 'verniz_aspereza': 'Coat Roughness',
             'veludo': 'Sheen Weight', 'veludo_aspereza': 'Sheen Roughness', 'veludo_cor': 'Sheen Tint',
             'sss': 'Subsurface Weight', 'sss_raio': 'Subsurface Radius', 'sss_escala': 'Subsurface Scale',
             'brilho': 'Specular IOR Level', 'transmissao': 'Transmission Weight', 'ior': 'IOR'}
    for k, v in kw.items():
        bsdf.inputs[nomes[k]].default_value = v


def _relevo(mat, escala, forca, detalhe=6.0):
    """Relevo fino (poro do plástico, pelo do tecido, risco do escovado) — só no render;
    o .glb leva cor, metal e aspereza."""
    nt = mat.node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = escala
    tex.inputs['Detail'].default_value = detalhe
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = forca
    bump.inputs['Distance'].default_value = 0.0004
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])


def _escovado(mat, escala=900.0, forca=0.08):
    """Risco do metal escovado: ruído esticado ao longo de X."""
    nt = mat.node_tree
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapa = nt.nodes.new('ShaderNodeMapping')
    mapa.inputs['Scale'].default_value = (0.02, 1.0, 1.0)
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = escala
    tex.inputs['Detail'].default_value = 2.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = forca
    bump.inputs['Distance'].default_value = 0.0002
    nt.links.new(coord.outputs['Object'], mapa.inputs['Vector'])
    nt.links.new(mapa.outputs['Vector'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])


def material(tipo, cor, nome=None):
    """Materiais PBR aparentes. `tipo` é o que o anúncio mostra; `cor` é hex sRGB."""
    m, b = _principled(nome or f'{tipo}-{cor}')
    _set(b, cor=rgba(cor))
    if tipo == 'aluminio_escovado':
        _set(b, metal=1.0, aspereza=0.32, aniso=0.6)
        _escovado(m)
    elif tipo == 'aluminio_anodizado':           # "alumínio espacial" fosco
        _set(b, metal=1.0, aspereza=0.42, aniso=0.3)
        _escovado(m, forca=0.05)
    elif tipo == 'inox_escovado':
        _set(b, metal=1.0, aspereza=0.26, aniso=0.7)
        _escovado(m, forca=0.1)
    elif tipo == 'metal_cromado':
        _set(b, metal=1.0, aspereza=0.08)
    elif tipo == 'metal_pintado':                # tinta eletrostática
        _set(b, metal=0.0, aspereza=0.42, verniz=0.25, verniz_aspereza=0.3)
        _relevo(m, 1800, 0.05)
    elif tipo == 'plastico_fosco':
        _set(b, metal=0.0, aspereza=0.55)
        _relevo(m, 2500, 0.04)
    elif tipo == 'plastico_brilhante':
        _set(b, metal=0.0, aspereza=0.18, verniz=0.4, verniz_aspereza=0.08)
    elif tipo == 'silicone':
        _set(b, metal=0.0, aspereza=0.5, sss=0.15, sss_escala=0.002)
    elif tipo == 'borracha':
        _set(b, metal=0.0, aspereza=0.75)
        _relevo(m, 3000, 0.05)
    elif tipo == 'pelucia':                      # tecido de pelo curto (plush)
        _set(b, metal=0.0, aspereza=0.95, brilho=0.15, veludo=0.7, veludo_aspereza=0.4,
             veludo_cor=(0.3, 0.3, 0.32, 1.0))
        _relevo(m, 1400, 0.35, detalhe=10.0)
    elif tipo == 'tecido':
        _set(b, metal=0.0, aspereza=0.9, veludo=0.5, veludo_aspereza=0.5)
        _relevo(m, 3500, 0.15)
    elif tipo == 'madeira':
        _set(b, metal=0.0, aspereza=0.5, verniz=0.2)
        _relevo(m, 600, 0.05)
    elif tipo == 'plastico_transparente':        # PET, acrílico: transparência simples (leve no celular)
        _set(b, metal=0.0, aspereza=0.08, verniz=0.5, verniz_aspereza=0.05)
        b.inputs['Alpha'].default_value = 0.32
    elif tipo == 'vidro_tela':                   # tela apagada de celular
        _set(b, metal=0.0, aspereza=0.05, verniz=1.0, verniz_aspereza=0.02)
    elif tipo == 'vidro':
        _set(b, metal=0.0, aspereza=0.02, transmissao=1.0, ior=1.45)
    else:
        raise ValueError(f'material desconhecido: {tipo}')
    return m


# ─────────────────────────── peças ───────────────────────────

class Estudio:
    """Cena da maquete. Guarda as peças do produto e os cortadores (booleanos)."""

    def __init__(self, cod):
        self.cod = cod
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.cena = bpy.context.scene
        self.col_produto = bpy.data.collections.new(f'produto-{cod}')
        self.col_aux = bpy.data.collections.new('auxiliar')
        self.cena.collection.children.link(self.col_produto)
        self.cena.collection.children.link(self.col_aux)
        self.pecas = []
        self._mats = {}

    def mat(self, tipo, cor):
        k = (tipo, cor)
        if k not in self._mats:
            self._mats[k] = material(tipo, cor)
        return self._mats[k]

    # -- base

    def _obj(self, nome, bm, mat, pos, rot, aux=False):
        me = bpy.data.meshes.new(nome)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(nome, me)
        (self.col_aux if aux else self.col_produto).objects.link(ob)
        ob.location = Vector(pos) * CM
        ob.rotation_euler = [math.radians(a) for a in rot]
        if mat is not None:
            me.materials.append(mat)
        if not aux:
            for p in me.polygons:
                p.use_smooth = True
            self.pecas.append(ob)
        return ob

    @staticmethod
    def _bevel(ob, raio_cm, segmentos=4):
        if raio_cm <= 0:
            return
        mod = ob.modifiers.new('bevel', 'BEVEL')
        mod.width = raio_cm * CM
        mod.segments = segmentos
        mod.limit_method = 'ANGLE'
        mod.angle_limit = math.radians(35)
        mod.harden_normals = True
        # normais limpas nas faces planas depois do bevel
        wn = ob.modifiers.new('normais', 'WEIGHTED_NORMAL')
        wn.keep_sharp = True

    def caixa(self, nome, l, p, a, pos=(0, 0, 0), rot=(0, 0, 0), mat=None, raio=0.15, segmentos=4, aux=False,
              arredondar=False):
        """Caixa L × P × A (cm), com cantos arredondados de `raio` cm; `pos` é o centro.
        Cortador (`aux`) com `arredondar=True` faz rebaixo de cantos redondos."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(l * CM, p * CM, a * CM), verts=bm.verts)
        ob = self._obj(nome, bm, mat, pos, rot, aux)
        if not aux or arredondar:
            self._bevel(ob, min(raio, l / 2.05, p / 2.05, a / 2.05), segmentos)
        return ob

    def cilindro(self, nome, d, a, pos=(0, 0, 0), rot=(0, 0, 0), mat=None, raio=0.1, lados=64, d_topo=None, aux=False):
        """Cilindro (ou tronco de cone, com `d_topo`) de diâmetro `d` e altura `a` (cm), eixo Z."""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=lados, radius1=d / 2 * CM,
                              radius2=(d_topo if d_topo is not None else d) / 2 * CM, depth=a * CM)
        ob = self._obj(nome, bm, mat, pos, rot, aux)
        if not aux:
            self._bevel(ob, min(raio, d / 4, a / 2.05), 3)
        return ob

    def esfera(self, nome, d, pos=(0, 0, 0), mat=None, escala=(1, 1, 1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=d / 2 * CM)
        bmesh.ops.scale(bm, vec=escala, verts=bm.verts)
        return self._obj(nome, bm, mat, pos, (0, 0, 0))

    def tubo(self, nome, pontos, d, mat=None, fechado=False):
        """Arame/tubo de diâmetro `d` (cm) passando pelos `pontos` (cm), cantos suaves."""
        cu = bpy.data.curves.new(nome, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = d / 2 * CM
        cu.bevel_resolution = 3
        cu.use_fill_caps = True
        # Bézier com alças automáticas: a curva passa exatamente pelos pontos dados
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(pontos) - 1)
        for bp, (x, y, z) in zip(sp.bezier_points, pontos):
            bp.co = (x * CM, y * CM, z * CM)
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        sp.use_cyclic_u = fechado
        # curva com muitos pontos pede menos subdivisão por trecho (o .glb fica leve no celular)
        sp.resolution_u = max(2, min(24, 480 // len(pontos)))
        ob = bpy.data.objects.new(nome, cu)
        self.col_produto.objects.link(ob)
        if mat is not None:
            cu.materials.append(mat)
        self.pecas.append(ob)
        return ob

    def toro(self, nome, d_maior, d_menor, pos=(0, 0, 0), rot=(0, 0, 0), mat=None):
        bpy.ops.mesh.primitive_torus_add(major_radius=d_maior / 2 * CM, minor_radius=d_menor / 2 * CM,
                                         major_segments=64, minor_segments=24)
        ob = bpy.context.active_object
        ob.name = nome
        for c in ob.users_collection:
            c.objects.unlink(ob)
        self.col_produto.objects.link(ob)
        ob.location = Vector(pos) * CM
        ob.rotation_euler = [math.radians(a) for a in rot]
        if mat is not None:
            ob.data.materials.append(mat)
        for p in ob.data.polygons:
            p.use_smooth = True
        self.pecas.append(ob)
        return ob

    def engrenagem(self, nome, d, esp, dentes, pos=(0, 0, 0), rot=(0, 0, 0), mat=None, altura_dente=None, furo=0.0):
        """Engrenagem plana: disco de `dentes` dentes, diâmetro externo `d`, espessura `esp` (cm)."""
        h = altura_dente if altura_dente is not None else d * 0.09
        r_ext, r_int = d / 2, d / 2 - h
        bm = bmesh.new()
        pts = []
        n = dentes * 4
        for i in range(n):
            ang = 2 * math.pi * i / n
            r = r_ext if (i % 4) in (1, 2) else r_int
            pts.append((r * math.cos(ang) * CM, r * math.sin(ang) * CM))
        baixo = [bm.verts.new((x, y, -esp / 2 * CM)) for x, y in pts]
        topo = [bm.verts.new((x, y, esp / 2 * CM)) for x, y in pts]
        bm.faces.new(list(reversed(baixo)))
        bm.faces.new(topo)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((baixo[i], baixo[j], topo[j], topo[i]))
        ob = self._obj(nome, bm, mat, pos, rot)
        self._bevel(ob, min(0.08, esp / 3), 2)
        if furo > 0:
            c = self.cilindro(f'{nome}-furo', furo, esp * 3, pos=pos, rot=rot, aux=True)
            self.furar(ob, c)
        return ob

    def furar(self, ob, cortador, depois_do_bevel=False):
        """Tira o volume do `cortador` da peça (booleano).
        Padrão: o furo entra antes do bevel (chapa com rasgo, tudo arredondado junto).
        `depois_do_bevel=True`: para peça de cantos bem redondos (o bevel grande falha em malha
        já recortada) — o furo entra depois, e um bevel fino arredonda só a borda do furo."""
        cortador.hide_render = True
        cortador.display_type = 'WIRE'
        mod = ob.modifiers.new(f'furo-{cortador.name}', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = cortador

        def mover(nome, indice):
            with bpy.context.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_move_to_index(modifier=nome, index=indice)

        if not depois_do_bevel:
            mover(mod.name, 0)
            return mod
        if 'bevel-furo' not in ob.modifiers:
            fino = ob.modifiers.new('bevel-furo', 'BEVEL')
            fino.width = 0.06 * CM
            fino.segments = 2
            fino.limit_method = 'ANGLE'
            fino.angle_limit = math.radians(50)
        # ordem: bevel · furos · bevel-furo · normais
        mover(mod.name, ob.modifiers.find('bevel-furo'))
        mover('bevel-furo', len(ob.modifiers) - 1)
        if 'normais' in ob.modifiers:
            mover('normais', len(ob.modifiers) - 1)
        return mod

    def rasgos(self, ob, eixo, centro, n, passo, largura, comprimento, prof=1.0, normal='y'):
        """Série de `n` rasgos (fendas de cantos redondos) atravessando uma chapa.
        `normal` = eixo que a chapa atravessa ('y' em chapa de pé, 'z' em chapa deitada);
        `eixo` = direção em que a série se repete ('x' ou 'z'); `centro` (cm) é o meio da série;
        `largura` é medida ao longo de `eixo` e `comprimento` na direção restante."""
        cx, cy, cz = centro
        for i in range(n):
            off = (i - (n - 1) / 2) * passo
            pos = (cx + off, cy, cz) if eixo == 'x' else (cx, cy, cz + off)
            if normal == 'z':
                dims = (largura, comprimento, prof)
            elif eixo == 'x':
                dims = (largura, prof, comprimento)
            else:
                dims = (comprimento, prof, largura)
            c = self.caixa(f'{ob.name}-rasgo{i}', *dims, pos=pos, aux=True)
            self.furar(ob, c)

    # -- blocos prontos (padrão Tavrov): o que deu certo no piloto, para reusar em produto novo

    def torneado(self, nome, perfil, mat, pos=(0, 0, 0), lados=96, escala_xy=(1.0, 1.0)):
        """Peça de revolução (como num torno): caneca, garrafa, copo, vaso, pote, luminária.
        `perfil` = pontos (raio, altura) em cm, de baixo para cima pelo lado de fora e voltando
        por dentro; ponto com raio 0 fica no eixo. Parede com espessura sai sem booleano (sem
        sombra tremida por dentro). `escala_xy` achata a peça (frasco oval, por exemplo)."""
        bm = bmesh.new()
        aneis = []
        for r, z in perfil:
            if r <= 1e-6:
                aneis.append([bm.verts.new((0, 0, z * CM))])
            else:
                aneis.append([bm.verts.new((r * CM * math.cos(2 * math.pi * i / lados) * escala_xy[0],
                                            r * CM * math.sin(2 * math.pi * i / lados) * escala_xy[1], z * CM))
                              for i in range(lados)])
        for a, b in zip(aneis, aneis[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(lados):
                j = (i + 1) % lados
                if len(a) == 1:
                    bm.faces.new((a[0], b[i], b[j]))
                elif len(b) == 1:
                    bm.faces.new((a[i], b[0], a[j]))
                else:
                    bm.faces.new((a[i], b[i], b[j], a[j]))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = self._obj(nome, bm, mat, pos, (0, 0, 0))
        sm = ob.modifiers.new('suave', 'WEIGHTED_NORMAL')
        sm.keep_sharp = True
        return ob

    def rebaixo_face(self, corpo, face, largura, altura, cor, prof=1.0, raio=0.8, centro_z=None, material='plastico_fosco'):
        """Rebaixo de cantos redondos numa face do `corpo` (caixa centrada em x = y = 0), com uma
        placa colorida no fundo — o "painel de atividade" do cubo p16. `face`: 'frente' (-Y),
        'costas' (+Y), 'esq' (-X) ou 'dir' (+X). Devolve a placa (dá para furar ou pôr peças nela);
        as peças da face ficam entre o fundo do rebaixo e a face, sem passar da medida."""
        lo, hi = self.caixa_envolvente()
        L, P = (hi.x - lo.x) / CM, (hi.y - lo.y) / CM
        zc = centro_z if centro_z is not None else (lo.z + hi.z) / 2 / CM
        eixo, sinal = {'frente': ('y', -1), 'costas': ('y', 1), 'esq': ('x', -1), 'dir': ('x', 1)}[face]
        if eixo == 'y':
            y = sinal * P / 2
            self.furar(corpo, self.caixa(f'reb-{face}', largura, prof * 2, altura, pos=(0, y, zc), aux=True,
                                         arredondar=True, raio=raio), depois_do_bevel=True)
            return self.caixa(f'placa-{face}', largura - 0.1, 0.12, altura - 0.1, pos=(0, y - sinal * (prof - 0.06), zc),
                              mat=self.mat(material, cor), raio=0.05)
        x = sinal * L / 2
        self.furar(corpo, self.caixa(f'reb-{face}', prof * 2, largura, altura, pos=(x, 0, zc), aux=True,
                                     arredondar=True, raio=raio), depois_do_bevel=True)
        return self.caixa(f'placa-{face}', 0.12, largura - 0.1, altura - 0.1, pos=(x - sinal * (prof - 0.06), 0, zc),
                          mat=self.mat(material, cor), raio=0.05)

    def almofada(self, nome, L, P, A, mat, vivo=0.42, cor_vivo='#161618', costas=0.32, lombar=0.58,
                 altura_lombar=-0.3, abas=1.6, contorno=0.28, perfil=0.5, n_theta=128, n_phi=48):
        """Peça macia de pé (almofada, travesseiro, assento) no padrão da p08: superfície
        paramétrica (superelipsoide) L × P × A exatos, costas quase planas, frente abaulada
        (`lombar` = quanto engorda, em `altura_lombar` de -1 embaixo a 1 em cima), pontas que
        avançam (`abas`, cm) e o vivo (costura) em volta. Devolve os pontos da borda (cm), para
        pôr zíper, etiqueta ou alça nela."""
        a, c = L / 2, A / 2
        atras = costas * P
        frente = P - atras

        def bf(z):
            v = z / c
            return frente * ((1 - lombar) + lombar * math.exp(-((v - altura_lombar) / 0.62) ** 2))

        def sp(t, ex):
            return math.copysign(abs(t) ** ex, t)

        def ponto(theta, phi):
            cp, sn = math.cos(phi), math.sin(phi)
            x = a * sp(cp, perfil) * sp(math.cos(theta), contorno)
            z = c * sp(cp, perfil) * sp(math.sin(theta), contorno)
            y = sp(sn, perfil) * (bf(z) if sn < 0 else atras)
            return [x, y - abas * (x / a) ** 2, z]

        aneis = [[ponto(2 * math.pi * i / n_theta, -math.pi / 2 + math.pi * k / n_phi) for i in range(n_theta)]
                 for k in range(1, n_phi)]
        polo_f, polo_t = [0.0, -bf(0.0), 0.0], [0.0, atras, 0.0]
        borda = [ponto(2 * math.pi * i / n_theta, 0.0) for i in range(n_theta)]
        todos = [p for anel in aneis for p in anel] + [polo_f, polo_t]
        lo = [min(p[i] for p in todos) for i in range(3)]
        hi = [max(p[i] for p in todos) for i in range(3)]
        rv = vivo / 2                       # o vivo fica na borda e fecha L e A por fora
        alvo = (L - 2 * rv, P, A - 2 * rv)
        esc = [alvo[i] / (hi[i] - lo[i]) for i in range(3)]
        meio = [(hi[i] + lo[i]) / 2 for i in range(3)]

        def ajusta(p):
            q = [(p[i] - meio[i]) * esc[i] for i in range(3)]
            q[2] += A / 2
            return q

        bm = bmesh.new()
        n = len(aneis[0])
        vs = [[bm.verts.new(Vector(ajusta(p)) * CM) for p in anel] for anel in aneis]
        vf = bm.verts.new(Vector(ajusta(polo_f)) * CM)
        vt = bm.verts.new(Vector(ajusta(polo_t)) * CM)
        for k in range(len(vs) - 1):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((vs[k][i], vs[k][j], vs[k + 1][j], vs[k + 1][i]))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((vf, vs[0][j], vs[0][i]))
            bm.faces.new((vt, vs[-1][i], vs[-1][j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self._obj(nome, bm, mat, (0, 0, 0), (0, 0, 0))
        pontos = [ajusta(p) for p in borda]
        if vivo:
            self.tubo(f'{nome}-vivo', pontos, vivo, mat=self.mat('tecido', cor_vivo), fechado=True)
        return pontos

    # -- medidas

    def caixa_envolvente(self):
        """Caixa envolvente do produto montado (m), com modificadores aplicados."""
        bpy.context.view_layer.update()     # curvas novas só têm caixa depois de avaliadas
        dg = bpy.context.evaluated_depsgraph_get()
        lo = Vector((1e9, 1e9, 1e9))
        hi = Vector((-1e9, -1e9, -1e9))
        for ob in self.pecas:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()           # malha final (curva com espessura, booleanos, bevel)
            mw = ev.matrix_world
            for v in me.vertices:
                w = mw @ v.co
                lo = Vector(map(min, lo, w))
                hi = Vector(map(max, hi, w))
            ev.to_mesh_clear()
        return lo, hi

    def medidas_cm(self):
        lo, hi = self.caixa_envolvente()
        return tuple(round((hi[i] - lo[i]) / CM, 2) for i in range(3))

    # -- estúdio

    def montar_estudio(self):
        lo, hi = self.caixa_envolvente()
        centro = (lo + hi) / 2
        tam = max((hi - lo).length, 0.05)
        cena = self.cena

        # chão que só recebe sombra (o fundo vira a cor da marca na composição)
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=tam * 20)
        chao = self._obj('chao', bm, None, (centro.x / CM, centro.y / CM, lo.z / CM), (0, 0, 0), aux=True)
        chao.is_shadow_catcher = True

        # mundo de estúdio: teto claro, horizonte cinza e chão escuro — é o que o metal reflete
        # (sem isso o metal vira um branco chapado)
        w = bpy.data.worlds.new('estudio')
        w.use_nodes = True
        nt = w.node_tree
        bg = nt.nodes['Background']
        coord = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        rampa = nt.nodes.new('ShaderNodeValToRGB')
        cr = rampa.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.35, (0.03, 0.03, 0.035, 1)
        cr.elements[1].position, cr.elements[1].color = 0.9, (0.95, 0.94, 0.92, 1)
        meio = cr.elements.new(0.52)
        meio.color = (0.32, 0.31, 0.31, 1)
        mapa = nt.nodes.new('ShaderNodeMapRange')
        mapa.inputs['From Min'].default_value = -1.0
        mapa.inputs['From Max'].default_value = 1.0
        nt.links.new(coord.outputs['Generated'], sep.inputs['Vector'])
        nt.links.new(sep.outputs['Z'], mapa.inputs['Value'])
        nt.links.new(mapa.outputs['Result'], rampa.inputs['Fac'])
        nt.links.new(rampa.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.45
        cena.world = w

        # 3 pontos: principal (softbox grande à esquerda-frente), preenchimento, recorte atrás, e topo
        d = tam * 3.2
        def luz(nome, az, el, tamanho, fator):
            ld = bpy.data.lights.new(nome, 'AREA')
            ld.shape = 'RECTANGLE'
            ld.size = tamanho * tam
            ld.size_y = tamanho * tam * 0.7
            ld.energy = fator * (d ** 2) * 32
            ld.color = (1.0, 0.98, 0.95)
            ob = bpy.data.objects.new(nome, ld)
            self.col_aux.objects.link(ob)
            a, e = math.radians(az), math.radians(el)
            ob.location = centro + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d
            dirv = centro - ob.location
            ob.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler()
            ob.visible_camera = False
            return ob
        self.luzes = {n: luz(n, *a) for n, a in (('luz-principal', (-65, 36, 2.2, 1.0)),
                                                  ('luz-preenche', (60, 18, 2.6, 0.2)),
                                                  ('luz-recorte', (170, 45, 1.4, 0.55)),
                                                  ('luz-topo', (0, 85, 2.0, 0.18)))}
        self._base_luz = {n: ob.data.energy for n, ob in self.luzes.items()}
        self._mundo, self._base_mundo = bg, bg.inputs['Strength'].default_value

        cam_data = bpy.data.cameras.new('camera')
        cam_data.lens = 70
        cam_data.sensor_width = 36
        self.camera = bpy.data.objects.new('camera', cam_data)
        self.col_aux.objects.link(self.camera)
        cena.camera = self.camera
        self._centro, self._tam = centro, tam

        r = cena.render
        r.engine = 'CYCLES'
        r.film_transparent = True
        cena.cycles.device = 'CPU'
        cena.cycles.use_denoising = True
        cena.cycles.use_adaptive_sampling = True
        cena.cycles.adaptive_threshold = 0.015
        cena.cycles.denoiser = 'OPENIMAGEDENOISE'
        cena.cycles.max_bounces = 8
        cena.cycles.glossy_bounces = 4
        cena.cycles.transparent_max_bounces = 8
        # Khronos PBR Neutral: o mapa de tons feito para mostrar produto com a cor fiel — e é o
        # mesmo "neutral" do <model-viewer>, então o render e o 3D da página ficam iguais
        cena.view_settings.view_transform = 'Khronos PBR Neutral'
        cena.view_settings.look = 'None'
        cena.view_settings.exposure = -0.55
        r.resolution_x, r.resolution_y = 1600, 1200     # o enquadramento depende da proporção
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'

    def enquadrar(self, az, el, lente=70, alvo=None, zoom=1.0, folga=1.18):
        """Câmera a `az` graus (0 = de frente, positivo gira para a direita do produto)
        e `el` graus de elevação, enquadrando o produto inteiro (ou `alvo` em cm, com `zoom`)."""
        cam = self.camera
        cam.data.lens = lente
        a, e = math.radians(az), math.radians(el)
        direcao = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        alvo_m = Vector(alvo) * CM if alvo is not None else self._centro
        cam.rotation_euler = (-direcao).to_track_quat('-Z', 'Y').to_euler()
        # distância que cabe a caixa envolvente inteira no quadro
        lo, hi = self.caixa_envolvente()
        cantos = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        r = self.cena.render
        aspecto = r.resolution_x / r.resolution_y
        fov_h = 2 * math.atan(cam.data.sensor_width / 2 / lente)
        fov_v = 2 * math.atan(math.tan(fov_h / 2) / aspecto)
        rot = cam.rotation_euler.to_matrix()
        dir_cam, cima, lado = rot @ Vector((0, 0, -1)), rot @ Vector((0, 1, 0)), rot @ Vector((1, 0, 0))
        dist = 0.0
        for c in cantos:
            v = c - alvo_m
            prof = v.dot(dir_cam)
            dist = max(dist,
                       abs(v.dot(lado)) / math.tan(fov_h / 2) - prof,
                       abs(v.dot(cima)) / math.tan(fov_v / 2) - prof)
        dist = dist * folga / zoom
        cam.location = alvo_m - dir_cam * dist
        cam.data.clip_start = dist / 100
        cam.data.clip_end = dist * 100

    def render(self, caminho_png, largura=1600, altura=1200, amostras=160):
        r = self.cena.render
        if abs(largura / altura - r.resolution_x / r.resolution_y) > 1e-3:
            raise ValueError('a proporção do render tem de ser a do enquadramento (4:3)')
        r.resolution_x, r.resolution_y = largura, altura
        r.resolution_percentage = 100
        self.cena.cycles.samples = amostras
        r.filepath = str(caminho_png)
        bpy.ops.render.render(write_still=True)

    # -- cor da foto (cérebro 30/10): o .glb leva a cor verdadeira; a exposição se ajusta (maquete3d/cor.py)

    def preencher(self, fator):
        """30/10 (cérebro): produto escuro lê preto COM volume. Em vez de baixar a exposição de tudo (a u03 virou silhueta
        chapada e a alça amarela ficou mostarda), baixa só o que lava a peça escura: preenchimento, topo e o ambiente.
        A luz principal (key) e o recorte (rim) ficam, e com eles os realces e a borda."""
        for n in ('luz-preenche', 'luz-topo'):
            self.luzes[n].data.energy = self._base_luz[n] * fator
        self._mundo.inputs['Strength'].default_value = self._base_mundo * fator

    @staticmethod
    def sem_veludo(material, peso=0.05):
        """30/10: o veludo (Sheen) do 'tecido' (0,5) põe um véu cinza no preto: a u03 ficou #595756 com o preenchimento no
        mínimo e a exposição no piso (alvo da foto oficial #1A1D23). A u04 já usava 0,05 pelo mesmo motivo (_pano).
        Não mexe na cor (Base Color), só no brilho de veludo do corpo escuro."""
        b = material.node_tree.nodes.get('Principled BSDF') if material and material.node_tree else None
        if b is not None and 'Sheen Weight' in b.inputs:
            b.inputs['Sheen Weight'].default_value = min(b.inputs['Sheen Weight'].default_value, peso)

    def materiais_por_area(self):
        """[(material, hex, área)] dos materiais do produto, do que cobre mais área para o que cobre menos."""
        hex_de = {m: cor for (_, cor), m in self._mats.items()}
        dg = bpy.context.evaluated_depsgraph_get()
        area = {}
        for ob in self.pecas:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            esc = ob.matrix_world.to_scale()
            k = abs(esc.x * esc.y * esc.z) ** (2 / 3)
            for p in me.polygons:
                if p.material_index < len(ob.material_slots):
                    m = ob.material_slots[p.material_index].material
                    if m in hex_de:
                        area[m] = area.get(m, 0.0) + p.area * k
            ev.to_mesh_clear()
        return [(m, hex_de[m], a) for m, a in sorted(area.items(), key=lambda x: -x[1])]

    def material_corpo(self):
        """(material, hex) do material que cobre a maior área do produto (o 'corpo')."""
        hex_de = {m: cor for (_, cor), m in self._mats.items()}
        dg = bpy.context.evaluated_depsgraph_get()
        area = {}
        for ob in self.pecas:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            esc = ob.matrix_world.to_scale()
            k = abs(esc.x * esc.y * esc.z) ** (2 / 3)
            for p in me.polygons:
                if p.material_index < len(ob.material_slots):
                    m = ob.material_slots[p.material_index].material
                    if m in hex_de:
                        area[m] = area.get(m, 0.0) + p.area * k
            ev.to_mesh_clear()
        if not area:
            return None, None
        m = max(area, key=area.get)
        return m, hex_de[m]

    def render_mascara(self, caminho_png, material, largura=400, altura=300):
        """Render rápido só do corpo: as outras peças viram holdout (alfa 0). A câmera é a do último enquadrar."""
        corte = bpy.data.materials.get('_holdout') or bpy.data.materials.new('_holdout')
        corte.use_nodes = True
        nt = corte.node_tree
        if 'Holdout' not in nt.nodes:
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            sai = nt.nodes.new('ShaderNodeOutputMaterial')
            nt.links.new(nt.nodes.new('ShaderNodeHoldout').outputs['Holdout'], sai.inputs['Surface'])
        guardado = []
        for ob in self.pecas:
            for s in ob.material_slots:
                if s.material is not material:
                    guardado.append((s, s.material, s.link))
                    s.material = corte
        r, c = self.cena.render, self.cena.cycles
        antes = (r.resolution_x, r.resolution_y, r.resolution_percentage, c.samples, c.use_denoising, r.filepath)
        try:
            r.resolution_x, r.resolution_y, r.resolution_percentage = largura, altura, 100
            c.samples, c.use_denoising = 4, False
            r.filepath = str(caminho_png)
            bpy.ops.render.render(write_still=True)
        finally:
            r.resolution_x, r.resolution_y, r.resolution_percentage, c.samples, c.use_denoising, r.filepath = antes
            for s, m, link in guardado:
                s.material = m

    def exportar_glb(self, caminho):
        """Só as peças do produto, com modificadores aplicados, em metros (3D da página)."""
        for ob in bpy.data.objects:
            ob.select_set(False)
        for ob in self.pecas:
            ob.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(caminho), export_format='GLB', use_selection=True,
                                  export_apply=True, export_yup=True, export_cameras=False,
                                  export_lights=False, export_texcoords=False)


def exportar_usdz(estudio, caminho):
    """USDZ do produto (realidade aumentada no iPhone, Quick Look), em metros. Malha da vista
    (como o .glb), não a do render: subdivisão alta só no render (p06) deixaria o arquivo pesado."""
    for ob in bpy.data.objects:
        ob.select_set(ob in estudio.pecas)
    bpy.ops.wm.usd_export(filepath=str(caminho), selected_objects_only=True, export_materials=True,
                          generate_preview_surface=True, export_lights=False, export_cameras=False,
                          convert_world_material=False, export_global_up_selection='Y', evaluation_mode='VIEWPORT',
                          export_global_forward_selection='NEGATIVE_Z')
