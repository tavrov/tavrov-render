"""Composição das fotos das maquetes: render transparente + sombra → foto no fundo da marca.
Sem Blender (só Pillow): `python ops/gerar-3d.py --recompor` troca o fundo a partir dos renders
guardados em maquetes/renders/<cod>/.
"""
from pathlib import Path

# Fundo único das fotos de todas as maquetes: tom quente médio (L* ≈ 79), para produto branco e
# produto preto ficarem legíveis no mesmo fundo (tarefa nuvem 07, CEO 02/10: o branco sumia no #F2ECEA).
FUNDO_HEX = '#CBC2B9'


def compor(png, destino, fundo=FUNDO_HEX, qualidade=90, tamanho=None, quadrado=False):
    """Render com fundo transparente + sombra → imagem final no fundo da marca.
    `quadrado=True`: completa com o fundo até ficar quadrada (o cartão da vitrine é 1:1)."""
    from PIL import Image
    im = Image.open(png).convert('RGBA')
    base = Image.new('RGBA', im.size, fundo)
    base.alpha_composite(im)
    out = base.convert('RGB')
    if quadrado:
        # a foto ocupa 84% da largura e desce: o alto do cartão fica livre para a etiqueta e o coração da vitrine
        lado = int(max(out.size) / 0.84)
        q = Image.new('RGB', (lado, lado), fundo)
        # bordas esfumadas: a foto se funde com o fundo, sem aparecer o retângulo dela
        from PIL import ImageDraw, ImageFilter
        w, h = out.size
        borda = int(min(w, h) * 0.06)
        mascara = Image.new('L', (w, h), 0)
        ImageDraw.Draw(mascara).rectangle((borda, borda, w - borda, h - borda), fill=255)
        mascara = mascara.filter(ImageFilter.GaussianBlur(borda / 2))
        q.paste(out, ((lado - w) // 2, int((lado - h) * 0.86)), mascara)
        out = q
    if tamanho:
        out = out.resize(tamanho, Image.LANCZOS)
    destino = Path(destino)
    fmt = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.png': 'PNG'}[destino.suffix.lower()]
    kw = {'quality': qualidade} if fmt in ('JPEG', 'WEBP') else {}
    if fmt == 'JPEG':
        kw.update(optimize=True, progressive=True)
    out.save(destino, fmt, **kw)
    return destino
