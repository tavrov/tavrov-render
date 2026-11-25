"""p51 · Kit de escovinhas para desentupir os furos do chuveiro (10 unidades) — maquete REPRESENTATIVA.

Forma pela foto oficial do anúncio da Shopee (loja CRUZEIRO ELETRO; só referência, sem logotipo, sem texto):
- cabo de plástico branco, achatado, com frisos de pega na metade de baixo;
- pescoço fino branco que sai do cabo;
- ponta curta de cerdas de náilon brancas (a parte que entra no furo do chuveiro);
- o kit aparece com as 10 escovinhas deitadas lado a lado.
Medida: o anúncio não dá. 9 cm de comprimento total e 0,9 cm de largura do cabo são hipótese pela proporção da
foto (a escovinha ao lado dos dedos e do chuveirinho); aviso no laudo.
Eixos: X = as 10 escovinhas lado a lado; Y = o comprimento de cada uma; deitadas no chão em z = 0.
"""
BRANCO = '#F2F2EF'
FRISO = '#DCDCD6'
CERDA = '#FAFAF7'

N, PASSO = 10, 1.3
CABO_L, CABO_C, CABO_A = 0.9, 6.0, 0.7
PESC_D, PESC_C = 0.3, 1.5
CERDA_D, CERDA_C = 0.35, 1.5


def modelar(e, spec):
    cabo_m = e.mat('plastico_fosco', BRANCO)
    friso_m = e.mat('plastico_fosco', FRISO)
    cerda_m = e.mat('plastico_fosco', CERDA)
    z = CABO_A / 2
    y0 = -(CABO_C + PESC_C + CERDA_C) / 2          # ponta de trás do cabo
    for i in range(N):
        x = -(N - 1) * PASSO / 2 + i * PASSO
        e.caixa(f'cabo{i}', CABO_L, CABO_C, CABO_A, pos=(x, y0 + CABO_C / 2, z), mat=cabo_m, raio=0.3)
        for k in range(6):                         # frisos de pega na metade de baixo do cabo
            e.caixa(f'friso{i}-{k}', CABO_L * 0.8, 0.12, 0.05,
                    pos=(x, y0 + 0.6 + k * 0.45, CABO_A - 0.025), mat=friso_m, raio=0.02)
        e.cilindro(f'pescoco{i}', PESC_D, PESC_C, pos=(x, y0 + CABO_C + PESC_C / 2, z), rot=(90, 0, 0),
                   mat=cabo_m, raio=0.03)
        e.cilindro(f'cerda{i}', CERDA_D, CERDA_C, pos=(x, y0 + CABO_C + PESC_C + CERDA_C / 2, z), rot=(90, 0, 0),
                   mat=cerda_m, raio=0.05)
