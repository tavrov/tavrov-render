"""Animação 3D da maquete (FÁBRICA 2.0, CEO 30/10: "faça um vídeo com as maquetes, mas precisa melhorar muito, usando o
exemplo do ferreiro: um vídeo animado, top de linha"). Roda NA NUVEM (GitHub Actions, `pip install bpy`), com o MESMO
estúdio aprovado das maquetes (luz, materiais, câmera, Khronos PBR Neutral) e o mesmo `maquetes/<cod>.py`.

Mestres (SISTEMA/divulgacao/mestres/animado.md): câmera sempre em movimento, corte a cada 1,5–2 s, um momento de
transformação (explodir e montar, como o SMEG), macro do detalhe e o produto em destaque no fim. A função que só a
Tavrov mostra: o botão desce, os pinos recolhem e o pelo solta; e a régua em escala real.

Saída: <saida>/<plano>/0001.png ... (fundo transparente, com a sombra); quem monta o vídeo é ops/maquete3d/montar_animado.py.
Uso: python ops/maquete3d/animar.py u02 <saida> [--amostras 20] [--escala 1.0] [--so S1,S3]
"""
import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'ops'))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from maquete3d.estudio import CM, Estudio  # noqa: E402

FPS = 24
# (nome, quadros): 8 planos de 2 a 3,5 s (mestres: troca a cada 1–3 s). v2 30/10: a voz Kokoro tem 25,3 s; com 15 s de
# planos o fecho ficava 8 s parado. BASE = os quadros da v1: os eventos (botão, pinos, pelo) escalam com o plano
PLANOS = [('S1-gancho', 48), ('S2-botao', 48), ('S3-solta', 72), ('S4-monta', 72),
          ('S5-regua', 72), ('S6-giro', 72), ('S7-macro', 60), ('S8-destaque', 84)]
BASE = {'S1-gancho': 36, 'S2-botao': 36}
# 30/10 (regra 129, vídeo de marca e versão BR): planos GENÉRICOS para qualquer maquete, sem a mecânica da escova (pino,
# botão, pelo). Também 8 (a montagem na nuvem espera os 8 caches da matriz S1..S8).
PLANOS_GEN = [('S1-gancho', 48), ('S2-giro', 48), ('S3-regua', 72), ('S4-macro', 48),
              ('S5-alto', 48), ('S6-macro2', 48), ('S7-topo', 48), ('S8-destaque', 72)]


def carregar(cod):
    spec = json.loads((RAIZ / 'maquetes' / f'{cod}.json').read_text(encoding='utf-8'))
    caminho = RAIZ / 'maquetes' / f'{cod}.py'
    m = importlib.util.spec_from_file_location(f'maquete_{cod}', caminho)
    mod = importlib.util.module_from_spec(m)
    m.loader.exec_module(mod)
    return spec, mod


def chave(ob, quadro, loc=None, rot=None, esc=None):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert('location', frame=quadro)
    if rot is not None:
        ob.rotation_euler = rot
        ob.keyframe_insert('rotation_euler', frame=quadro)
    if esc is not None:
        ob.scale = esc
        ob.keyframe_insert('scale', frame=quadro)


def suave(ob):
    """saída e chegada suaves em todas as chaves (o movimento dos mestres não começa nem para de golpe)"""
    ad = ob.animation_data
    if not (ad and ad.action):
        return
    act = ad.action
    if hasattr(act, 'fcurves'):          # Blender até 4.3
        curvas = list(act.fcurves)
    else:                                # Blender 4.4+ (ações em camadas): as curvas ficam nos channelbags
        curvas = [fc for camada in act.layers for faixa in camada.strips for cb in faixa.channelbags for fc in cb.fcurves]
    for fc in curvas:
        for k in fc.keyframe_points:
            k.interpolation = 'BEZIER'
            k.easing = 'EASE_IN_OUT'


