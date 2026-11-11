"""Bestiário/Codex lore text (docs/design/12-monstros.md, 13-chefes.md).

Purely descriptive content, keyed by the same enemy id used everywhere
else (EncounterDef.enemy_ids, ENEMY_DEFS) -- no new engine concept, just
a dict the UI reads once an id is discovered (see
persistence/store.py::MetaProgressionState.discover_enemy).
"""

from __future__ import annotations

BESTIARY_ENTRIES: dict[str, str] = {
    "goblin": "Pequeno, oportunista e covarde sozinho -- mas o Túmulo Oco está cheio deles, e em grupo mordem forte.",
    "skitterling": "Rápido demais para se esquivar com calma, e seu ferrão carrega um veneno fraco mas persistente.",
    "bonewarden": "Ossos antigos amarrados por um pacto esquecido, lento mas quase impossível de derrubar de perto.",
    "hollow_knight": (
        "Ele se ergue de seu trono de ossos, e o Túmulo Oco lembra o nome de quem ele foi -- "
        "o primeiro guardião de verdade que a masmorra tem a oferecer."
    ),
    "cinderling": "Uma chama pequena com pernas. Morre fácil, mas explode ao cair -- não se aproxime displicente.",
    "forge_automaton": "Um construto lento e pesado, forjado para golpear com toda a força que carrega.",
    "living_bellows": "Um saco de couro e brasa que infla os outros ao seu redor, tornando-os mais perigosos.",
    "magma_golem": (
        "Rachaduras de magma cruzam sua pele de pedra. Alterna entre investidas e explosões de fogo em área."
    ),
    "ashkarion": (
        "Um elemental de fogo colossal, aprisionado havia eras dentro de uma armadura de forjador "
        "que ele mesmo nunca pediu."
    ),
    "lobo_de_gelo": "Caça em matilha pela trilha congelada, e cada mordida deixa a presa mais lenta.",
    "espectro_gelado": "Um sopro de frio com forma vaga, que enfraquece aos poucos tudo que toca.",
    "xama_da_nevasca": "Ergue barreiras de gelo para proteger os seus -- o único do grupo que luta para curar.",
    "ceifador_de_carambano": (
        "Fica mais perigoso perto do gelo do pico, e suas rajadas de carâmbano fragilizam de uma vez só."
    ),
    "viuva_de_gelo": (
        "Guarda o pico há tanto tempo que ninguém mais lembra o que ela estava esperando -- "
        "quanto mais a batalha se arrasta, mais forte a nevasca ao redor dela fica."
    ),
    "ave_trovao": "Corta o céu antes mesmo do trovão -- ninguém age mais rápido que ela.",
    "sentinela_eletrizada": "Ergue o escudo e espera. Quem golpeia primeiro leva um choque de volta.",
    "arauto_da_tempestade": "Acelera os companheiros a cada descarga de Raio que lança.",
    "colosso_carregado": "Pulsa com energia acumulada a cada turno, até liberar tudo de uma vez.",
    "voltharion": (
        "Um relâmpago que aprendeu a vestir uma armadura, e depois esqueceu como tirá-la -- "
        "seu golpe de assinatura encadeia entre todos que ousam ficar por perto."
    ),
    "afogado": "Se arrasta pela água rasa, e cada garra encharca quem ele agarra.",
    "enguia_espectral": "Desliza silenciosa pela água escura, sugando a vontade de quem se aproxima.",
    "sacerdotisa_afogada": "Canta uma bênção antiga, e a água ao redor cura quem ainda a serve.",
    "kraken_jovem": "Vários tentáculos, vários golpes -- e todos eles deixam a presa encharcada.",
    "maremoto": (
        "Um leviatã que lembra de quando aquele templo ainda estava seco -- "
        "a terra bebe sua água como nada mais consegue."
    ),
    "verme_de_pedra": "Emerge da rocha antes que qualquer um perceba -- ninguém age mais cedo que ele.",
    "golem_de_cascalho": "Frágil sozinho, mas nunca vem sozinho -- as minas estão cheias deles.",
    "xama_de_pedra": "Canta uma maldição que racha a pedra ao redor -- e tudo que ela toca.",
    "guardiao_cristalino": "Coberto de cristais afiados -- cada golpe contra ele dói duas vezes.",
    "terrakon": (
        "Não é uma criatura que vive na montanha. É a montanha, tentando se lembrar de como se mover."
    ),
    "harpia": "Circula em bando pelas pontes estreitas, e cada rajada deixa o alvo mais fácil de acertar de volta.",
    "elemental_de_vento": "Gira nas correntes de ar acima do abismo, rápido demais pra se prender a um só lugar.",
    "arauto_do_vendaval": "Convoca ventos que atrasam qualquer um que tente se aproximar rápido demais.",
    "roc_menor": "Observa do alto do ninho, esperando o primeiro erro pra punir quem errou.",
    "zephyra": (
        "O vento nesses pináculos já levou tudo que não estava preso -- "
        "inclusive, em algum momento, o resto dela mesma."
    ),
    "sanguessuga_gigante": "Se agarra e não solta -- cada mordida cura mais ela do que fere quem é mordido.",
    "esporo_ambulante": "Flutua baixo pelo charco, e explode numa nuvem de esporos se atacado de perto demais.",
    "xama_do_lodo": "Canta sobre o pântano, fazendo o veneno grudar mais fundo em quem já está envenenado.",
    "horror_do_charco": "Emerge da lama e se cura do próprio veneno -- ironia que só um horror consegue viver.",
    "mae_putrida": "Não tem rosto. Só tem fome, e uma quantidade obscena de filhotes.",
    "serafim_partido": "Se cura sozinho, e força qualquer batalha a durar mais do que deveria.",
    "zelote_cego": "Quanto mais ferido, mais perigoso -- nunca hesita, nem quando deveria recuar.",
    "cantor_de_hinos": "Entoa hinos que pesam mais do que curam quem os ouve.",
    "guardiao_de_luz": "Vigia o altar sem medo, luz cortante reservada pra quem já morreu uma vez.",
    "solyth": "Guardou este lugar tempo demais sozinho. O que sobrou de piedade virou outra coisa.",
    "sussurro": "Sussurra medos que não são bem seus, e a escuridão empresta força a cada palavra.",
    "carne_amaldicoada": "Recusa-se a ficar de vez no chão -- mesmo sem PV, ainda tem um último golpe.",
    "arauto_do_veu": "Torna os seus difíceis de acertar, um manto de sombra sobre cada aliado.",
    "devorador_de_luz": "Suga o ambiente ao redor, e a própria vontade de quem se aproxima.",
    "o_inominavel": (
        "Não tem uma forma. Tem uma coleção de máscaras, e nenhuma memória de qual delas veio primeiro."
    ),
    "livro_errante": "Flutua entre as estantes, e cada página virada ignora um pouco mais de qualquer defesa.",
    "eco_arcano": "Nunca luta da mesma forma duas vezes -- imita um arquétipo diferente a cada golpe.",
    "copista_louco": "Tenta copiar tudo o que vê, e devolve cada cópia um pouco mais distorcida que o original.",
    "paradoxo_ambulante": "Seu elemento muda a cada investida -- não existe uma resistência certa contra ele.",
    "eco_de_nyxelle_fogo": "Uma cópia mais fraca de Nyxelle, presa a um resquício de fogo que nunca apaga.",
    "eco_de_nyxelle_gelo": "Uma cópia mais fraca de Nyxelle, presa a um resquício de gelo que nunca derrete.",
    "nyxelle": (
        "Tentou catalogar todo o conhecimento arcano existente. O conhecimento não coube nela -- "
        "ela coube em vários pedaços do conhecimento, em vez disso."
    ),
    "sombra_de_arquetipo": "Um espectro que veste a forma de um destino roubado -- o próprio herói, virado contra ele.",
    "fiandeira_menor": "Tece o ritmo da luta final nos dedos -- mata-a rápido se quiser desacelerar o que vem depois.",
    "tecela_desfeita": "O próprio Wyrd, desfiando-se. É de onde o nome do lugar -- e do jogo -- vem.",
}