class Animacao:
    def realista(self):
        """30/10 (correções do CEO: "pelo com cara de esponja", "material muito liso"; AVANCADO-VIDEO.md §3: o "uau" do material
        vale no quadro 0). Só com --realista, para medir num run antes de virar padrão:
          - plástico com micro-relevo (ruído → bump) e rugosidade mínima 0,35 (o liso de antes refletia como vidro);
          - o pelo vira FIOS (sistema de partículas de cabelo do Cycles, filhos interpolados) em vez do deslocamento;
          - profundidade de campo com foco no centro do produto (a lente macro dos mestres)."""
        for m in bpy.data.materials:
            nt = m.node_tree if m.use_nodes else None
            b = nt.nodes.get('Principled BSDF') if nt else None
            if not b or b.inputs['Metallic'].default_value > 0.5 or m.name.startswith(('regua', 'pelucia')):
                continue
            b.inputs['Roughness'].default_value = max(b.inputs['Roughness'].default_value, 0.35)
            ruido = nt.nodes.new('ShaderNodeTexNoise')
            ruido.inputs['Scale'].default_value = 450.0
            ruido.inputs['Detail'].default_value = 8.0
            relevo = nt.nodes.new('ShaderNodeBump')
            relevo.inputs['Strength'].default_value = 0.06
            relevo.inputs['Distance'].default_value = 0.0004
            nt.links.new(ruido.outputs['Fac'], relevo.inputs['Height'])
            nt.links.new(relevo.outputs['Normal'], b.inputs['Normal'])
        if self.pelo:
            self.pelo.modifiers.clear()   # sai o deslocamento ("esponja")
            ps = self.pelo.modifiers.new('fios', 'PARTICLE_SYSTEM').particle_system.settings
            ps.type, ps.count, ps.hair_length = 'HAIR', 2500, 0.012
            ps.child_type, ps.rendered_child_count, ps.child_nbr = 'INTERPOLATED', 12, 4
            ps.root_radius, ps.tip_radius = 0.0006, 0.0
            ps.use_advanced_hair = True
            ps.use_render_emitter = False   # só os fios aparecem (a bola de antes some)
            ps.roughness_2 = 0.004   # fio solto, nada de palito reto
            fio = bpy.data.materials.new('fio-pelo')
            fio.use_nodes = True
            nt = fio.node_tree
            for n in list(nt.nodes):
                if n.type != 'OUTPUT_MATERIAL':
                    nt.nodes.remove(n)
            hb = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
            hb.parametrization = 'COLOR'
            hb.inputs['Color'].default_value = (0.32, 0.25, 0.19, 1.0)   # cinza-castanho do pelo de cachorro
            nt.links.new(hb.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
            self.pelo.data.materials.append(fio)
            ps.material = len(self.pelo.data.materials)
        cam = self.cam.data
        cam.dof.use_dof = True
        foco = bpy.data.objects.new('foco', None)
        foco.location = (0, 0, self.A / 2 * CM)
        self.e.cena.collection.objects.link(foco)
        cam.dof.focus_object, cam.dof.aperture_fstop = foco, 4.0

    def __init__(self, cod, amostras, escala, realista=False):
        self.spec, mod = carregar(cod)
        self.e = Estudio(cod)
        mod.modelar(self.e, self.spec)
        L, P, A = (self.spec['medidas_cm'][k] for k in ('L', 'P', 'A'))
        self.L, self.P, self.A = L, P, A
        self.escova = cod == 'u02' and 'cabeca' in bpy.data.objects   # os planos com pino, botão e pelo são da u02
        self.pelo = self._pelo() if self.escova else None
        self.regua = self._regua()
        # a régua e o pelo não são o produto: fora da caixa envolvente (o enquadramento e o chão seguem os da maquete)
        extras = {ob.name for ob in self.regua} | {'pelo'}
        self.e.pecas = [ob for ob in self.e.pecas if ob.name not in extras]
        self.e.montar_estudio()
        cena = self.e.cena
        cena.render.fps = FPS
        cena.render.resolution_x, cena.render.resolution_y = int(1080 * escala), int(1920 * escala)   # v2: 9:16 cheio, sem faixa preta
        cena.render.resolution_percentage = 100
        cena.cycles.samples = amostras
        self.planos = PLANOS if self.escova else PLANOS_GEN
        # 30/10: o 1º render (8 planos, 20 amostras) passou das 2 h do runner; luz mais curta e amostragem adaptativa
        cena.cycles.use_adaptive_sampling = True
        cena.cycles.max_bounces, cena.cycles.transparent_max_bounces = 4, 4
        cena.render.use_persistent_data = True
        self.cam = self.e.camera
        if realista:
            self.realista()
        self.base = {ob.name: (ob.location.copy(), ob.rotation_euler.copy(), ob.scale.copy()) for ob in bpy.data.objects}

    # -- peças a mais da animação (não entram na maquete do site)
    def _pelo(self):
        """o tufo de pelo solto em cima dos pinos (o que a escova junta e o botão solta)"""
        cab = bpy.data.objects['cabeca']
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=0.5)
        bmesh.ops.scale(bm, vec=(self.P * 0.82 * CM, self.P * 0.78 * CM, 0.9 * CM), verts=bm.verts)
        me = bpy.data.meshes.new('pelo')
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new('pelo', me)
        self.e.col_produto.objects.link(ob)
        ob.location = (cab.location.x, 0, (self.A + 0.15) * CM)
        tex = bpy.data.textures.new('fiapos', 'CLOUDS')
        tex.noise_scale = 0.0015   # v2: fiapo fino (a v1 parecia uma panqueca lisa)
        tex.noise_depth = 4
        d = ob.modifiers.new('fiapos', 'DISPLACE')
        d.texture, d.strength = tex, 0.012
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(self.e.mat('pelucia', '#9A8571'))   # v2: pelo de cachorro cinza-castanho, contraste com a escova branca
        return ob

    def _regua(self):
        """régua Tavrov em escala real: o comprimento do produto arredondado para cima de 10 em 10 cm (mínimo 20), traço a
        cada 1 cm (5 cm acima de 30), número a cada 5 (10 acima de 30) e a marca da medida do anúncio (L) em destaque.
        u02: 0 a 20 cm com a marca dos 18, como antes; p06: 0 a 70 com a dos 68,5"""
        preta, branca = self.e.mat('plastico_fosco', '#1B1B1B'), self.e.mat('plastico_fosco', '#F4F1EA')
        y = -(self.P / 2 + 2.2)
        comp = max(20, int(math.ceil(self.L / 10.0)) * 10)
        passo, num = (1, 5) if comp <= 30 else (5, 10)
        esc_t = comp / 20.0   # traços e números maiores na régua comprida (a câmera recua)
        pecas = [self.e.caixa('regua-base', comp + 1.0, 3.0 * esc_t, 0.25, pos=(0.5 - self.L / 2 + comp / 2, y, 0.125),
                              mat=branca, raio=0.2)]
        for c in range(0, comp + 1, passo):
            alto = (1.2 if c % num == 0 else 0.6) * esc_t
            pecas.append(self.e.caixa(f'regua-traco{c}', 0.07 * esc_t, alto, 0.05,
                                      pos=(-self.L / 2 + c, y + 1.5 * esc_t - alto / 2, 0.27), mat=preta, raio=0.0))
        medida = round(self.L, 1)
        for c in sorted(set(range(0, comp + 1, num)) | {medida}):
            cu = bpy.data.curves.new(f'regua-n{c}', 'FONT')
            cu.body = f'{c:g} cm' if c == medida else str(c)
            cu.size = 0.7 * CM * esc_t
            cu.align_x = 'CENTER'
            ob = bpy.data.objects.new(f'regua-n{c}', cu)
            ob.location = ((-self.L / 2 + c) * CM, (y - 0.7 * esc_t) * CM, 0.27 * CM)
            ob.data.materials.append(preta)
            self.e.col_produto.objects.link(ob)
            pecas.append(ob)
        # a marca da medida do anúncio em destaque (u02: 18 cm)
        pecas.append(self.e.caixa('regua-18', 0.12 * esc_t, 2.6 * esc_t, 0.06, pos=(self.L / 2, y + 0.9 * esc_t, 0.29),
                                  mat=self.e.mat('plastico_fosco', '#D9B65E'), raio=0.0))
        return pecas

    # -- utilidades
    def zerar(self):
        for ob in bpy.data.objects:
            ob.animation_data_clear()
            if ob.name in self.base:
                ob.location, ob.rotation_euler, ob.scale = self.base[ob.name]
        for ob in self.regua:
            ob.hide_render = True
        if self.pelo:
            self.pelo.hide_render = False

    def cam_em(self, quadro, az, el, lente=70, alvo=None, zoom=1.0):
        self.e.enquadrar(az, el, lente=lente, alvo=alvo, zoom=zoom)
        chave(self.cam, quadro, loc=self.cam.location.copy(), rot=self.cam.rotation_euler.copy())

    def pinos(self):
        return [ob for ob in bpy.data.objects if ob.name.startswith(('pino', 'bola'))]

    def render(self, nome, quadros, saida):
        cena = self.e.cena
        cena.frame_start, cena.frame_end = 1, quadros
        for ob in bpy.data.objects:
            suave(ob)
        pasta = Path(saida) / nome
        pasta.mkdir(parents=True, exist_ok=True)
        cena.render.filepath = str(pasta) + '/'
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        print(f'{nome}: {quadros} quadros em {time.time() - t0:.0f} s', flush=True)

    # -- os 8 planos
    def plano_generico(self, nome, n):
        """os 8 planos de qualquer maquete: o produto se mexe pela câmera (giro, macro, régua, topo), sem mecânica própria"""
        self.zerar()
        L, A = self.L, self.A
        if nome == 'S1-gancho':      # quadro 0: o produto inteiro chegando perto (push-in)
            self.cam_em(1, -35, 28, lente=60, zoom=0.85)
            self.cam_em(n, -20, 24, lente=60, zoom=1.15)
        elif nome == 'S2-giro':      # giro de 90 graus, câmera média
            self.cam_em(1, -70, 22, lente=55, zoom=1.0)
            self.cam_em(n, 20, 22, lente=55, zoom=1.0)
        elif nome == 'S3-regua':     # a régua no tamanho real entra por baixo; vista de cima
            for ob in self.regua:
                ob.hide_render = False
                chave(ob, 1, loc=ob.location + Vector((0, -4 * CM, 0)))
                chave(ob, 18, loc=ob.location.copy())
            self.cam_em(1, -5, 62, lente=50, alvo=(0, -3, 0), zoom=0.85)
            self.cam_em(n, 0, 72, lente=50, alvo=(0, -3, 0), zoom=0.9)
        elif nome == 'S4-macro':     # travelling rente a um canto do produto
            self.cam_em(1, -60, 14, lente=100, alvo=(-L * 0.25, 0, A * 0.6), zoom=2.4)
            self.cam_em(n, -60, 14, lente=100, alvo=(L * 0.05, 0, A * 0.6), zoom=2.4)
        elif nome == 'S5-alto':      # câmera alta descendo
            self.cam_em(1, 30, 55, lente=60, zoom=0.95)
            self.cam_em(n, 45, 30, lente=60, zoom=1.05)
        elif nome == 'S6-macro2':    # macro do outro lado
            self.cam_em(1, 120, 16, lente=100, alvo=(L * 0.25, 0, A * 0.6), zoom=2.4)
            self.cam_em(n, 120, 16, lente=100, alvo=(-L * 0.05, 0, A * 0.6), zoom=2.4)
        elif nome == 'S7-topo':      # de cima, girando devagar
            self.cam_em(1, -10, 80, lente=55, zoom=0.95)
            self.cam_em(n, 30, 80, lente=55, zoom=0.95)
        else:                        # S8-destaque: recuo em giro lento, o produto inteiro para o fecho
            self.cam_em(1, 20, 30, lente=70, zoom=1.3)
            self.cam_em(n, -35, 22, lente=70, zoom=0.9)

    def plano(self, nome, n):
        if not self.escova:
            return self.plano_generico(nome, n)
        self.zerar()
        b = BASE.get(nome, 48)
        q = lambda k: max(1, round(k * n / b))   # o quadro do evento escala com a duração do plano
        cab = bpy.data.objects['cabeca']
        xh = cab.location.x / CM
        botao = bpy.data.objects['botao']
        if nome == 'S1-gancho':      # quadro 0: macro no pelo preso nos pinos, push-in rápido
            self.cam_em(1, -40, 38, lente=85, alvo=(xh, 0, self.A), zoom=1.6)
            self.cam_em(n, -24, 30, lente=85, alvo=(xh, 0, self.A), zoom=2.6)
        elif nome == 'S2-botao':     # o dedo invisível aperta o botão: o botão desce
            self.cam_em(1, -70, 24, lente=85, alvo=(botao.location.x / CM, 0, 2.0), zoom=3.2)
            self.cam_em(n, -55, 30, lente=85, alvo=(botao.location.x / CM, 0, 2.0), zoom=3.6)
            z0 = botao.location.z
            chave(botao, 1, loc=Vector((botao.location.x, 0, z0)))
            chave(botao, q(14), loc=Vector((botao.location.x, 0, z0)))
            chave(botao, q(22), loc=Vector((botao.location.x, 0, z0 - 0.22 * CM)))
        elif nome == 'S3-solta':     # os pinos recolhem e o tufo de pelo escorrega e cai: a prova
            self.cam_em(1, -30, 34, lente=70, alvo=(xh, 0, 1.5), zoom=1.7)
            self.cam_em(n, -10, 26, lente=70, alvo=(xh, 0, 1.0), zoom=1.5)
            for ob in self.pinos():
                z0 = ob.location.z
                chave(ob, 1, loc=ob.location.copy())
                chave(ob, q(6), loc=ob.location.copy())
                chave(ob, q(16), loc=Vector((ob.location.x, ob.location.y, z0 - (self.A - 1.6) * CM)))
            p = self.pelo
            z0 = p.location.z
            chave(p, 1, loc=p.location.copy(), rot=Vector((0, 0, 0)))
            chave(p, q(12), loc=Vector((p.location.x, 0, 1.55 * CM)), rot=Vector((0, 0, 0)))
            chave(p, q(40), loc=Vector((p.location.x + (self.P * 0.9) * CM, 0, 0.45 * CM)), rot=Vector((0, math.radians(28), 0.3)))
        elif nome == 'S4-monta':     # explodir e montar (mestre SMEG): as peças voam para o lugar
            self.pelo.hide_render = True
            self.cam_em(1, -35, 30, lente=50, zoom=0.75)
            self.cam_em(n, -20, 24, lente=50, zoom=1.0)
            voo = {'cabo': Vector((-14, 0, 6)), 'cabeca': Vector((10, 0, 9)), 'botao': Vector((-6, 0, 12))}
            for ob in bpy.data.objects:
                if ob.name in voo:
                    d = voo[ob.name] * CM
                elif ob.name.startswith(('pino', 'bola')):
                    i = int(ob.name[4:].split('-')[0]) if ob.name.startswith('pino') else int(ob.name[4:].split('-')[0])
                    d = Vector((0, 0, (5 + i * 1.2))) * CM
                else:
                    continue
                destino = ob.location.copy()
                chave(ob, 1, loc=destino + d)
                chave(ob, q(30 + (int(d.z / CM) % 6)), loc=destino)
        elif nome == 'S5-regua':     # a régua em escala real entra por baixo; vista de cima
            self.pelo.hide_render = True
            for ob in self.regua:
                ob.hide_render = False
                chave(ob, 1, loc=ob.location + Vector((0, -4 * CM, 0)))
                chave(ob, q(18), loc=ob.location.copy())
            self.cam_em(1, -5, 62, lente=50, alvo=(0, -3, 0), zoom=0.9)
            self.cam_em(n, 0, 72, lente=50, alvo=(0, -3, 0), zoom=0.95)
        elif nome == 'S6-giro':      # giro de 120 graus, câmera baixa (destaque)
            self.pelo.hide_render = True
            for k, az in enumerate((-60, 0, 60)):
                self.cam_em(1 + k * (n - 1) // 2, az, 16, lente=70, zoom=1.0)
        elif nome == 'S7-macro':     # travelling lateral rente aos pinos (macro do detalhe)
            self.pelo.hide_render = True
            self.cam_em(1, -80, 12, lente=100, alvo=(xh - 2.5, 0, 2.2), zoom=3.0)
            self.cam_em(n, -80, 12, lente=100, alvo=(xh + 2.5, 0, 2.2), zoom=3.0)
        elif nome == 'S8-destaque':  # recuo em giro lento: o produto inteiro para o preço
            self.pelo.hide_render = True
            self.cam_em(1, 20, 30, lente=70, zoom=1.35)
            self.cam_em(n, -35, 22, lente=70, zoom=0.95)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cod')
    ap.add_argument('saida')
    ap.add_argument('--amostras', type=int, default=20)
    ap.add_argument('--escala', type=float, default=1.0)
    ap.add_argument('--so', default='')
    ap.add_argument('--realista', action='store_true')   # 30/10: pelo em fios, plástico com micro-relevo, foco (Animacao.realista)
    ap.add_argument('--quadros', type=int, default=0)   # 30/10 (prova de bancada de 10 min): só os N primeiros quadros
    a = ap.parse_args()
    an = Animacao(a.cod, a.amostras, a.escala, a.realista)
    so = set(filter(None, a.so.split(',')))
    for nome, n in an.planos:
        if so and nome.split('-')[0] not in so:
            continue
        an.plano(nome, n)
        an.render(nome, min(n, a.quadros) if a.quadros else n, a.saida)


if __name__ == '__main__':
    main()
